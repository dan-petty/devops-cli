"""Shared test fixtures.

The one `pytest_plugins` entry, `tests.support.bootstrap`, isolates HOME and then registers every
submodule and subpackage of `tests.support` as a plugin (#1312). `tests.support` is marked for assertion
rewriting before that, and this module imports it only inside functions: a support module
imported earlier could not be rewritten, which `filterwarnings` turns into a failed run.
"""

from __future__ import annotations

import os

# OpenBLAS parks an idle thread per CPU in each process that loads numpy, against pids.max.
# pytest-randomly (`devops ci test --repeat`) loads numpy before this line, so that run keeps them.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
# Textual reads its animation level once, on import. Off, a tab switch moves its underline at once
# instead of over 0.3 s of frames that the pilot waits out after every key and pause (#1725).
os.environ["TEXTUAL_ANIMATIONS"] = "none"

import errno
import gc
import ipaddress
import socket
import subprocess
import sys
import tempfile
import threading
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NoReturn

import pytest
import typer.rich_utils

pytest.register_assert_rewrite("tests.support")

pytest_plugins = ("tests.support.bootstrap",)


@pytest.fixture(autouse=True, scope="session")
def isolate_kubeconfig(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point KUBECONFIG at a throwaway file for the whole run.

    A test whose code loads the kubeconfig, or runs a kubectl stand-in that edits it, reads
    and writes this file, never the developer's own. Isolating the path once, for every
    test, removes the possibility rather than relying on each test to remember it.
    """
    kubeconfig = tmp_path_factory.mktemp("kube") / "config"
    kubeconfig.write_text(
        "apiVersion: v1\n"
        "kind: Config\n"
        "clusters: []\n"
        "contexts: []\n"
        'current-context: ""\n'
        "preferences: {}\n"
        "users: []\n",
        encoding="utf-8",
    )
    previous = os.environ.get("KUBECONFIG")
    os.environ["KUBECONFIG"] = str(kubeconfig)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("KUBECONFIG", None)
        else:
            os.environ["KUBECONFIG"] = previous


_PROCESS_STATE_RESETS: dict[str, tuple[str, ...]] = {
    "devops_cli.ai.benchmark.document_chunker": ("reset_document_chunker_cache",),
    "devops_cli.ai.benchmark.embedding_tasks": ("reset_embedding_tasks_cache",),
    "devops_cli.ai.client.claude": ("reset_claude_model_capabilities",),
    "devops_cli.ai.client.factory": ("reset_llm_client_override",),
    "devops_cli.ai.client.network": ("reset_ollama_slots", "reset_model_call_limit"),
    "devops_cli.ai.context_budget": ("reset_tiktoken_encoding_cache",),
    "devops_cli.ai.gateway": ("clear_gateway_reasoning_cache",),
    "devops_cli.ai.kb": ("reset_uv_lock_cache",),
    "devops_cli.ai.mcp.dispatcher": ("reset_mcp_dispatcher",),
    "devops_cli.ai.mcp.generator": ("reset_click_command_cache",),
    "devops_cli.ai.mcp.server": ("reset_hydrated_domains",),
    "devops_cli.ai.personas": ("reset_persona_caches",),
    "devops_cli.ai.rag.embeddings": ("reset_model_dimension_cache", "reset_embedder"),
    "devops_cli.ai.rag.investigator": ("clear_investigation_cache",),
    "devops_cli.ai.rag.kb_sync": ("reset_kb_sync_state",),
    "devops_cli.ai.rag.qdrant": ("reset_qdrant_client",),
    "devops_cli.ai.rag.retriever": ("reset_search_verified_models",),
    "devops_cli.ai.response_cache": ("reset_llm_response_cache",),
    "devops_cli.ai.spend.ledger": ("reset_spend_ledger",),
    "devops_cli.ai.spend.pricing": ("reset_pricing_registry",),
    "devops_cli.security.vault_lease": ("reset_lease_registry",),
    "devops_cli.config.env": ("reset_declarations_cache",),
    "devops_cli.config.metadata": ("reset_project_metadata_cache",),
    "devops_cli.config.os_keyring": ("clear_remembered_secrets", "reset_keyring_edge"),
    "devops_cli.config.settings": ("reset_settings_cache",),
    "devops_cli.core.command_resolver": ("reset_command_resolver_cache",),
    "devops_cli.core.dns_names": ("reset_dns_names_cache",),
    "devops_cli.core.gitignore": ("reset_indexes",),
    "devops_cli.core.process": ("reset_github_token", "reset_process_runner"),
    "devops_cli.core.repo": ("reset_repo_caches",),
    "devops_cli.core.templating": ("reset_template_environment_cache",),
    "devops_cli.core.untrusted_trees": ("reset_untrusted_trees",),
    "devops_cli.core.validation": ("reset_network_caches",),
    "devops_cli.docker.engine": ("DockerEngineService.reset_instance",),
    "devops_cli.dry_run.state": ("reset_dry_run_state",),
    "devops_cli.git.operations": ("reset_known_host_cache",),
    "devops_cli.github.metrics": ("reset_sent_item_series", "reset_refused_paths"),
    "devops_cli.github.projects": ("reset_project_caches",),
    "devops_cli.github.rate_limiter": ("reset_github_rate_limiter",),
    "devops_cli.github.request_classifier": ("reset_request_classifier_cache",),
    "devops_cli.github.session": ("reset_github_session",),
    "devops_cli.http.broker": ("reset_broker",),
    "devops_cli.http.pool": ("close_shared_clients",),
    "devops_cli.k8s.context": ("reset_context_cache",),
    "devops_cli.k8s.gpu_matrix": ("reset_gpu_matrix_cache",),
    "devops_cli.k8s.port_forward_daemon": ("reset_daemon_manager",),
    "devops_cli.k8s.service": ("KubernetesService.reset_instance",),
    "devops_cli.k8s.service_proxy": ("reset_configuration_cache",),
    "devops_cli.main": ("reset_timing",),
    "devops_cli.output.console": ("reset_console",),
    "devops_cli.review.canary": ("clear_canary_cache",),
    "devops_cli.review.rules_pack": ("reset_rules_pack_cache",),
    "devops_cli.security.reference_extractor": ("reset_reference_extractor_caches",),
    "devops_cli.security.secrets": ("reset_resolver",),
    "devops_cli.telemetry.logfire": ("reset_logfire_bridge",),
    "devops_cli.telemetry.tracer": ("clear_span_buffer", "remove_exporter", "reset_tracer"),
    "devops_cli.tools_lock": ("reset_tools_lock_cache",),
    "devops_cli.valkey.cache": ("reset_shared_cache_tier",),
    "devops_cli.valkey.client": ("reset_valkey_client",),
}


def _reset_loaded_process_state() -> None:
    """Call the public reset of every loaded src module and close shared HTTP clients (#1310)."""
    for module_name, resets in _PROCESS_STATE_RESETS.items():
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for reset_spec in resets:
            target: Any = module
            for attr in reset_spec.split("."):
                target = getattr(target, attr, None)
                if target is None:
                    break
            if callable(target):
                target()


@pytest.fixture(autouse=True)
def reset_process_wide_state() -> Iterator[None]:
    """Reset all process-wide state in loaded src modules after every test (#1310).

    Defined first among function-scoped autouse fixtures so its teardown runs after monkeypatch
    has restored every patched attribute and environment variable.
    """
    yield
    _reset_loaded_process_state()


def _is_loopback(host: str) -> bool:
    """Report whether a connect or lookup names the loopback interface."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


_ORIG_GETADDRINFO = socket.getaddrinfo


def _is_numeric_host(host: Any, resolve: Callable[..., Any] = _ORIG_GETADDRINFO) -> bool:
    """Report whether a host is numeric in any spelling glibc accepts, which needs no DNS query.

    `2852039166` and `0xa9fea9fe` are 169.254.169.254 to glibc, so they resolve in tests as they
    do in production. `resolve` is the unguarded `socket.getaddrinfo`.
    """
    try:
        resolve(host, None, flags=socket.AI_NUMERICHOST)
    except OSError, UnicodeError:
        return False
    return True


# Unfaked edge reaches recorded during a test (`unexpected_loopback_connects` clears and fails
# the test at teardown, even when the code under test caught the raised error).
_UNEXPECTED_LOOPBACK_CONNECTS: list[str] = []
_ALLOWED_LIVE_BINARIES: set[str] = set()
_UNREACHABLE_TARGETS: set[str] = set()
# Whether the running test carries the `bwrap` mark, so it may start bubblewrap (#2096).
_BWRAP_TEST: list[bool] = [False]


def _matches_unreachable(host: str, port: int | None, unreachable: set[str]) -> bool:
    """Report whether `host` and `port` match an `@pytest.mark.unreachable(...)` declaration."""
    if not unreachable:
        return False
    candidates = {host}
    if port is None and "/" in host:
        candidates.add(Path(host).name)
    if _is_loopback(host):
        candidates.update({"localhost", "127.0.0.1", "::1"})
    if port is not None:
        candidates.update({f"{h}:{port}" for h in list(candidates)} | {f":{port}", str(port)})
    return bool(candidates & unreachable)


def _resolve_unix_socket_candidates(address: str | bytes | os.PathLike[Any]) -> set[str]:
    """Return raw and resolved string spellings for an AF_UNIX socket path."""
    raw = os.fsdecode(address)
    if not raw or raw.startswith("\x00"):
        return {raw} if raw else set()
    try:
        return {raw, str(Path(raw).resolve())}
    except OSError, RuntimeError:
        return {raw}


def _refuses_connect(
    address: Any, owned_ports: set[int], owned_unix_paths: set[str] | None = None
) -> bool:
    """Report whether the network guard refuses a connect, recording a refused loopback port;
    raise for a host that is not loopback or an unowned AF_UNIX socket."""
    if isinstance(address, (str, bytes, os.PathLike)):
        candidates = _resolve_unix_socket_candidates(address)
        if owned_unix_paths and (candidates & owned_unix_paths):
            return False
        unix_target = os.fsdecode(address)
        if _matches_unreachable(unix_target, None, _UNREACHABLE_TARGETS):
            return True
        msg = (
            f"network edge reached without a fake: unix:{unix_target} "
            f"(External network call blocked during test execution: {unix_target})"
        )
        _UNEXPECTED_LOOPBACK_CONNECTS.append(f"{msg} ({threading.current_thread().name})")
        raise RuntimeError(msg)
    if not (isinstance(address, tuple) and len(address) >= 2):
        return False
    host = str(address[0])
    port = int(address[1])
    if not _is_loopback(host):
        msg = (
            f"network edge reached without a fake: {host}:{port} "
            f"(External network call blocked during test execution: attempt to connect to {host}:{port}. "
            "All external APIs and endpoints must be mocked in tests.)"
        )
        if not _matches_unreachable(host, port, _UNREACHABLE_TARGETS):
            _UNEXPECTED_LOOPBACK_CONNECTS.append(f"{msg} ({threading.current_thread().name})")
        raise RuntimeError(msg)
    if port in owned_ports:
        return False
    if not _matches_unreachable(host, port, _UNREACHABLE_TARGETS):
        _UNEXPECTED_LOOPBACK_CONNECTS.append(f"{host}:{port} ({threading.current_thread().name})")
    return True


class _BoundPorts:
    """The ports and AF_UNIX paths sockets in this process bind, each owned while its socket is open.

    `listen` binds a socket that was not bound yet, to a port of the kernel's choosing. A closed
    socket reports fileno -1, and one that was collected has already left the weak mapping.
    """

    def __init__(self) -> None:
        self._ports: weakref.WeakKeyDictionary[socket.socket, int] = weakref.WeakKeyDictionary()
        self._unix_paths: weakref.WeakKeyDictionary[socket.socket, set[str]] = (
            weakref.WeakKeyDictionary()
        )
        self._lock = threading.RLock()

    def own(self, sock: socket.socket) -> None:
        """Own the port or AF_UNIX path `sock` is bound to."""
        try:
            name = sock.getsockname()
        except OSError:
            return
        if isinstance(name, tuple) and len(name) >= 2 and isinstance(name[1], int):
            with self._lock:
                self._ports[sock] = name[1]
        elif isinstance(name, (str, bytes)) and name:
            with self._lock:
                self._unix_paths[sock] = _resolve_unix_socket_candidates(name)

    def owned(self) -> set[int]:
        """The ports of the bound sockets still open."""
        with self._lock:
            return {port for sock, port in self._ports.items() if sock.fileno() != -1}

    def owned_unix(self) -> set[str]:
        """The AF_UNIX socket paths of the bound sockets still open."""
        with self._lock:
            paths: set[str] = set()
            for sock, sock_paths in self._unix_paths.items():
                if sock.fileno() != -1:
                    paths.update(sock_paths)
            return paths


_BOUND_PORTS = _BoundPorts()
_NETWORK_GUARD_INSTALLED = False
_PROCESS_GUARD_INSTALLED = False
_DENY_KEYRING_INSTANCE: Any = None


def _guarded_getaddrinfo(
    host: Any, orig_getaddrinfo: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    """Resolve numeric or loopback names and fail any external DNS lookup."""
    name = host.decode() if isinstance(host, bytes) else str(host)
    flags = kwargs.get("flags", args[4] if len(args) >= 5 else 0) or 0
    if (
        host is None
        or bool(flags & socket.AI_NUMERICHOST)
        or _is_loopback(name)
        or _is_numeric_host(host, orig_getaddrinfo)
    ):
        return orig_getaddrinfo(host, *args, **kwargs)
    msg = (
        f"network edge reached without a fake: dns:{name} "
        f"(External DNS lookup blocked during test execution: {name}. "
        "All external APIs and endpoints must be mocked in tests.)"
    )
    if not _matches_unreachable(name, None, _UNREACHABLE_TARGETS):
        _UNEXPECTED_LOOPBACK_CONNECTS.append(f"{msg} ({threading.current_thread().name})")
    raise socket.gaierror(socket.EAI_NONAME, msg)


def _install_network_guard() -> None:
    """Install socket connect/bind/listen/getaddrinfo guards once per process."""
    global _NETWORK_GUARD_INSTALLED
    if _NETWORK_GUARD_INSTALLED:
        return
    _NETWORK_GUARD_INSTALLED = True

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_bind = socket.socket.bind
    orig_listen = socket.socket.listen
    orig_getaddrinfo = socket.getaddrinfo

    def guarded_getaddrinfo(host, *args, **kwargs):
        return _guarded_getaddrinfo(host, orig_getaddrinfo, *args, **kwargs)

    def guarded_bind(self, address):
        orig_bind(self, address)
        _BOUND_PORTS.own(self)

    def guarded_listen(self, *args):
        orig_listen(self, *args)
        _BOUND_PORTS.own(self)

    def guarded_connect(self, address):
        if _refuses_connect(address, _BOUND_PORTS.owned(), _BOUND_PORTS.owned_unix()):
            raise ConnectionRefusedError(errno.ECONNREFUSED, os.strerror(errno.ECONNREFUSED))
        return orig_connect(self, address)

    def guarded_connect_ex(self, address):
        if _refuses_connect(address, _BOUND_PORTS.owned(), _BOUND_PORTS.owned_unix()):
            return errno.ECONNREFUSED
        return orig_connect_ex(self, address)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.socket.bind = guarded_bind
    socket.socket.listen = guarded_listen
    socket.getaddrinfo = guarded_getaddrinfo


@pytest.fixture(autouse=True, scope="session")
def prevent_external_network_calls() -> Iterator[None]:
    """Guarantee that tests never hit external APIs or endpoints, nor live services on loopback.

    A loopback connect reaches only a port a socket in this test process binds, and only while
    that socket is open: a server the test started, or `refusing_port`. Any other loopback port
    refuses, as if nothing listened there, so a `kubectl port-forward` or a daemon on the
    workstation is never reached and every machine takes CI's offline path, and the connect fails
    the test (`unexpected_loopback_connects`). Once a test closes its socket, the port refuses
    again, so whatever binds it next, such as another xdist worker or a port-forward, is not reached
    either. The refusal is the `ConnectionRefusedError` that clients already handle: a
    `RuntimeError` would escape them and send the test down a path no user reaches. Non-loopback
    connects and unowned AF_UNIX connects raise `RuntimeError`.

    The guard patches this process only. A subprocess a test spawns is not guarded, and a server
    a test starts in a subprocess is refused like any other port this process does not own.
    """
    _install_network_guard()
    yield
    if _UNEXPECTED_LOOPBACK_CONNECTS:
        late_reaches = ", ".join(_UNEXPECTED_LOOPBACK_CONNECTS)
        _UNEXPECTED_LOOPBACK_CONNECTS.clear()
        pytest.fail(f"Edge reached outside a test: {late_reaches}", pytrace=False)


def _is_allowed_kubectl_renderer(words: list[str]) -> bool:
    """Report whether `kubectl` argv invokes an offline renderer (`kustomize` or `patch --local`)."""
    if len(words) < 2:
        return False
    subcommand = words[1]
    if subcommand == "kustomize":
        return True
    if subcommand == "patch":
        return any(token == "--local" or token.startswith("--local=") for token in words[2:])
    return False


def _is_allowed_process(words: list[str]) -> bool:
    """Report whether `words` names an allowed process (`git`, `bwrap` in a `bwrap` test, offline kubectl, or `@pytest.mark.live`).

    A review runs its tools in the sandbox by default (#2096), so a real tool would start as the
    program that bubblewrap confines, where a refusal by its name does not see it. Bubblewrap
    therefore starts only in a test with the `bwrap` mark, which runs the real sandbox.
    """
    if not words:
        return True
    raw_program = words[0]
    program = Path(raw_program).name
    if program == "git":
        return True
    if program == "bwrap":
        return _BWRAP_TEST[0]
    if program in _ALLOWED_LIVE_BINARIES or raw_program in _ALLOWED_LIVE_BINARIES:
        return True
    return program == "kubectl" and _is_allowed_kubectl_renderer(words)


@pytest.fixture(autouse=True, scope="session")
def refuse_real_programs() -> None:
    """Deny any process other than git, bwrap, offline kubectl renderers, or `@pytest.mark.live` tools (#1310).

    The refusal sits on `subprocess.Popen`, beneath `run_subprocess`, `run_gh`, `subprocess.run`
    and asyncio's subprocesses, so a test that fakes any of those is untouched and only a program
    that would really start is refused. Every reach is recorded and raises `RuntimeError`, so a
    test whose code catches `Exception` still fails at teardown.
    """
    global _PROCESS_GUARD_INSTALLED
    if _PROCESS_GUARD_INSTALLED:
        return
    _PROCESS_GUARD_INSTALLED = True

    import platform

    platform.platform()
    from tests.support.started_programs import started_words

    real_init = subprocess.Popen.__init__

    def refusing_init(self: subprocess.Popen[Any], args: Any, *rest: Any, **kwargs: Any) -> None:
        words = started_words(args)
        if not _is_allowed_process(words):
            program = Path(words[0]).name if words else ""
            target = " ".join([program, *words[1:]])[:256]
            msg = (
                f"process edge reached without a fake: {target} "
                f"(A test started a real {program}: fake it through its seam or mark @pytest.mark.live)"
            )
            _UNEXPECTED_LOOPBACK_CONNECTS.append(msg)
            pytest.fail(msg, pytrace=False)
        real_init(self, args, *rest, **kwargs)

    # Installed for the rest of the process, as the network block is.
    setattr(subprocess.Popen, "__init__", refusing_init)


_HOST_PATH_GUARD_INSTALLED = False


def _is_denied_host_path(norm: str, raw: str) -> bool:
    """Report whether a path points to /proc or /usr/local/share/tiktoken (#2165)."""
    if norm == "/proc" or norm.startswith("/proc/"):
        return True
    if norm == "/usr/local/share/tiktoken" or norm.startswith("/usr/local/share/tiktoken/"):
        return True
    if raw.startswith("/proc") or raw.startswith("/usr/local/share/tiktoken"):
        return True
    return False


def _collect_allowed_host_roots() -> tuple[Path, ...]:
    """Collect the allowed repository, temporary, and interpreter directory roots (#2165)."""
    import sysconfig

    from tests.support.paths import REPO_ROOT

    allowed_roots: list[Path] = [
        REPO_ROOT.resolve(),
        Path(tempfile.gettempdir()).resolve(),
        Path(os.sep).joinpath("tmp").resolve(),
        Path(os.sep).joinpath("var", "tmp").resolve(),
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
        Path(sys.exec_prefix).resolve(),
        Path(sys.base_exec_prefix).resolve(),
        Path(sys.executable).resolve().parent,
    ]
    main_worktree = Path("/workspaces/devops-cli")
    if main_worktree.exists():
        allowed_roots.append(main_worktree.resolve())
    for p in sys.path:
        if p:
            try:
                allowed_roots.append(Path(p).resolve())
            except OSError:
                pass
    for path_name in ("stdlib", "purelib", "platlib", "data"):
        try:
            allowed_roots.append(Path(sysconfig.get_path(path_name)).resolve())
        except Exception:
            pass
    return tuple(dict.fromkeys(allowed_roots))


def _is_allowed_host_path(raw_path: str, unique_roots: tuple[Path, ...]) -> bool:
    """Check whether a path is allowed under the hermetic floor (#2165)."""
    if raw_path.startswith("/dev/"):
        return True
    if raw_path in (
        "/etc/ld.so.cache",
        "/etc/localtime",
        "/etc/os-release",
        "/etc/machine-id",
        "/var/lib/dbus/machine-id",
        "/usr/lib/os-release",
    ) or raw_path.startswith("/usr/share/zoneinfo"):
        return True
    if (
        raw_path.startswith(
            (
                "/bin/",
                "/usr/bin/",
                "/usr/local/bin/",
                "/sbin/",
                "/usr/sbin/",
                "/usr/lib",
                "/usr/local/lib",
                "/opt/lib",
                "/opt/scanners",
                "/usr/lib64",
                "/lib",
                "/lib64",
                "/usr/share",
            )
        )
        or "/site-packages" in raw_path
        or "/dist-packages" in raw_path
    ):
        return True

    try:
        resolved = Path(raw_path).resolve()
    except Exception:
        resolved = Path(os.path.abspath(raw_path))

    for root in unique_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            pass
    return False


def _install_host_path_guard() -> None:
    """Install file open guard to deny host paths outside repo, temp, and interpreter (#2165)."""
    global _HOST_PATH_GUARD_INSTALLED
    if _HOST_PATH_GUARD_INSTALLED:
        return
    _HOST_PATH_GUARD_INSTALLED = True

    import builtins
    import io

    unique_roots = _collect_allowed_host_roots()
    real_open = builtins.open

    def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(file, int):
            return real_open(file, *args, **kwargs)
        raw_path = os.fsdecode(file)
        if not raw_path:
            return real_open(file, *args, **kwargs)
        norm = os.path.normpath(raw_path)
        if _is_denied_host_path(norm, raw_path) or not _is_allowed_host_path(
            raw_path, unique_roots
        ):
            msg = f"host path reached without a fake: {raw_path}"
            _UNEXPECTED_LOOPBACK_CONNECTS.append(msg)
            pytest.fail(msg, pytrace=False)

        return real_open(file, *args, **kwargs)

    builtins.open = guarded_open
    io.open = guarded_open


@pytest.fixture(autouse=True, scope="session")
def refuse_host_paths() -> None:
    """Deny opening host paths outside tmp_path, repo root, and the interpreter (#2165)."""
    _install_host_path_guard()


def _raise_keyring_deny(service: str, username: str | None) -> NoReturn:
    """Record and raise an unfaked keyring edge reach."""
    target = f"{service}/{username}" if username is not None else service
    msg = f"keyring edge reached without a fake: {target}"
    _UNEXPECTED_LOOPBACK_CONNECTS.append(msg)
    raise RuntimeError(msg)


@pytest.fixture(autouse=True, scope="session")
def deny_real_keyring() -> None:
    """Install a default-deny keyring backend before the first test so backend discovery never runs (#1310)."""
    global _DENY_KEYRING_INSTANCE
    import keyring
    from keyring.backend import KeyringBackend

    if _DENY_KEYRING_INSTANCE is None:

        class _DenyKeyring(KeyringBackend):
            priority = 1

            def __init__(self) -> None:
                super().__init__()

            def get_password(self, service: str, username: str) -> str | None:
                _raise_keyring_deny(service, username)

            def set_password(self, service: str, username: str, password: str) -> None:
                _raise_keyring_deny(service, username)

            def delete_password(self, service: str, username: str) -> None:
                _raise_keyring_deny(service, username)

            def get_credential(self, service: str, username: str | None) -> Any:
                _raise_keyring_deny(service, username)

        _DENY_KEYRING_INSTANCE = _DenyKeyring()

    keyring.set_keyring(_DENY_KEYRING_INSTANCE)


def _register_live_binary(raw_binary: Any) -> None:
    """Register a `@pytest.mark.live` binary name and any Python interpreter aliases."""
    binary = str(raw_binary)
    name = Path(binary).name
    _ALLOWED_LIVE_BINARIES.update({binary, name})
    if name in {"python", "python3"}:
        _ALLOWED_LIVE_BINARIES.update(
            {"python", "python3", sys.executable, Path(sys.executable).name}
        )


@pytest.fixture(autouse=True)
def configure_edge_markers(request: pytest.FixtureRequest) -> Iterator[None]:
    """Populate `_ALLOWED_LIVE_BINARIES` and `_UNREACHABLE_TARGETS` from the test's markers (#1310)."""
    _ALLOWED_LIVE_BINARIES.clear()
    _UNREACHABLE_TARGETS.clear()
    _BWRAP_TEST[0] = request.node.get_closest_marker("bwrap") is not None
    for marker in request.node.iter_markers("live"):
        for binary in marker.args:
            _register_live_binary(binary)
    for marker in request.node.iter_markers("unreachable"):
        for target in marker.args:
            _UNREACHABLE_TARGETS.add(str(target))
    yield
    _ALLOWED_LIVE_BINARIES.clear()
    _UNREACHABLE_TARGETS.clear()
    _BWRAP_TEST[0] = False


@pytest.fixture(autouse=True)
def unexpected_loopback_connects() -> Iterator[list[str]]:
    """Fail a test that reached a process, network, or keyring edge without a fake (#1310).

    The guard refuses such a reach and records it; the record fails the test here even when the
    code under test swallowed the error. A test of the guard itself reads its reaches from this
    list and clears it.
    """
    yield _UNEXPECTED_LOOPBACK_CONNECTS
    reached = list(_UNEXPECTED_LOOPBACK_CONNECTS)
    _UNEXPECTED_LOOPBACK_CONNECTS.clear()
    if reached:
        pytest.fail(
            "network edge reached without a fake — Connected to a loopback port no socket in this "
            f"test process binds or reached an unfaked edge: {', '.join(reached)}. "
            "Fake the service at its edge, or refuse it through `refusing_port`.",
            pytrace=False,
        )


@contextmanager
def _bound_refusing_socket() -> Iterator[int]:
    """Bind a loopback port and never listen on it, so the kernel refuses every connect to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        yield sock.getsockname()[1]


@pytest.fixture
def refusing_port(prevent_external_network_calls: None) -> Iterator[int]:
    """A loopback port whose every connect is refused: the double of a service that is down.

    The test binds it, so the network guard lets connects through and the kernel refuses them.
    """
    with _bound_refusing_socket() as port:
        yield port


@pytest.fixture(scope="session")
def unserved_side_channel_port(prevent_external_network_calls: None) -> Iterator[int]:
    """The refusing port the floor's config names for telemetry export and the Valkey cache.

    Both are best-effort side channels the code under test survives without, and every test
    reaches them, so the floor binds one port for the run that refuses them as an unserved
    workstation does. A test that checks either channel installs its own double.
    """
    with _bound_refusing_socket() as port:
        yield port


# Rich reads COLUMNS once, when a console is built, and `devops_cli.output.console` caches one per
# process. Set the terminal before any test module is imported, so a console built during
# collection is not left at the 80-column non-terminal default for its whole xdist worker.
_TERMINAL_ENV = {"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"}
os.environ.update(_TERMINAL_ENV)

# Typer forces a terminal when GITHUB_ACTIONS, FORCE_COLOR or PY_COLORS is set, which under TERM=dumb
# causes Rich to report an 80x25 terminal size and ignore COLUMNS. Clear FORCE_TERMINAL so test
# consoles always honour COLUMNS in every environment (#1041).
typer.rich_utils.FORCE_TERMINAL = None


@pytest.fixture(autouse=True)
def preserve_cwd():
    """Ensure working directory is always restored to repository root after each test."""
    orig_cwd = os.getcwd()
    try:
        yield
    finally:
        try:
            os.chdir(orig_cwd)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def reset_dry_run_state():
    """Clear dry-run state and give each test a freshly built, standard-width console."""
    import devops_cli.dry_run.state as dry_run_state
    import devops_cli.output.console as console_module

    typer.rich_utils.FORCE_TERMINAL = None
    os.environ.update(_TERMINAL_ENV)
    os.environ.pop("DEVOPS_CLI_DRY_RUN", None)
    dry_run_state.reset_dry_run_state()
    console_module.reset_console()
    yield
    os.environ.pop("DEVOPS_CLI_DRY_RUN", None)
    dry_run_state.reset_dry_run_state()


@pytest.fixture(autouse=True)
def isolate_llm_response_cache(isolate_data_dir: Path):
    """Ensure LLM response cache is isolated per test to prevent cross-test cache hits.

    The cache is built on first use, from the settings the test has by then: building it here
    would load and validate the settings for each of the 13,000 tests, and most never use it.
    """
    from devops_cli.ai.response_cache import reset_llm_response_cache

    reset_llm_response_cache()
    yield
    reset_llm_response_cache()


@pytest.fixture(autouse=True)
def isolate_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Ensure tests run against an isolated temporary .data/ directory to protect user reviews."""
    from devops_cli.config.settings import reset_settings_cache

    reset_settings_cache()
    test_data_dir = (tmp_path / ".data").resolve()
    test_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(test_data_dir))
    yield test_data_dir
    reset_settings_cache()


@pytest.fixture(autouse=True)
def isolate_user_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the user-level data root, where a review's relative data paths resolve (#972) and
    locked tools install (#1142), in the test's temporary directory rather than the developer's
    home (#1311)."""
    user_data_root = (tmp_path / "user-data").resolve()
    monkeypatch.setenv("DEVOPS_CLI_USER_DATA_ROOT", str(user_data_root))
    return user_data_root


@pytest.fixture(autouse=True)
def isolate_tempdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Ensure tempfile.gettempdir() returns a directory under tmp_path for each test (#1311)."""
    import tempfile

    test_temp_str = str(tmp_path)
    monkeypatch.setenv("TMPDIR", test_temp_str)
    monkeypatch.setenv("TEMP", test_temp_str)
    monkeypatch.setenv("TMP", test_temp_str)
    prev_tempdir = tempfile.tempdir
    tempfile.tempdir = test_temp_str
    try:
        yield tmp_path
    finally:
        tempfile.tempdir = prev_tempdir


@pytest.fixture(scope="session")
def _hermetic_floor_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session temporary directory holding floor double files outside test tmp_path (#2165)."""
    floor_dir = tmp_path_factory.mktemp("hermetic_floor")
    (floor_dir / "tiktoken_cache").mkdir(parents=True, exist_ok=True)
    mounts_file = floor_dir / "proc_mounts"
    mounts_file.write_text("/dev/root / ext4 rw,relatime 0 0\n", encoding="utf-8")
    proc_root = floor_dir / "proc"
    proc_root.mkdir(parents=True, exist_ok=True)
    self_dir = proc_root / "self"
    self_dir.mkdir(parents=True, exist_ok=True)
    dummy_stat = b"1 (python3) R 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 1000 0 0 0\n"
    (self_dir / "stat").write_bytes(dummy_stat)
    return floor_dir


@pytest.fixture(autouse=True)
def isolate_tiktoken_cache(_hermetic_floor_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ensure tests see an empty tokenizer cache by default (#2165)."""
    cache_dir = _hermetic_floor_dir / "tiktoken_cache"
    cache_str = str(cache_dir)
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", cache_str)
    monkeypatch.setenv("DATA_GYM_CACHE_DIR", cache_str)
    return cache_dir


@pytest.fixture(autouse=True)
def isolate_proc_mounts(_hermetic_floor_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ensure tests see an isolated mounts table rather than /proc/mounts (#2165)."""
    mounts_file = _hermetic_floor_dir / "proc_mounts"
    import devops_cli.ci.diagnostics as diag

    monkeypatch.setattr(diag, "_PROC_MOUNTS", mounts_file)
    return mounts_file


@pytest.fixture(autouse=True)
def isolate_proc_root(_hermetic_floor_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ensure tests see an isolated process table rather than host /proc (#2165)."""
    proc_root = _hermetic_floor_dir / "proc"
    import devops_cli.k8s.port_forward_daemon as pfd

    real_process_start_ticks = pfd.process_start_ticks

    def floor_process_start_ticks(pid: int) -> int | None:
        if not (pfd._PROC_ROOT / "self" / "stat").is_file():
            return None
        try:
            os.kill(pid, 0)
        except OSError:
            stat_file = pfd._PROC_ROOT / str(pid) / "stat"
            if stat_file.is_file():
                stat_file.unlink(missing_ok=True)
            return None

        stat_file = pfd._PROC_ROOT / str(pid) / "stat"
        if not stat_file.is_file():
            pid_dir = pfd._PROC_ROOT / str(pid)
            pid_dir.mkdir(parents=True, exist_ok=True)
            dummy_stat = (
                f"{pid} (proc) R 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 1000 0 0 0\n"
            ).encode()
            (pid_dir / "stat").write_bytes(dummy_stat)
        return real_process_start_ticks(pid)

    monkeypatch.setattr(pfd, "_PROC_ROOT", proc_root)
    monkeypatch.setattr(pfd, "process_start_ticks", floor_process_start_ticks)
    import devops_cli.k8s.tunnel as tunnel_mod

    monkeypatch.setattr(tunnel_mod, "process_start_ticks", floor_process_start_ticks)
    return proc_root


@pytest.fixture(autouse=True)
def isolate_end_leftover_processes(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Ensure non-live tests do not read host /proc to find leftover processes (#2165)."""
    if "live" in request.keywords:
        return
    import devops_cli.core.process_hardening as ph
    import devops_cli.roadmap.implement_step as implement_step

    monkeypatch.setattr(ph, "end_leftover_processes", lambda timeout=0.0: None)
    monkeypatch.setattr(implement_step, "end_leftover_processes", lambda timeout=0.0: None)


@pytest.fixture(autouse=True)
def isolate_own_source_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test as a devops-cli installed in site-packages runs, trusting no repository as
    its own (#972). The suite imports devops-cli from the checkout it runs in, which would make
    that checkout trusted: a review started there would read its `config.yaml` and `.data`. A test
    of the trusted repository points `_own_source_dir` at a repository of its own."""
    import sysconfig

    installed = Path(sysconfig.get_paths()["purelib"]).resolve() / "devops_cli"
    monkeypatch.setattr("devops_cli.core.repo._own_source_dir", lambda: installed)


@pytest.fixture(scope="session")
def runtime_dirs_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The one directory of the worker that holds the runtime directory of each test.

    `mktemp` with a number scans every entry of the base directory to find the next number, so a
    numbered directory for each of the worker's 3,500 tests made each one slower than the last.
    The runtime directories are made inside this one, by `mkdtemp`, which scans nothing.
    """
    return tmp_path_factory.mktemp("runtime", numbered=False)


@pytest.fixture(autouse=True)
def isolate_session_bus(runtime_dirs_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep tests off the devcontainer's session bus, where gnome-keyring holds real secrets.

    The runtime directory sits beside `tmp_path`, neither holding it nor inside it: a sandbox
    never mounts a workspace that overlaps the runtime directory (#1115), and most sandbox tests
    mount `tmp_path`.
    """
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    # the bus fallback is $XDG_RUNTIME_DIR/bus
    monkeypatch.setenv("XDG_RUNTIME_DIR", tempfile.mkdtemp(dir=runtime_dirs_root))


@pytest.fixture(autouse=True)
def isolate_docker_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests off the developer's own engine endpoint, which the sandbox workspace check
    reads to find the engine socket it refuses to mount (#1115). A test that needs `DOCKER_HOST`
    sets it."""
    monkeypatch.delenv("DOCKER_HOST", raising=False)


@pytest.fixture(autouse=True)
def isolate_ssh_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests off the developer's own SSH agent, whose directory the sandbox workspace check
    refuses to mount (#1384). A test that needs `SSH_AUTH_SOCK` sets it."""
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)


@pytest.fixture(autouse=True)
def isolate_gh_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep tests from reading the developer's gh login, which may hold a plaintext token."""
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "gh-config"))


@pytest.fixture(autouse=True)
def pin_github_session(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Give every test one fake GitHub identity, so no test runs a real `gh auth token`.

    Every gh and git child a test starts gets `PINNED_GITHUB_TOKEN` as GH_TOKEN, never the
    developer's login. A test of the lookup itself sets `devops_cli.core.process._github_token`
    back to None, and `no_github_identity` makes every lookup fail. The session is dropped only
    once something has imported it: importing it here would load all of `devops_cli.github` in
    every worker.
    """
    from devops_cli.core import process
    from tests.support.github_identity import PINNED_GITHUB_TOKEN

    def drop_session() -> None:
        session_module = sys.modules.get("devops_cli.github.session")
        if session_module is not None:
            session_module.reset_github_session()

    drop_session()
    process.reset_github_token()
    monkeypatch.setattr(process, "_github_token", PINNED_GITHUB_TOKEN)
    yield PINNED_GITHUB_TOKEN
    drop_session()


@pytest.fixture(autouse=True)
def isolate_keyring_backends(deny_real_keyring: None) -> Iterator[None]:
    """Unregister the keyring backend classes a test defines and restore keyring's chosen backend,
    so no test's fake backend becomes a later test's keyring (`tests/keyring_isolation.py`)."""
    from tests.keyring_isolation import keyring_backends_restored

    with keyring_backends_restored():
        yield


class _DenyKeyringEdge:
    """The keyring edge of a test that installs no fake: every keyring and D-Bus reach fails."""

    def backend(self) -> Any:
        return _DENY_KEYRING_INSTANCE

    def session_bus_running(self, socket_path: Path) -> bool:
        _raise_keyring_deny("session-bus", str(socket_path))

    def default_collection_locked(self) -> bool | None:
        _raise_keyring_deny("secret-service", "default-collection")


@pytest.fixture(autouse=True)
def deny_keyring_edge(isolate_keyring_backends: None) -> None:
    """Install the deny edge through the keyring seam before each test (#1318).

    devops-cli reaches the keyring and the Secret Service only through
    `devops_cli.config.os_keyring`, so this edge refuses each of its reaches, D-Bus included;
    `keyring_store` replaces it for a test. The deny backend that `deny_real_keyring` gives the
    `keyring` library stays for third-party code, such as fastmcp's key-value store, that calls
    the library itself. The floor resets the edge after the test.
    """
    from devops_cli.config.os_keyring import set_keyring_edge

    set_keyring_edge(_DenyKeyringEdge())


@pytest.fixture(autouse=True)
def isolate_devops_cli_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unserved_side_channel_port: int
) -> Iterator[Path]:
    """Ensure every test gets its own temporary config through DEVOPS_CLI_CONFIG.

    Telemetry export is off by default; when a test opts in through `config`, export goes to the
    floor's refusing port, as the Valkey cache does. Qdrant's address is one no test binds, so a
    test that reaches Qdrant without a double fails.
    """
    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.telemetry.tracer import reset_tracer

    reset_settings_cache()
    reset_tracer()
    test_config_dir = (tmp_path / ".test_config").resolve()
    test_config_dir.mkdir(parents=True, exist_ok=True)
    test_config = test_config_dir / "config.yaml"
    side_channel = f"127.0.0.1:{unserved_side_channel_port}"
    test_config.write_text(
        f"telemetry:\n  enabled: false\n  endpoint: http://{side_channel}\n"
        "tempo:\n  url: http://localhost:3200\n"
        "pyroscope:\n  url: http://localhost:4040\n"
        "ai:\n  allow_private_network: true\n  rag:\n    enabled: false\n"
        "  gateway_url: http://localhost:4000/v1\n"
        "  ollama_urls:\n    - http://localhost:11434\n"
        "qdrant:\n  url: http://localhost:6333\n"
        f"valkey:\n  url: valkey://{side_channel}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(test_config))
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", f"http://{side_channel}")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    yield test_config
    reset_settings_cache()
    reset_tracer()


# How long the floor waits for a worker that a dispatch timeout abandoned. A test releases its
# hung command at once, so a worker alive after this wait is a command the test never released.
_DISPATCH_WORKER_JOIN_SECONDS = 5.0


@pytest.fixture(autouse=True)
def finish_abandoned_dispatch_workers(isolate_devops_cli_config: Path) -> Iterator[None]:
    """Wait for the dispatch workers that a timeout abandoned, while the test's isolation holds (#2277).

    A dispatch that passes its timeout returns and leaves its worker running. When the worker ends
    its command it calls `get_tracer()`. After the floor has reset the tracer and restored the
    environment, that call builds a tracer from the real settings, which export to port 4318 from
    a `devops-otel` thread during whichever test runs next. Depending on `isolate_devops_cli_config`
    puts this teardown before the reset of that fixture and before the restore of the environment,
    so the worker ends against the isolated tracer.
    """
    yield
    from devops_cli.config.constants import CONST_MCP_DISPATCH_THREAD_NAME

    workers = [t for t in threading.enumerate() if t.name == CONST_MCP_DISPATCH_THREAD_NAME]
    for worker in workers:
        worker.join(timeout=_DISPATCH_WORKER_JOIN_SECONDS)
    if running := [w for w in workers if w.is_alive()]:
        pytest.fail(
            f"{len(running)} in-process dispatch worker(s) still running {_DISPATCH_WORKER_JOIN_SECONDS:g} "
            "seconds after the test ended. Release the command that the dispatch abandoned before "
            "the test returns.",
            pytrace=False,
        )


# The garbage collector runs a young collection after each 2,000 net allocations, and the heap of
# the imported libraries (pydantic models, Textual, the Kubernetes client) is large, so a full
# collection took 0.9 s. In a worker of the full run the collector ran 4,000 to 7,000 times for
# 22 to 37 s of its 260 s. A young threshold of 50,000 leaves 120 to 190 runs and 5 to 10 s of it
# (#2699). The cycles that the tests leave stay uncollected a little longer, which no test reads;
# a test that needs the collection calls `gc.collect()`.
GC_YOUNG_THRESHOLD = 50_000


def pytest_configure(config: pytest.Config) -> None:
    """Register `pytester` so subpackage test modules such as `tests/invariants/` can use it, and
    raise the collector's young threshold for this process."""
    if not config.pluginmanager.has_plugin("pytester"):
        config.pluginmanager.import_plugin("pytester")
    _, gen1, gen2 = gc.get_threshold()
    gc.set_threshold(GC_YOUNG_THRESHOLD, gen1, gen2)


def _missing_live_binary(item: pytest.Item) -> str | None:
    """Return the first `@pytest.mark.live` binary missing from PATH, or None."""
    import shutil

    for marker in item.iter_markers("live"):
        for raw_binary in marker.args:
            binary = str(raw_binary)
            if shutil.which(binary) is None and not Path(binary).is_file():
                return binary
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Opt-in live bubblewrap tests and skip live tests where the binary is not installed (#832, #1310, #2143, #2149)."""
    from devops_cli.sandbox.host import HostSandbox

    markexpr = config.getoption("-m", "")
    if "bwrap" not in markexpr:
        selected: list[pytest.Item] = []
        deselected: list[pytest.Item] = []
        for item in items:
            if "bwrap" in item.keywords:
                deselected.append(item)
            else:
                selected.append(item)
        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = selected
    else:
        bwrap_available = HostSandbox().is_available()
        skip_bwrap = pytest.mark.skip(reason="bubblewrap is not installed")
        for item in items:
            if not bwrap_available and "bwrap" in item.keywords:
                item.add_marker(skip_bwrap)

    for item in items:
        missing = _missing_live_binary(item)
        if missing is not None:
            item.add_marker(pytest.mark.skip(reason=f"{missing} is not installed"))
