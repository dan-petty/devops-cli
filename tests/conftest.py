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
import functools
import ipaddress
import json
import socket
import subprocess
import sys
import threading
import weakref
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn
from unittest.mock import patch

import pytest
import typer.rich_utils

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger
    from devops_cli.review.session import ReviewSessionStore
    from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
    from devops_cli.roadmap.store import RoadmapStore
    from tests.support.fakes.model import ModelFake
    from tests.web_fakes import StubWeb

pytest.register_assert_rewrite("tests.support")

pytest_plugins = ("tests.support.bootstrap",)


@pytest.fixture(autouse=True, scope="session")
def isolate_kubeconfig(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point KUBECONFIG at a throwaway file for the whole run.

    `KubernetesService.switch_context` rewrites the kubeconfig on disk, so a test that
    exercises context switching without mocking it silently repoints the developer's real
    kubectl at another cluster -- which is exactly what was happening. Isolating the path
    once, for every test, removes the possibility rather than relying on each test to
    remember to mock it.
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
    "devops_cli.ai.client.factory": ("reset_llm_client_override",),
    "devops_cli.ai.client.network": ("reset_ollama_slots",),
    "devops_cli.ai.context_budget": ("reset_tiktoken_encoding_cache",),
    "devops_cli.ai.gateway": ("clear_gateway_reasoning_cache",),
    "devops_cli.ai.kb": ("reset_uv_lock_cache",),
    "devops_cli.ai.mcp.dispatcher": ("reset_mcp_dispatcher",),
    "devops_cli.ai.mcp.generator": ("reset_click_command_cache",),
    "devops_cli.ai.mcp.server": ("reset_hydrated_domains",),
    "devops_cli.ai.personas": ("reset_persona_caches",),
    "devops_cli.ai.rag.embeddings": ("reset_model_dimension_cache",),
    "devops_cli.ai.rag.investigator": ("clear_investigation_cache",),
    "devops_cli.ai.rag.kb_sync": ("reset_kb_sync_state",),
    "devops_cli.ai.rag.retriever": ("reset_search_verified_models",),
    "devops_cli.ai.response_cache": ("reset_llm_response_cache",),
    "devops_cli.ai.spend.ledger": ("reset_spend_ledger",),
    "devops_cli.ai.spend.pricing": ("reset_pricing_registry",),
    "devops_cli.commands.vault": ("reset_lease_registry",),
    "devops_cli.config.metadata": ("reset_project_metadata_cache",),
    "devops_cli.config.settings": ("reset_settings_cache", "clear_ephemeral_ci_secrets"),
    "devops_cli.core.command_resolver": ("reset_command_resolver_cache",),
    "devops_cli.core.dns_names": ("reset_dns_names_cache",),
    "devops_cli.core.gitignore": ("reset_indexes",),
    "devops_cli.core.process": ("reset_github_token",),
    "devops_cli.core.repo": ("reset_repo_caches",),
    "devops_cli.core.templating": ("reset_template_environment_cache",),
    "devops_cli.core.untrusted_trees": ("reset_untrusted_trees",),
    "devops_cli.core.validation": ("reset_network_caches",),
    "devops_cli.docker.engine": ("DockerEngineService.reset_instance",),
    "devops_cli.dry_run.state": ("reset_dry_run_state",),
    "devops_cli.git.operations": ("reset_known_host_cache",),
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
    "devops_cli.telemetry.tracer": ("clear_span_buffer", "reset_tracer"),
    "devops_cli.tools_lock": ("reset_tools_lock_cache",),
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


def _started_words(args: Any) -> list[str]:
    """Return the tokenized argv words `subprocess.Popen(args)` starts."""
    if isinstance(args, (str, bytes, os.PathLike)):
        return os.fsdecode(args).split()
    return [os.fsdecode(word) for word in args] if args else []


def _started_program(args: Any) -> str:
    """The name of the program `subprocess.Popen(args)` starts: a command line's first word."""
    words = _started_words(args)
    return Path(words[0]).name if words else ""


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
    """Report whether `words` names an allowed process (`git`, `bwrap`, offline kubectl, or `@pytest.mark.live`)."""
    if not words:
        return True
    raw_program = words[0]
    program = Path(raw_program).name
    if program in {"git", "bwrap"}:
        return True
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
    real_init = subprocess.Popen.__init__

    def refusing_init(self: subprocess.Popen[Any], args: Any, *rest: Any, **kwargs: Any) -> None:
        words = _started_words(args)
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
    for marker in request.node.iter_markers("live"):
        for binary in marker.args:
            _register_live_binary(binary)
    for marker in request.node.iter_markers("unreachable"):
        for target in marker.args:
            _UNREACHABLE_TARGETS.add(str(target))
    yield
    _ALLOWED_LIVE_BINARIES.clear()
    _UNREACHABLE_TARGETS.clear()


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


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch) -> str:
    """Resolve every external hostname to one public address, for tests that validate egress.

    The session guard fails external lookups, so a test whose code checks that a URL resolves
    to a public address declares this fixture instead of depending on real DNS.
    """
    import socket

    address = "93.184.215.14"
    guarded = socket.getaddrinfo

    def resolve(host, port, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else str(host)
        flags = kwargs.get("flags", args[2] if len(args) >= 3 else 0) or 0
        if (
            host is None
            or bool(flags & socket.AI_NUMERICHOST)
            or _is_loopback(name)
            or _is_numeric_host(host, _ORIG_GETADDRINFO)
        ):
            return guarded(host, port, *args, **kwargs)
        number = int(port) if isinstance(port, int) or str(port or "").isdigit() else 0
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, number),
            )
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    return address


