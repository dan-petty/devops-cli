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
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn
from unittest.mock import MagicMock, patch

import pytest
import typer.rich_utils

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger
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


@pytest.fixture(autouse=True, scope="session")
def register_test_mock_provider():
    """Register test MockProvider for unit testing."""
    from devops_cli.ai.providers import register_provider
    from tests.mock_provider import MockProvider

    register_provider("mock", MockProvider)


@pytest.fixture(autouse=True)
def reset_rag_state_per_test() -> Iterator[None]:
    """Ensure every unit test starts and ends with clean RAG verified collection models, no
    cached investigation retriever, whose Qdrant client would carry one test's address into the
    next, and no knowledge-base check state, whose cooldown would let only the first test in a
    process to reach Qdrant make the check. A module no test has imported holds none of that
    state, so only the loaded ones are reset, and a test that never reaches RAG does not import
    it, with pydantic-ai behind it (#1735)."""
    resets = {
        "devops_cli.ai.rag.retriever": "reset_search_verified_models",
        "devops_cli.ai.rag.investigator": "clear_investigation_cache",
        "devops_cli.ai.rag.kb_sync": "reset_kb_sync_state",
    }

    def reset_loaded() -> None:
        for module_name, reset in resets.items():
            module = sys.modules.get(module_name)
            if module is not None:
                getattr(module, reset)()

    reset_loaded()
    yield
    reset_loaded()


def _is_loopback(host: str) -> bool:
    """Report whether a connect or lookup names the loopback interface."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_numeric_host(host: Any, resolve: Callable[..., Any]) -> bool:
    """Report whether a host is numeric in any spelling glibc accepts, which needs no DNS query.

    `2852039166` and `0xa9fea9fe` are 169.254.169.254 to glibc, so they resolve in tests as they
    do in production. `resolve` is the unguarded `socket.getaddrinfo`.
    """
    try:
        resolve(host, None, flags=socket.AI_NUMERICHOST)
    except OSError, UnicodeError:
        return False
    return True


# Loopback connects the network guard refused because no socket in this process binds the port,
# each as `host:port (thread)`, naming the thread, which may outlive its test.
# `unexpected_loopback_connects` fails the test that leaves any.
_UNEXPECTED_LOOPBACK_CONNECTS: list[str] = []


def _refuses_connect(address: Any, owned_ports: set[int]) -> bool:
    """Report whether the network guard refuses a connect, recording a refused loopback port;
    raise for a host that is not loopback."""
    if not (isinstance(address, tuple) and len(address) >= 2):
        return False
    host = str(address[0])
    if not _is_loopback(host):
        raise RuntimeError(
            f"External network call blocked during test execution: attempt to connect to {host}:{address[1]}. "
            "All external APIs and endpoints must be mocked in tests."
        )
    if address[1] in owned_ports:
        return False
    _UNEXPECTED_LOOPBACK_CONNECTS.append(f"{host}:{address[1]} ({threading.current_thread().name})")
    return True


class _BoundPorts:
    """The ports sockets in this process bind, each owned while its socket is open.

    `listen` binds a socket that was not bound yet, to a port of the kernel's choosing. A closed
    socket reports fileno -1, and one that was collected has already left the weak mapping.
    """

    def __init__(self) -> None:
        self._ports: weakref.WeakKeyDictionary[socket.socket, int] = weakref.WeakKeyDictionary()
        self._lock = threading.RLock()

    def own(self, sock: socket.socket) -> None:
        """Own the port `sock` is bound to, if it is an address family with ports."""
        name = sock.getsockname()
        if isinstance(name, tuple):
            with self._lock:
                self._ports[sock] = name[1]

    def owned(self) -> set[int]:
        """The ports of the bound sockets still open."""
        with self._lock:
            return {port for sock, port in self._ports.items() if sock.fileno() != -1}


@pytest.fixture(autouse=True, scope="session")
def prevent_external_network_calls() -> None:
    """Guarantee that tests never hit external APIs or endpoints, nor live services on loopback.

    A loopback connect reaches only a port a socket in this test process binds, and only while
    that socket is open: a server the test started, or `refusing_port`. Any other loopback port
    refuses, as if nothing listened there, so a `kubectl port-forward` or a daemon on the
    workstation is never reached and every machine takes CI's offline path, and the connect fails
    the test (`unexpected_loopback_connects`). Once a test closes its socket, the port refuses
    again, so whatever binds it next, such as another xdist worker or a port-forward, is not reached
    either. The refusal is the `ConnectionRefusedError` that clients already handle: a
    `RuntimeError` would escape them and send the test down a path no user reaches. Non-loopback
    connects raise `RuntimeError`.

    The guard patches this process only. A subprocess a test spawns is not guarded, and a server
    a test starts in a subprocess is refused like any other port this process does not own.
    """
    import socket

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_bind = socket.socket.bind
    orig_listen = socket.socket.listen
    orig_getaddrinfo = socket.getaddrinfo
    bound = _BoundPorts()

    # A blocked connect still pays for a real DNS query first. Fail external
    # names the way an unresolvable one does, so callers take their existing gaierror path at once.
    def guarded_getaddrinfo(host, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else str(host)
        flags = kwargs.get("flags", args[4] if len(args) >= 5 else 0) or 0
        if (
            host is None
            or bool(flags & socket.AI_NUMERICHOST)
            or _is_loopback(name)
            or _is_numeric_host(host, orig_getaddrinfo)
        ):
            return orig_getaddrinfo(host, *args, **kwargs)
        raise socket.gaierror(
            socket.EAI_NONAME,
            f"External DNS lookup blocked during test execution: {name}. "
            "All external APIs and endpoints must be mocked in tests.",
        )

    def guarded_bind(self, address):
        orig_bind(self, address)
        bound.own(self)

    def guarded_listen(self, *args):
        orig_listen(self, *args)
        bound.own(self)

    def guarded_connect(self, address):
        if _refuses_connect(address, bound.owned()):
            raise ConnectionRefusedError(errno.ECONNREFUSED, os.strerror(errno.ECONNREFUSED))
        return orig_connect(self, address)

    def guarded_connect_ex(self, address):
        if _refuses_connect(address, bound.owned()):
            return errno.ECONNREFUSED
        return orig_connect_ex(self, address)

    # Installed for the rest of the process, not undone at teardown: an export a test queued on a
    # worker thread, or one `atexit` flushes, still runs after the last fixture is torn down.
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.socket.bind = guarded_bind
    socket.socket.listen = guarded_listen
    socket.getaddrinfo = guarded_getaddrinfo


def _started_program(args: Any) -> str:
    """The name of the program `subprocess.Popen(args)` starts: a command line's first word."""
    if isinstance(args, (str, bytes, os.PathLike)):
        words = os.fsdecode(args).split(maxsplit=1)
    else:
        words = [os.fsdecode(args[0])] if args else []
    return Path(words[0]).name if words else ""


