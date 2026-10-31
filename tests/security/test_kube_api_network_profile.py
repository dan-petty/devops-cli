"""The `kube-api` network profile of the tool sandbox: only Popeye selects it, a run with it reaches
the Kubernetes API server only through `kubectl proxy` and `socat`, and the record of each run
names the network of the tool (#2132).

These cases fake the process edge with `process_fake`, so no sandbox, proxy or tool starts. The
fake finds each program that a run looks for at `/usr/local/bin/<name>`. The executor gets a
`HostSandbox` with a stand-in for bubblewrap.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.config.constants import (
    CONST_KUBE_API_HOST_SCRIPT,
    CONST_KUBE_API_REJECTED_METHODS,
    CONST_KUBE_API_REJECTED_PATHS,
    CONST_KUBE_API_SANDBOX_SCRIPT,
    CONST_KUBE_API_SCRIPT_NAME,
    CONST_TOOL_MIN_ADDRESS_SPACE_BYTES,
)
from devops_cli.exceptions.sandbox import SandboxError, SandboxUnavailableError
from devops_cli.sandbox.host import HostSandbox
from devops_cli.sandbox.kube_api import kube_api_relay
from devops_cli.security.registry import ScannerRegistry
from devops_cli.security.tool_executor import (
    DirectToolExecutor,
    KubeApiNetwork,
    SandboxToolExecutor,
    ToolRequest,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

# The contexts of the kubeconfig of the user, with their namespaces. `example` is the current one.
_USER_CONTEXTS = {"example": "apps", "other": "tools"}
_CURRENT_CONTEXT = "example"


def _kubectl_config_view(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `kubectl config view --minify --output=json` prints for the kubeconfig of the user: the
    context that the command selects, else the current one, with a cluster at a documentation
    address and the credentials redacted. A context that the kubeconfig does not have fails."""
    selected = next(
        (arg.removeprefix("--context=") for arg in call.argv if arg.startswith("--context=")),
        _CURRENT_CONTEXT,
    )
    if selected not in _USER_CONTEXTS:
        return subprocess.CompletedProcess(
            list(call.argv), 1, "", f"error: cannot locate context {selected}\n"
        )
    view = {
        "apiVersion": "v1",
        "kind": "Config",
        "current-context": selected,
        "clusters": [{"name": selected, "cluster": {"server": "https://192.0.2.10:6443"}}],
        "contexts": [
            {
                "name": selected,
                "context": {
                    "cluster": selected,
                    "user": selected,
                    "namespace": _USER_CONTEXTS[selected],
                },
            }
        ],
        "users": [{"name": selected, "user": {"token": "REDACTED"}}],
    }
    return subprocess.CompletedProcess(list(call.argv), 0, json.dumps(view), "")


def _is_config_view(call: ProcessCall) -> bool:
    """Whether `call` reads the kubeconfig of the user with `kubectl config view`."""
    return call.argv[1:4] == ("config", "view", "--minify")


def _stand_in(path: Path) -> Path:
    """An executable file at `path` that nothing starts: `process_fake` answers each command."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture
def bwrap(tmp_path: Path) -> Path:
    """A stand-in for bubblewrap."""
    return _stand_in(tmp_path / "bwrap-bin" / "bwrap")


@pytest.fixture
def kube_tree(tmp_path: Path) -> Path:
    """An empty tree outside any checkout, as Popeye scans."""
    root = (tmp_path / "tree").resolve()
    root.mkdir()
    return root


@pytest.fixture
def user_kubeconfig(process_fake: ProcessFake) -> ProcessFake:
    """The process fake, with `kubectl config view` answered from the kubeconfig of the user."""
    process_fake.answer(_is_config_view, ProcessAnswer(side_effect=_kubectl_config_view))
    return process_fake


def _request(tree: Path, tool: str = "popeye", **fields: Any) -> ToolRequest:
    """A request to run `tool` over `tree`."""
    return ToolRequest(tool=tool, arguments=("-o", "json"), workdir=tree, targets=(tree,), **fields)


def _scanner_tools() -> dict[str, str]:
    """The tool of each scanner of the scanner registry, by the name of the scanner."""
    registry = ScannerRegistry(auto_load_defaults=True)
    scanners = (registry.get(name) for name in registry.list_scanners())
    return {scanner.name: scanner.binary_name for scanner in scanners if scanner is not None}


def _binds(bwrap_command: list[str] | tuple[str, ...]) -> list[list[str]]:
    """Each bind option of a bubblewrap command, as `[flag, source, destination]`."""
    options = list(bwrap_command[: bwrap_command.index("--")])
    return [options[i : i + 3] for i, flag in enumerate(options) if flag in {"--ro-bind", "--bind"}]


def _setenv(bwrap_command: tuple[str, ...]) -> dict[str, str]:
    """The environment that a bubblewrap command sets in the sandbox."""
    options = bwrap_command[: bwrap_command.index("--")]
    return {options[i + 1]: options[i + 2] for i, flag in enumerate(options) if flag == "--setenv"}


def _split(argv: tuple[str, ...], bwrap: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The command of a kube-api run: the host script and its arguments, then bubblewrap."""
    start = argv.index(str(bwrap))
    return argv[:start], argv[start:]