@pytest.fixture
def stub_web(monkeypatch: pytest.MonkeyPatch, public_dns: str) -> Iterator[StubWeb]:
    """Answer every httpx2 client from canned pages, so a fetch never leaves the process.

    Clients keep the broker's own redirect limit and request hooks; only their transport is the
    stub's. They stay classes, so code that subclasses them or checks isinstance still works.
    External names resolve to a public address, as `public_dns` does.

    A canned page never reaches a connect, so a client the factory built at an egress level has
    each request's host vetted with `vet_addresses` at that level before the stub answers it, as
    its backend would before dialling.
    """
    import httpx2

    from devops_cli.http import broker
    from tests.web_fakes import StubWeb, egress_level_of, install_async_client_fake

    web = StubWeb()

    def stub_transport(factory_transport: Any) -> httpx2.MockTransport:
        return httpx2.MockTransport(web.vetting_handler(egress_level_of(factory_transport)))

    class StubClient(httpx2.Client):
        """An httpx2.Client whose transport is always the stub's."""

        def __init__(self, **kwargs: Any) -> None:
            transport = stub_transport(kwargs.get("transport"))
            super().__init__(**{**kwargs, "transport": transport})

    class StubAsyncClient(httpx2.AsyncClient):
        """An httpx2.AsyncClient whose transport is always the stub's."""

        fake_owner = "stub_web"

        def __init__(self, **kwargs: Any) -> None:
            transport = stub_transport(kwargs.get("transport"))
            super().__init__(**{**kwargs, "transport": transport})

    install_async_client_fake(monkeypatch, StubAsyncClient)
    monkeypatch.setattr(httpx2, "Client", StubClient)
    stub_broker = broker.HttpClientBroker()
    monkeypatch.setattr(broker, "DEFAULT_HTTP_BROKER", stub_broker)
    yield web
    stub_broker.close()


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
def isolate_llm_response_cache(tmp_path: Path):
    """Ensure LLM response cache is isolated per test to prevent cross-test cache hits."""
    from devops_cli.ai.response_cache import (
        get_llm_response_cache,
        reset_llm_response_cache,
    )

    reset_llm_response_cache()
    test_cache_dir = tmp_path / "test_llm_cache"
    get_llm_response_cache(cache_dir=test_cache_dir, enabled=True)
    yield
    reset_llm_response_cache()


@pytest.fixture
def spend_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SpendLedger:
    """A fresh ledger that every recorded call in the test writes to."""
    from devops_cli.ai.spend import ledger as ledger_module

    ledger = ledger_module.SpendLedger(db_path=tmp_path / "spend.db")
    monkeypatch.setattr(ledger_module, "_GLOBAL_LEDGER", ledger)
    return ledger


@pytest.fixture
def tracer(config: Callable[..., Path]) -> Iterator[Any]:
    """An enabled tracer with a clean span buffer and no trace context inherited from the run."""
    from devops_cli.config.constants import (
        CONST_TRACEPARENT_ENV_VAR,
        CONST_TRACEPARENT_HEADER,
    )
    from devops_cli.telemetry.tracer import clear_span_buffer, get_tracer, reset_tracer

    config(telemetry={"enabled": True})
    environment = dict(os.environ)
    environment.pop(CONST_TRACEPARENT_ENV_VAR, None)
    environment.pop(CONST_TRACEPARENT_HEADER, None)
    with patch.dict(os.environ, environment, clear=True):
        reset_tracer()
        clear_span_buffer()
        yield get_tracer()
        clear_span_buffer()
        reset_tracer()


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