@pytest.fixture(autouse=True, scope="session")
def refuse_real_programs() -> None:
    """Fail any test that starts gh or a security scanner for real, before it starts.

    The names are `refused_programs()`'s (`tests/support/refused_programs.py`), read once from
    the scanner registry when the guard is installed. The refusal sits on `subprocess.Popen`,
    beneath `run_subprocess`, `run_gh`, `subprocess.run` and asyncio's subprocesses, so a test
    that fakes any of those is untouched and only a program that would really start is refused.
    It fails the test with `pytest.fail`, which no `except Exception` in the code under test can
    turn into a failed scan or a warning (#1666). #1310's hermetic floor, when it lands, refuses
    processes in general and replaces this guard.
    """
    from tests.support.refused_programs import refused_programs

    refused = refused_programs()
    real_init = subprocess.Popen.__init__

    def refusing_init(self: subprocess.Popen[Any], args: Any, *rest: Any, **kwargs: Any) -> None:
        program = _started_program(args)
        if program in refused:
            pytest.fail(
                f"A test started a real {program}, which no test may start (#1666): fake it "
                "through its seam, or with the recorded runs of `scanner_fake` for a scanner. "
                f"Command: {str(args)[:256]}"
            )
        real_init(self, args, *rest, **kwargs)

    # Installed for the rest of the process, as the network block is.
    subprocess.Popen.__init__ = refusing_init  # type: ignore[method-assign]