def _kube_api_run(process_fake: ProcessFake) -> tuple[str, ...]:
    """The command of the one run, after the read of the kubeconfig and the check of the host."""
    view, _check, run = process_fake.calls
    assert _is_config_view(view)
    return run.argv


def test_no_other_scanner_can_select_the_kube_api_network_profile(kube_tree: Path) -> None:
    """A request for the tool of each scanner other than Popeye that selects the profile is
    refused. A request for Popeye that selects it is accepted."""
    others = sorted(tool for name, tool in _scanner_tools().items() if name != "popeye")
    refused = []
    for tool in others:
        with pytest.raises(ValidationError, match="kube-api"):
            _request(kube_tree, tool, network=KubeApiNetwork())
        refused.append(tool)

    accepted = _request(kube_tree, network=KubeApiNetwork(context="example"))

    assert (len(refused), refused == others, accepted.network) == (
        len(_scanner_tools()) - 1,
        True,
        KubeApiNetwork(context="example"),
    )


def test_a_popeye_request_from_another_program_cannot_select_the_profile(
    kube_tree: Path, tmp_path: Path
) -> None:
    """A program can start another binary under the name of Popeye, so a request that names one
    cannot select the profile."""
    program = _stand_in(tmp_path / "elsewhere" / "popeye")

    with pytest.raises(ValidationError, match="program"):
        _request(kube_tree, program=program, network=KubeApiNetwork())


def test_only_the_popeye_scanner_selects_a_network() -> None:
    """Popeye selects the profile for the context of its scan, and for the current context when
    the scan names none or `current`. Every other scanner selects no network."""
    registry = ScannerRegistry(auto_load_defaults=True)
    networks = {
        name: scanner.tool_network(context="example")
        for name in registry.list_scanners()
        if (scanner := registry.get(name)) is not None
    }
    popeye = registry.get("popeye")
    assert popeye is not None

    assert (
        {name: network for name, network in networks.items() if network is not None},
        popeye.tool_network(context="current"),
        popeye.tool_network(),
    ) == (
        {"popeye": KubeApiNetwork(context="example")},
        KubeApiNetwork(context=None),
        KubeApiNetwork(context=None),
    )


def test_the_direct_executor_runs_no_network_profile(
    kube_tree: Path, process_fake: ProcessFake
) -> None:
    """The direct executor gives a tool the whole network of the host, so it refuses a request
    that selects a profile, and starts nothing."""
    with pytest.raises(SandboxError, match="kube-api"):
        DirectToolExecutor().run(_request(kube_tree, network=KubeApiNetwork()))

    assert process_fake.calls == []


def test_the_record_of_a_run_names_the_network_of_the_tool(
    kube_tree: Path, bwrap: Path, user_kubeconfig: Path, process_fake: ProcessFake
) -> None:
    """The direct executor gives a tool the network of the host, the sandbox gives it none, and
    the sandbox with the profile gives Popeye the profile."""
    direct = DirectToolExecutor().run(_request(kube_tree, "gitleaks"))
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))
    sandbox = executor.run(_request(kube_tree, "gitleaks"))
    kube_api = executor.run(_request(kube_tree, network=KubeApiNetwork()))

    assert (direct.run.network, sandbox.run.network, kube_api.run.network) == (
        "host",
        "none",
        "kube-api",
    )