@pytest.fixture
def review_store(isolate_data_dir: Path) -> type[ReviewSessionStore]:
    """The review session store, rooted in the test's own data directory with its root created
    (#771). Naming `ReviewSessionStore.root()` creates nothing, as a review that has not yet
    written a session finds it, so a test that lists or searches sessions asks for the store."""
    from devops_cli.review.session import ReviewSessionStore

    ReviewSessionStore.root().mkdir(parents=True)
    return ReviewSessionStore


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


@pytest.fixture(autouse=True)
def isolate_own_source_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test as a devops-cli installed in site-packages runs, trusting no repository as
    its own (#972). The suite imports devops-cli from the checkout it runs in, which would make
    that checkout trusted: a review started there would read its `config.yaml` and `.data`. A test
    of the trusted repository points `_own_source_dir` at a repository of its own."""
    import sysconfig

    installed = Path(sysconfig.get_paths()["purelib"]).resolve() / "devops_cli"
    monkeypatch.setattr("devops_cli.core.repo._own_source_dir", lambda: installed)


@pytest.fixture(autouse=True)
def isolate_session_bus(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Keep tests off the devcontainer's session bus, where gnome-keyring holds real secrets.

    The runtime directory sits beside `tmp_path`, neither holding it nor inside it: a sandbox
    never mounts a workspace that overlaps the runtime directory (#1115), and most sandbox tests
    mount `tmp_path`.
    """
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    # the bus fallback is $XDG_RUNTIME_DIR/bus
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path_factory.mktemp("run")))


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


@pytest.fixture
def model_fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModelFake]:
    """The model and embedding edge, faked for every AI client the test opens (ADR 0007, #1001).

    Installs an in-memory `ModelFake` into the client factory seam. Any client built by
    `get_llm_client` or `build_llm_client` routes to this fake, answering queued responses,
    matching route patterns, or returning deterministic embeddings without network calls.
    """
    from devops_cli.ai.client import factory
    from tests.support.fakes.model import ModelFake

    fake = ModelFake()
    monkeypatch.setattr(factory, "_client_override", fake)
    yield fake


