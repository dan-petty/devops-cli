"""The `kube-api` network profile of the tool sandbox: only Popeye selects it, a run with it reaches
the Kubernetes API server only through `kubectl proxy` and `socat`, and the record of each run
names the network of the tool (#2132).

These cases fake the process edge with `process_fake`, so no sandbox, proxy or tool starts. The
fake finds each program that a run looks for at `/usr/local/bin/<name>`. The executor gets a
`HostSandbox` with a stand-in for bubblewrap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.exceptions.sandbox import SandboxError
from devops_cli.sandbox.host import HostSandbox
from devops_cli.security.registry import ScannerRegistry
from devops_cli.security.tool_executor import (
    DirectToolExecutor,
    KubeApiNetwork,
    SandboxToolExecutor,
    ToolRequest,
)
from tests.support.fakes.process import ProcessFake

# The kubeconfig of the user: the active context `example`, and the context `other`. Each names a
# cluster at a documentation address and a user with a token.
_USER_KUBECONFIG = """\
apiVersion: v1
kind: Config
current-context: example
clusters:
- name: example
  cluster: {server: "https://192.0.2.10:6443"}
- name: other
  cluster: {server: "https://192.0.2.20:6443"}
contexts:
- name: example
  context: {cluster: example, user: example, namespace: apps}
- name: other
  context: {cluster: other, user: other, namespace: tools}
users:
- name: example
  user: {token: example-token}
- name: other
  user: {token: other-token}
"""


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
def tree(tmp_path: Path) -> Path:
    """An empty tree outside any checkout, as Popeye scans."""
    root = (tmp_path / "tree").resolve()
    root.mkdir()
    return root


@pytest.fixture
def user_kubeconfig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The kubeconfig of the user, which `KUBECONFIG` names."""
    path = tmp_path / "kube" / "config"
    path.parent.mkdir()
    path.write_text(_USER_KUBECONFIG, encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(path))
    return path


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
    """The command of the one run after the check of the host."""
    _check, run = (call.argv for call in process_fake.calls)
    return run


def test_no_other_scanner_can_select_the_kube_api_network_profile(tree: Path) -> None:
    """A request for the tool of each scanner other than Popeye that selects the profile is
    refused. A request for Popeye that selects it is accepted."""
    others = sorted(tool for name, tool in _scanner_tools().items() if name != "popeye")
    refused = []
    for tool in others:
        with pytest.raises(ValidationError, match="kube-api"):
            _request(tree, tool, network=KubeApiNetwork())
        refused.append(tool)

    accepted = _request(tree, network=KubeApiNetwork(context="example"))

    assert (len(refused), refused == others, accepted.network) == (
        len(_scanner_tools()) - 1,
        True,
        KubeApiNetwork(context="example"),
    )


def test_a_popeye_request_from_another_program_cannot_select_the_profile(
    tree: Path, tmp_path: Path
) -> None:
    """A program can start another binary under the name of Popeye, so a request that names one
    cannot select the profile."""
    program = _stand_in(tmp_path / "elsewhere" / "popeye")

    with pytest.raises(ValidationError, match="program"):
        _request(tree, program=program, network=KubeApiNetwork())


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


def test_the_direct_executor_runs_no_network_profile(tree: Path, process_fake: ProcessFake) -> None:
    """The direct executor gives a tool the whole network of the host, so it refuses a request
    that selects a profile, and starts nothing."""
    with pytest.raises(SandboxError, match="kube-api"):
        DirectToolExecutor().run(_request(tree, network=KubeApiNetwork()))

    assert process_fake.calls == []


def test_the_record_of_a_run_names_the_network_of_the_tool(
    tree: Path, bwrap: Path, user_kubeconfig: Path, process_fake: ProcessFake
) -> None:
    """The direct executor gives a tool the network of the host, the sandbox gives it none, and
    the sandbox with the profile gives Popeye the profile."""
    direct = DirectToolExecutor().run(_request(tree, "gitleaks"))
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))
    sandbox = executor.run(_request(tree, "gitleaks"))
    kube_api = executor.run(_request(tree, network=KubeApiNetwork()))

    assert (direct.run.network, sandbox.run.network, kube_api.run.network) == (
        "host",
        "none",
        "kube-api",
    )