def test_a_kube_api_run_reaches_the_api_server_only_through_kubectl_proxy_and_socat(
    kube_tree: Path, bwrap: Path, user_kubeconfig: Path, process_fake: ProcessFake
) -> None:
    """Outside the sandbox, a shell starts `kubectl proxy` for the context on a socket of a scratch
    directory, with the methods and paths that it refuses, then bubblewrap. bubblewrap keeps
    `--unshare-all`, binds the scratch directory read-only, and starts a shell that relays the
    loopback port to the socket with `socat`, then Popeye under `prlimit`."""
    SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap)).run(
        _request(kube_tree, network=KubeApiNetwork())
    )

    host, sandbox = _split(_kube_api_run(process_fake), bwrap)
    socket = Path(host[4])
    scratch = str(socket.parent)
    which = shutil.which
    assert (
        host,
        sandbox[sandbox.index("--") + 1 :],
        "--unshare-all" in sandbox,
        "--share-net" in sandbox,
        ["--ro-bind", scratch, scratch] in _binds(sandbox),
        _setenv(sandbox)["KUBECONFIG"],
    ) == (
        (
            which("sh"),
            "-c",
            CONST_KUBE_API_HOST_SCRIPT,
            CONST_KUBE_API_SCRIPT_NAME,
            str(socket),
            which("setpriv"),
            which("kubectl"),
            "example",
            CONST_KUBE_API_REJECTED_METHODS,
            ",".join(CONST_KUBE_API_REJECTED_PATHS),
            which("socat"),
            "100",
            "0.1",
        ),
        (
            which("sh"),
            "-c",
            CONST_KUBE_API_SANDBOX_SCRIPT,
            CONST_KUBE_API_SCRIPT_NAME,
            which("socat"),
            str(socket),
            "8001",
            "100",
            "0.1",
            which("prlimit"),
            "--cpu=600",
            f"--as={CONST_TOOL_MIN_ADDRESS_SPACE_BYTES}",
            "--",
            which("popeye"),
            "-o",
            "json",
        ),
        True,
        False,
        True,
        str(socket.parent / "kubeconfig.json"),
    )


def test_a_relay_runs_only_with_a_request_that_selects_the_kube_api_profile(
    kube_tree: Path, bwrap: Path, user_kubeconfig: Path, process_fake: ProcessFake
) -> None:
    """The command of a request that selects no network profile gets no relay, so no other tool
    reaches the API server through a relay that a caller gives it. A request that selects
    `kube-api` gets no command without its relay. Neither starts a process."""
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))

    with kube_api_relay(None) as relay, pytest.raises(SandboxError, match="gitleaks"):
        executor.command(_request(kube_tree, "gitleaks"), relay)
    with pytest.raises(SandboxError, match="kube-api"):
        executor.command(_request(kube_tree, network=KubeApiNetwork()))

    assert [_is_config_view(call) for call in process_fake.calls] == [True]


# Requests through the proxy. Popeye reads the first paths. The others reach a process, a port or a
# server behind the API server. `kubectl proxy` v1.37.1 with the filters of a kube-api run sent each
# read path to the API server and answered `403 Forbidden` for each other path, and for POST, PUT,
# PATCH, DELETE and `post` (2026-10-28).
_READ_PATHS = (
    "/version",
    "/api/v1/pods",
    "/api/v1/namespaces/apps/pods/web-0",
    "/api/v1/nodes/node-1",
    "/apis/apps/v1/namespaces/apps/deployments",
    "/apis/metrics.k8s.io/v1beta1/pods",
)
_PATHS_PAST_THE_API_SERVER = (
    "/api/v1/namespaces/apps/pods/web-0/exec",
    "/api/v1/namespaces/apps/pods/web-0/attach",
    "/api/v1/namespaces/apps/pods/web-0/portforward",
    "/api/v1/namespaces/apps/pods/web-0:8080/proxy/metrics",
    "/api/v1/namespaces/apps/services/web:http/proxy/",
    "/api/v1/nodes/node-1/proxy/stats/summary",
)
_READ_METHODS = ("GET", "HEAD")
_WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE", "post")


def _refused(flag: str, value: str) -> bool:
    """Whether `kubectl proxy` refuses `value` for the value `flag` of `--reject-methods` or
    `--reject-paths`. kubectl splits the flag at each comma and refuses a value that one of the
    expressions matches anywhere (`regexp.MatchString` of Go). These expressions read the same in
    Go and in Python."""
    return any(re.search(expression, value) for expression in flag.split(","))