@functools.lru_cache(maxsize=1)
def _load_recorded_canary_outputs() -> dict[str, Any]:
    """Load recorded canary outputs once per worker process for offline test isolation.

    They are read through the `tests` package, not `tests.support.paths`: a conftest that
    imported the paths would make every change to them reach every test (#1312).
    """
    recorded = files("tests").joinpath("fixtures", "review_canary", "recorded_outputs.json")
    data = json.loads(recorded.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _recorded_canary_subprocess(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Return the recorded canary output for `cmd` without spawning a real scanner binary."""
    bin_name = Path(cmd[0]).name
    tool_key = "mypy" if "-m" in cmd and "mypy" in cmd else bin_name
    entry = _load_recorded_canary_outputs().get(tool_key, {})
    out = entry.get("output", "") if isinstance(entry, dict) else ""
    stdout_str = out if isinstance(out, str) else json.dumps(out)
    return subprocess.CompletedProcess(cmd, 0, stdout_str, "")


@pytest.fixture(autouse=True)
def pin_review_tool_canaries(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Feed review tool canaries recorded outputs and clear the canary cache between tests (#1143)."""
    from devops_cli.review import canary as canary_module

    canary_module.clear_canary_cache()
    monkeypatch.setattr(canary_module, "run_subprocess", _recorded_canary_subprocess)
    yield
    canary_module.clear_canary_cache()


@pytest.fixture(autouse=True, scope="session")
def github_roadmap_factory() -> Iterator[Callable[..., RoadmapStore]]:
    """Keep every test off the GitHub roadmap store, and hand its real factory to its own test.

    The GitHub store runs `gh`, which in a test acts as the developer's own login: `run_gh` passes
    its child no `GH_CONFIG_DIR`, so `isolate_gh_config` does not reach it. For the whole run the
    factory refuses instead, and a test that drives a roadmap command requests `roadmap_store`.
    """
    from devops_cli.roadmap import store as roadmap_module

    factory = roadmap_module.get_roadmap_store

    def refuse(repo: str, **_: Any) -> NoReturn:
        raise AssertionError(
            f"A test opened the GitHub roadmap store for {repo}, which runs the developer's own "
            "gh login. Request the roadmap_store fixture instead."
        )

    with patch.object(roadmap_module, "get_roadmap_store", refuse):
        yield factory


@pytest.fixture
def roadmap_store_repos() -> list[str]:
    """The repository each roadmap store a command opened during the test was opened for."""
    return []


@pytest.fixture
def roadmap_store(
    monkeypatch: pytest.MonkeyPatch, roadmap_store_repos: list[str]
) -> InMemoryRoadmapStore:
    """The in-memory roadmap that every store a command opens during the test reads and writes.

    Each store a command opens adds its repository to `roadmap_store_repos`, so a test can pin
    which repository a command reads and writes.
    """
    from devops_cli.roadmap import store as roadmap_module
    from devops_cli.roadmap.memory_store import InMemoryRoadmapStore

    roadmap = InMemoryRoadmapStore()

    def open_store(repo: str, **_: Any) -> InMemoryRoadmapStore:
        roadmap_store_repos.append(repo)
        return roadmap

    monkeypatch.setattr(roadmap_module, "get_roadmap_store", open_store)
    return roadmap


@pytest.fixture
def unreadable_github_roadmap(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Open the GitHub store over a `gh` that exits 1, as when GitHub can't be read, and a
    session whose listings that `gh` answers.

    Returns the argv of every `gh` command the store ran and every listing it read.
    """
    from devops_cli.roadmap import store as roadmap_module
    from devops_cli.roadmap.github_store import GitHubRoadmapStore
    from tests.support.fakes.github import RunnerSession

    calls: list[list[str]] = []

    def gh_exits_1(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "HTTP 503: Service Unavailable")

    monkeypatch.setattr(
        roadmap_module,
        "get_roadmap_store",
        # A runner the command passes (intake's spend meter) is replaced by the failing `gh`.
        lambda repo, runner=None, **kwargs: GitHubRoadmapStore(
            repo, runner=gh_exits_1, **kwargs, session=RunnerSession(gh_exits_1)
        ),
    )
    return calls


@pytest.fixture(autouse=True)
def isolate_keyring_backends(deny_real_keyring: None) -> Iterator[None]:
    """Unregister the keyring backend classes a test defines and restore keyring's chosen backend,
    so no test's fake backend becomes a later test's keyring (`tests/keyring_isolation.py`)."""
    from tests.keyring_isolation import keyring_backends_restored

    with keyring_backends_restored():
        yield


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
        "ai:\n  allow_private_network: true\n  rag:\n    enabled: false\n"
        "qdrant:\n  url: http://localhost:6333\n"
        f"valkey:\n  host: {side_channel}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(test_config))
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", f"http://{side_channel}")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    yield test_config
    reset_settings_cache()
    reset_tracer()


def _deep_merge_config(base: dict[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge `updates` into a copy of `base`."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge_config(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


@pytest.fixture
def config(isolate_devops_cli_config: Path) -> Callable[..., Path]:
    """Write overrides into the per-test `config.yaml` and reset the settings cache (#1310)."""
    import yaml

    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.telemetry.tracer import reset_tracer

    def apply(overrides: Mapping[str, Any] | None = None, **sections: Any) -> Path:
        current = yaml.safe_load(isolate_devops_cli_config.read_text(encoding="utf-8")) or {}
        combined: dict[str, Any] = {}
        if overrides:
            combined = _deep_merge_config(combined, overrides)
        if sections:
            combined = _deep_merge_config(combined, sections)
        updated = _deep_merge_config(current, combined)
        isolate_devops_cli_config.write_text(
            yaml.safe_dump(updated, sort_keys=False), encoding="utf-8"
        )
        reset_settings_cache()
        reset_tracer()
        return isolate_devops_cli_config

    return apply


@pytest.fixture
def cli() -> Callable[..., Any]:
    """Run `devops <args>` in process through `devops_cli.main.app` with the floor's terminal settings (#1310)."""
    from typer.testing import CliRunner

    from devops_cli.main import app

    runner = CliRunner(env=_TERMINAL_ENV)

    def invoke(
        *args: str | Sequence[str],
        input: str | bytes | None = None,
        env: Mapping[str, str | None] | None = None,
        catch_exceptions: bool = True,
    ) -> Any:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            argv = [str(item) for item in args[0]]
        else:
            argv = [str(item) for item in args]
        merged_env = {**_TERMINAL_ENV, **(env or {})}
        return runner.invoke(
            app,
            argv,
            input=input,
            env=merged_env,
            catch_exceptions=catch_exceptions,
        )

    return invoke


@pytest.fixture
def git() -> Callable[..., None]:
    """Run `git -C <repo> <args>` with a throwaway identity; a git error fails the test.

    Tests that build real repositories and worktrees in `tmp_path` share it.
    """

    def run(repo: Path, *args: str) -> None:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@example.com",
                *args,
            ],
            check=True,
            capture_output=True,
        )

    return run


@pytest.fixture
def nested_worktree(tmp_path: Path, git: Callable[..., None]) -> tuple[Path, Path]:
    """A checkout and a linked worktree nested under its `.claude/worktrees/`, as Claude Code
    places them; the checkout ignores `.claude/`, and its pyproject enables only ruff's
    unused-import rule."""
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "--quiet")
    (main / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    git(main, "add", ".")
    git(main, "commit", "--quiet", "-m", "first")
    nested = main / ".claude" / "worktrees" / "wt"
    git(main, "worktree", "add", "--quiet", "-b", "nested", str(nested))
    return main, nested


@pytest.fixture
def symbol_removal_repo(tmp_path: Path, git: Callable[..., None]) -> Path:
    """A real repository whose `main` defines two functions and whose `feature` branch
    removes one of them and adds another."""
    git(tmp_path, "init", "--quiet", "-b", "main")
    (tmp_path / "mod.py").write_text("def kept(): pass\ndef gone(): pass\n", encoding="utf-8")
    git(tmp_path, "add", "mod.py")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    git(tmp_path, "switch", "--quiet", "-c", "feature")
    (tmp_path / "mod.py").write_text("def kept(): pass\ndef added(): pass\n", encoding="utf-8")
    git(tmp_path, "commit", "--quiet", "-am", "remove gone")
    return tmp_path


@pytest.fixture
def write_review_session() -> Callable[..., Path]:
    """Write a published review session as the pipeline lays one out: findings.json, plus
    candidates.json and a profile.json naming `target` when they are given.

    Review history, baseline and stats tests share it.
    """
    from devops_cli.ai.review.profile import ReviewProfile
    from devops_cli.ai.review_schema import ReviewSessionPayload
    from devops_cli.review.session import ReviewSession

    def write(
        session_dir: Path,
        *,
        generated_at: str,
        subject: dict[str, str] | None = None,
        findings: Sequence[Any] = (),
        candidates: Sequence[Any] | None = None,
        target: str | None = None,
    ) -> Path:
        session = ReviewSession(session_dir)

        def payload(saved: Sequence[Any]) -> ReviewSessionPayload:
            return ReviewSessionPayload(
                generated_at=generated_at, subject=subject or {}, findings=list(saved)
            )

        session.write_findings(payload(findings))
        if candidates is not None:
            session.write_raised(payload(candidates))
        if target is not None:
            session.write_profile(ReviewProfile(session_id=session_dir.name, target=target))
        return session.publish()

    return write


@pytest.fixture
def review_history(tmp_path: Path, write_review_session: Callable[..., Path]) -> Path:
    """A reviews directory with three sessions of one subject, a target-only session, an unkeyed
    session, and a directory without findings.json.

    `same-3` is the newest of the subject and counts. With it left out, `same-1`, whose finding
    has a verdict, outranks the newer `same-2`, whose finding has none. Each session reports one
    finding, so counting every session and counting each subject once give different tables.
    """
    from devops_cli.ai.review.history import review_subject
    from devops_cli.ai.review_schema import SavedFinding

    reviews = tmp_path / "reviews"
    subject = review_subject("path", "/repo/src", ["diff --git a/mod.py b/mod.py\n"])
    sessions = (
        ("same-1", "2026-10-01T09:00:00+00:00", subject, "VERIFIED", None),
        ("same-2", "2026-10-01T10:00:00+00:00", subject, "UNVERIFIED", None),
        ("same-3", "2026-10-01T11:00:00+00:00", subject, "VERIFIED", None),
        ("target-only", "2026-09-30T09:00:00+00:00", None, "INVALIDATED", "/repo/src"),
        ("unkeyed", "2026-09-29T09:00:00", None, "MITIGATED", None),
    )
    for name, generated_at, session_subject, status, target in sessions:
        finding = SavedFinding(
            title=f"{name} finding",
            location="mod.py:1",
            status=status,
            persona="devsecops",
        )
        write_review_session(
            reviews / name,
            generated_at=generated_at,
            subject=session_subject,
            findings=[finding],
            target=target,
        )
    (reviews / "incomplete" / "files").mkdir(parents=True)
    return reviews


@pytest.fixture
def mock_keyring():
    """Install a fresh in-memory FakeKeyring for the test (#1310)."""
    import keyring

    from tests.cluster_secret_fakes import FakeKeyring

    fake = FakeKeyring()
    keyring.set_keyring(fake)
    return fake


@contextmanager
def _patched_docker_engine(client: Any) -> Iterator[Any]:
    """Bind a mock Engine API client to an isolated DockerEngineService singleton."""
    from devops_cli.docker.engine import DockerEngineService

    engine = DockerEngineService()
    engine._client = client
    with patch.object(DockerEngineService, "get_instance", return_value=engine):
        yield engine


@pytest.fixture
def docker_engine():
    """Provide a factory binding mock Engine API clients to the Docker engine singleton."""
    return _patched_docker_engine


@pytest.fixture
def docker_endpoint_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unserved_side_channel_port: int
):
    """Provide an isolated environment for Docker endpoint resolution tests (#1108)."""
    import hashlib
    import json

    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.docker.engine import DockerEngineService

    monkeypatch.delenv("CONTAINER_HOST", raising=False)
    monkeypatch.delenv("CONTAINER_CONNECTION", raising=False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.delenv("DOCKER_TLS_VERIFY", raising=False)
    monkeypatch.delenv("DOCKER_CERT_PATH", raising=False)
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)

    fake_run_user = tmp_path / "run_user"
    fake_rootful = tmp_path / "run_podman" / "podman.sock"
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(fake_run_user))
    monkeypatch.setattr("devops_cli.docker.engine.CONST_RUN_USER_BASE", fake_run_user)
    monkeypatch.setattr("devops_cli.docker.engine.CONST_PODMAN_ROOTFUL_SOCKET_PATH", fake_rootful)

    endpoint_config = tmp_path / "devops_endpoint_config.yaml"
    endpoint_config.write_text(
        f"telemetry:\n  enabled: false\n  endpoint: http://127.0.0.1:{unserved_side_channel_port}\n"
        "ai:\n  allow_private_network: false\n  rag:\n    enabled: false\n"
        "qdrant:\n  url: http://localhost:6333\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(endpoint_config))
    reset_settings_cache()

    config_file = tmp_path / "config.json"
    config_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("DOCKER_CONFIG", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    DockerEngineService.reset_instance()

    def write_context(name: str, host: str, skip_tls_verify: bool = False) -> Path:
        name_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()
        meta_dir = tmp_path / "contexts" / "meta" / name_hash
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "Name": name,
            "Metadata": {},
            "Endpoints": {
                "docker": {
                    "Host": host,
                    "SkipTLSVerify": skip_tls_verify,
                }
            },
        }
        meta_path = meta_dir / "meta.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return meta_path

    write_context.tmp_path = tmp_path  # type: ignore[attr-defined]
    write_context.config_file = config_file  # type: ignore[attr-defined]
    write_context.write_context = write_context  # type: ignore[attr-defined]
    write_context.run_user_base = fake_run_user  # type: ignore[attr-defined]
    write_context.rootful_socket = fake_rootful  # type: ignore[attr-defined]
    yield write_context
    DockerEngineService.reset_instance()
    reset_settings_cache()


def pytest_configure(config: pytest.Config) -> None:
    """Register `pytester` so subpackage test modules such as `tests/invariants/` can use it."""
    if not config.pluginmanager.has_plugin("pytester"):
        config.pluginmanager.import_plugin("pytester")


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
    """Skip live bubblewrap and `@pytest.mark.live(...)` tests where the binary is not installed (#832, #1310, #1337)."""
    from devops_cli.sandbox.host import HostSandbox

    bwrap_available = HostSandbox().is_available()
    skip_bwrap = pytest.mark.skip(reason="bubblewrap is not installed")
    for item in items:
        if not bwrap_available and "bwrap" in item.keywords:
            item.add_marker(skip_bwrap)
        missing = _missing_live_binary(item)
        if missing is not None:
            item.add_marker(pytest.mark.skip(reason=f"{missing} is not installed"))