@pytest.fixture(autouse=True)
def unexpected_loopback_connects() -> Iterator[list[str]]:
    """Fail a test that connected to a loopback port no socket in this process binds.

    The guard refuses such a connect as a service that is down would, so the client takes its
    ordinary path, and records it; the record fails the test here even when the code under test
    swallowed the refusal. A test that reaches a service fakes it at its edge, and one that checks a
    refused service refuses it through `refusing_port`. A connect from a thread that outlived an
    earlier test is reported by the test running when it happens. A test of the guard itself reads
    its connects from this list and clears it.
    """
    yield _UNEXPECTED_LOOPBACK_CONNECTS
    reached = list(_UNEXPECTED_LOOPBACK_CONNECTS)
    _UNEXPECTED_LOOPBACK_CONNECTS.clear()
    if reached:
        pytest.fail(
            "Connected to a loopback port no socket in this test process binds: "
            f"{', '.join(reached)}. Fake the service at its edge, or refuse it through "
            "`refusing_port`.",
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
        try:
            return guarded(host, port, *args, **kwargs)
        except socket.gaierror:
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
    dry_run_state.mark_dry_run_invocation(False)
    console_module._CONSOLE = None
    console_module._STDERR_CONSOLE = None
    yield
    os.environ.pop("DEVOPS_CLI_DRY_RUN", None)
    dry_run_state.mark_dry_run_invocation(False)


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
def tracer() -> Iterator[Any]:
    """An enabled tracer with a clean span buffer and no trace context inherited from the run."""
    from devops_cli.config.constants import (
        CONST_TRACEPARENT_ENV_VAR,
        CONST_TRACEPARENT_HEADER,
    )
    from devops_cli.telemetry.tracer import clear_span_buffer, get_tracer, reset_tracer

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
def isolate_vault_token() -> Iterator[None]:
    """Keep a Vault token, or any other ephemeral CI secret, from outliving the test that left
    it (#709).

    Brokers read the `devops vault login` record from the in-process secret store, the
    process-wide resolver's `VaultProvider` keeps the broker it built, token and all, and `vault
    leases` keeps its session registry. Each would let a later test reach Vault with a token. The
    store is cleared in place, since tests hold the dict itself; the registry is dropped only once
    something has imported the command. Every secret in the store is cleared, not only the Vault
    record: in a serial run, a `DEVOPS_CLI_HEADLESS_AUTH` secret `test_config_commands` stored
    reached `test_embedding_benchmark` (#853, one slice of #1310).
    """
    yield
    from devops_cli.config.settings import _EPHEMERAL_CI_SECRETS
    from devops_cli.security.secrets import reset_resolver

    _EPHEMERAL_CI_SECRETS.clear()
    reset_resolver()
    vault_commands = sys.modules.get("devops_cli.commands.vault")
    if vault_commands is not None:
        vault_commands.reset_lease_registry()


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
    monkeypatch.setattr(process, "_github_token", PINNED_GITHUB_TOKEN)
    monkeypatch.setattr(process, "_github_lookup_failure", None)
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
def isolate_keyring_backends() -> Iterator[None]:
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

    Telemetry export and the Valkey cache go to the floor's refusing port. Qdrant's address is
    one no test binds, so a test that reaches Qdrant without a double fails.
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
        f"telemetry:\n  enabled: true\n  endpoint: http://{side_channel}\n"
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
    """Write a completed review session as the pipeline lays one out: findings.json, plus
    candidates.json and a profile.json naming `target` when they are given.

    Review history, baseline and stats tests share it.
    """
    from devops_cli.ai.review.profile import ReviewProfile
    from devops_cli.ai.review_schema import ReviewSessionPayload
    from devops_cli.config.constants import (
        CONST_REVIEW_CANDIDATES_FILENAME,
        CONST_REVIEW_FINDINGS_FILENAME,
    )

    def write(
        session_dir: Path,
        *,
        generated_at: str,
        subject: dict[str, str] | None = None,
        findings: Sequence[Any] = (),
        candidates: Sequence[Any] | None = None,
        target: str | None = None,
    ) -> Path:
        session_dir.mkdir(parents=True)
        files = (
            (CONST_REVIEW_FINDINGS_FILENAME, findings),
            (CONST_REVIEW_CANDIDATES_FILENAME, candidates),
        )
        for name, saved in files:
            if saved is not None:
                payload = ReviewSessionPayload(
                    generated_at=generated_at,
                    subject=subject or {},
                    findings=list(saved),
                )
                (session_dir / name).write_text(payload.model_dump_json(), encoding="utf-8")
        if target is not None:
            ReviewProfile(session_id=session_dir.name, target=target).write(session_dir)
        return session_dir

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
def tmp_ssh_dir(tmp_path: Path) -> Path:
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    return ssh_dir


@pytest.fixture
def tmp_repos_dir(tmp_path: Path) -> Path:
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    return repos_dir


@pytest.fixture
def mock_keyring():
    with (
        patch("keyring.get_password", return_value=None),
        patch("keyring.set_password"),
    ):
        yield


@pytest.fixture
def mock_settings(tmp_path: Path):
    settings = MagicMock()
    settings.repos.base_dir = tmp_path / "repos"
    settings.ssh.key_dir = tmp_path / ".ssh"
    settings.ssh.rotation_days = 90
    settings.workspace.file = tmp_path / ".code-workspace"
    settings.github.default_org = None
    settings.grafana.url = None
    settings.prometheus.url = None
    settings.argocd.url = None
    return settings


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


@pytest.fixture(autouse=True)
def reset_docker_engine_singleton():
    """Guarantee no Engine API socket connection leaks between tests."""
    from devops_cli.docker.engine import DockerEngineService

    DockerEngineService.reset_instance()
    yield
    DockerEngineService.reset_instance()


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
        f"telemetry:\n  enabled: true\n  endpoint: http://127.0.0.1:{unserved_side_channel_port}\n"
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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live bubblewrap tests where bubblewrap is not installed on the host (#832, #1337)."""
    from devops_cli.sandbox.host import HostSandbox

    if not HostSandbox().is_available():
        skip_bwrap = pytest.mark.skip(reason="bubblewrap is not installed")
        for item in items:
            if "bwrap" in item.keywords:
                item.add_marker(skip_bwrap)