def test_the_proxy_refuses_every_method_that_writes_and_every_path_past_the_api_server(
    kube_tree: Path, bwrap: Path, user_kubeconfig: Path, process_fake: ProcessFake
) -> None:
    """The filters that the run gives `kubectl proxy` refuse each method that changes a resource
    and each path that reaches a process, a port or a server behind the API server. They let
    through each method and path that Popeye reads with."""
    SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap)).run(
        _request(kube_tree, network=KubeApiNetwork())
    )

    host, _sandbox = _split(_kube_api_run(process_fake), bwrap)
    methods, paths = host[8], host[9]
    assert (
        {method: _refused(methods, method) for method in (*_READ_METHODS, *_WRITE_METHODS)},
        {path: _refused(paths, path) for path in (*_READ_PATHS, *_PATHS_PAST_THE_API_SERVER)},
    ) == (
        {**dict.fromkeys(_READ_METHODS, False), **dict.fromkeys(_WRITE_METHODS, True)},
        {**dict.fromkeys(_READ_PATHS, False), **dict.fromkeys(_PATHS_PAST_THE_API_SERVER, True)},
    )


@pytest.mark.parametrize(("context", "expected_context"), [(None, "example"), ("other", "other")])
def test_the_relay_kubeconfig_names_the_loopback_port_and_the_context_with_no_credentials(
    kube_tree: Path,
    bwrap: Path,
    user_kubeconfig: Path,
    process_fake: ProcessFake,
    context: str | None,
    expected_context: str,
) -> None:
    """During the run, the kubeconfig of the sandbox names the relay on the loopback port and the
    context of the request, else the active context, with no credentials. It names no namespace:
    Popeye gets `-n <namespace>` or `-A`, so the namespace of the context has no effect (#2436).
    The proxy gets the same context. After the run, the scratch directory does not exist."""
    seen: dict[str, Any] = {}

    def read_kubeconfig(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        seen.update(json.loads((Path(call.argv[4]).parent / "kubeconfig.json").read_text()))
        return subprocess.CompletedProcess(list(call.argv), 0, "{}", "")

    process_fake.answer(
        lambda call: call.argv[0] == shutil.which("sh"),
        ProcessAnswer(side_effect=read_kubeconfig),
    )
    SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap)).run(
        _request(kube_tree, network=KubeApiNetwork(context=context))
    )

    host, _sandbox = _split(_kube_api_run(process_fake), bwrap)
    assert (seen, host[7], Path(host[4]).parent.exists()) == (
        {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [
                {"name": expected_context, "cluster": {"server": "http://127.0.0.1:8001"}}
            ],
            "contexts": [
                {
                    "name": expected_context,
                    "context": {"cluster": expected_context, "user": expected_context},
                }
            ],
            "users": [{"name": expected_context, "user": {}}],
            "current-context": expected_context,
        },
        expected_context,
        False,
    )


@pytest.mark.parametrize(
    ("context", "cause"),
    [
        ("missing", "error: cannot locate context missing"),
        (None, "error: current-context must exist in order to minify"),
    ],
)
def test_a_context_that_the_kubeconfig_does_not_have_starts_nothing(
    kube_tree: Path, bwrap: Path, process_fake: ProcessFake, context: str | None, cause: str
) -> None:
    """A context that the kubeconfig of the user does not have, or no kubeconfig, stops the run
    after kubectl reads the kubeconfig, before the proxy, the sandbox or the tool starts."""
    process_fake.answer(_is_config_view, ProcessAnswer(returncode=1, stderr=f"{cause}\n"))
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))

    with pytest.raises(SandboxError, match=cause):
        executor.run(_request(kube_tree, network=KubeApiNetwork(context=context)))

    assert [_is_config_view(call) for call in process_fake.calls] == [True]


@pytest.mark.parametrize("program", ["sh", "socat", "kubectl", "setpriv"])
def test_a_host_without_a_program_of_the_relay_runs_no_kube_api_request(
    kube_tree: Path,
    bwrap: Path,
    user_kubeconfig: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    program: str,
) -> None:
    """A host without one of the programs of the relay runs no kube-api request, and the cause
    names the program. The executor can still run the tools that need no network."""
    which = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda name, *a, **k: None if name == program else which(name, *a, **k)
    )
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))

    with pytest.raises(SandboxUnavailableError, match=program):
        executor.run(_request(kube_tree, network=KubeApiNetwork()))

    assert (process_fake.calls, executor.refusal) == ([], None)


def test_the_sandbox_binds_the_user_database_for_popeye_only(
    kube_tree: Path, bwrap: Path, process_fake: ProcessFake
) -> None:
    """Popeye stops at start when it cannot find the user, so the sandbox binds `/etc/passwd`
    read-only for Popeye, and not for another tool."""
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))

    popeye = _binds(executor.command(_request(kube_tree)))
    gitleaks = _binds(executor.command(_request(kube_tree, "gitleaks")))

    passwd = ["--ro-bind", "/etc/passwd", "/etc/passwd"]
    assert (passwd in popeye, passwd in gitleaks) == (True, False)
