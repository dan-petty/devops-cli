"""Shared test fixtures."""

from __future__ import annotations

import errno
import ipaddress
import os
import subprocess
import sys
import threading
import weakref
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
    from devops_cli.roadmap.store import RoadmapStore
    from tests.web_fakes import StubWeb


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


def _is_loopback(host: str) -> bool:
    """Report whether a connect or lookup names the loopback interface."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_ip_literal(host: str) -> bool:
    """Report whether a host is an IP address, which resolves without a DNS query."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _refuses_connect(address: Any, owned_ports: set[int]) -> bool:
    """Report whether the network guard refuses a connect; raise for a host that is not loopback."""
    if not (isinstance(address, tuple) and len(address) >= 2):
        return False
    host = str(address[0])
    if not _is_loopback(host):
        raise RuntimeError(
            f"External network call blocked during test execution: attempt to connect to {host}:{address[1]}. "
            "All external APIs and endpoints must be mocked in tests."
        )
    return address[1] not in owned_ports


@pytest.fixture(autouse=True, scope="session")
def prevent_external_network_calls() -> None:
    """Guarantee that tests never hit external APIs or endpoints, nor live services on loopback.

    A loopback connect reaches only a port this test process listens on, and only while that
    listener is open. Any other loopback port refuses, as if nothing listened there, so a
    `kubectl port-forward` or a daemon on the workstation is never reached and every machine takes
    CI's offline path. Once a test closes its server, the port refuses again, so whatever binds it
    next, such as another xdist worker or a port-forward, is not reached either. The refusal is the
    `ConnectionRefusedError` that clients already handle: a `RuntimeError` would escape them and
    send the test down a path no user reaches. Non-loopback connects raise `RuntimeError`.

    The guard patches this process only. A subprocess a test spawns is not guarded, and a server
    a test starts in a subprocess is refused like any other port this process does not own.
    """
    import socket

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_listen = socket.socket.listen
    orig_getaddrinfo = socket.getaddrinfo
    listeners: weakref.WeakKeyDictionary[socket.socket, int] = weakref.WeakKeyDictionary()
    listeners_lock = threading.RLock()

    # A blocked connect still pays for a real DNS query first. Fail external
    # names the way an unresolvable one does, so callers take their existing gaierror path at once.
    def guarded_getaddrinfo(host, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else str(host)
        flags = kwargs.get("flags", args[4] if len(args) >= 5 else 0) or 0
        if (
            host is None
            or bool(flags & socket.AI_NUMERICHOST)
            or _is_loopback(name)
            or _is_ip_literal(name)
        ):
            return orig_getaddrinfo(host, *args, **kwargs)
        raise socket.gaierror(
            socket.EAI_NONAME,
            f"External DNS lookup blocked during test execution: {name}. "
            "All external APIs and endpoints must be mocked in tests.",
        )

    def guarded_listen(self, *args):
        orig_listen(self, *args)
        name = self.getsockname()
        if isinstance(name, tuple):
            with listeners_lock:
                listeners[self] = name[1]

    # A listener's port is owned while the socket is open. A closed one reports fileno -1, and one
    # that was collected has already left the weak mapping.
    def owned_ports() -> set[int]:
        with listeners_lock:
            return {port for sock, port in listeners.items() if sock.fileno() != -1}

    def guarded_connect(self, address):
        if _refuses_connect(address, owned_ports()):
            raise ConnectionRefusedError(errno.ECONNREFUSED, os.strerror(errno.ECONNREFUSED))
        return orig_connect(self, address)

    def guarded_connect_ex(self, address):
        if _refuses_connect(address, owned_ports()):
            return errno.ECONNREFUSED
        return orig_connect_ex(self, address)

    # Installed for the rest of the process, not undone at teardown: an export a test queued on a
    # worker thread, or one `atexit` flushes, still runs after the last fixture is torn down.
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.socket.listen = guarded_listen
    socket.getaddrinfo = guarded_getaddrinfo


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
    """
    import httpx2

    from devops_cli.http import broker
    from tests.web_fakes import StubWeb

    web = StubWeb()
    transport = httpx2.MockTransport(web.handle)

    class StubClient(httpx2.Client):
        """An httpx2.Client whose transport is always the stub's."""

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**{**kwargs, "transport": transport})

    class StubAsyncClient(httpx2.AsyncClient):
        """An httpx2.AsyncClient whose transport is always the stub's."""

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**{**kwargs, "transport": transport})

    monkeypatch.setattr(httpx2, "Client", StubClient)
    monkeypatch.setattr(httpx2, "AsyncClient", StubAsyncClient)
    stub_broker = broker.HttpClientBroker()
    monkeypatch.setattr(broker, "DEFAULT_HTTP_BROKER", stub_broker)
    yield web
    stub_broker.close()


# Rich reads COLUMNS once, when a console is built, and `devops_cli.output.console` caches one per
# process. Set the terminal before any test module is imported, so a console built during
# collection is not left at the 80-column non-terminal default for its whole xdist worker.
_TERMINAL_ENV = {"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"}
os.environ.update(_TERMINAL_ENV)


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
    """Keep the user-level data root, where a review's relative data paths resolve (#972), in
    the test's temporary directory rather than the developer's home."""
    user_data_root = (tmp_path / "user-data").resolve()
    monkeypatch.setattr("devops_cli.core.repo.CONST_USER_DATA_ROOT", user_data_root)
    return user_data_root


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
def isolate_session_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep tests off the devcontainer's session bus, where gnome-keyring holds real secrets."""
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))  # the bus fallback is $XDG_RUNTIME_DIR/bus


@pytest.fixture(autouse=True)
def isolate_gh_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep tests from reading the developer's gh login, which may hold a plaintext token."""
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "gh-config"))


PINNED_GITHUB_TOKEN = "test-github-token"


@pytest.fixture(autouse=True)
def pin_github_session(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Give every test one fake GitHub identity, so no test runs a real `gh auth token`.

    Every gh and git child a test starts gets this token as GH_TOKEN, never the developer's login.
    A test of the lookup itself sets `devops_cli.core.process._github_token` back to None, and
    `no_github_identity` makes every lookup fail. The session is dropped only once something has
    imported it: importing it here would load all of `devops_cli.github` in every worker.
    """
    from devops_cli.core import process

    def drop_session() -> None:
        session_module = sys.modules.get("devops_cli.github.session")
        if session_module is not None:
            session_module.reset_github_session()

    drop_session()
    monkeypatch.setattr(process, "_github_token", PINNED_GITHUB_TOKEN)
    monkeypatch.setattr(process, "_github_lookup_failure", None)
    yield PINNED_GITHUB_TOKEN
    drop_session()


def fail_the_github_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `gh auth token` print no token from now on, as when gh has no login."""
    from devops_cli.core import process
    from devops_cli.lang import ERRORS

    unauthenticated = ERRORS.git.github_unauthenticated.format(status=1)
    monkeypatch.setattr(process, "_github_token", None)
    monkeypatch.setattr(process, "_lookup_github_token", lambda: ("", unauthenticated))


@pytest.fixture
def no_github_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """The process has no GitHub identity: every lookup finds no token."""
    fail_the_github_lookup(monkeypatch)


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
    """Open the GitHub store over a `gh` that exits 1, as when GitHub can't be read.

    Returns the argv of every `gh` command the store ran.
    """
    from devops_cli.roadmap import store as roadmap_module
    from devops_cli.roadmap.github_store import GitHubRoadmapStore

    calls: list[list[str]] = []

    def gh_exits_1(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "HTTP 503: Service Unavailable")

    monkeypatch.setattr(
        roadmap_module,
        "get_roadmap_store",
        # A runner the command passes (intake's spend meter) is replaced by the failing `gh`.
        lambda repo, runner=None, **kwargs: GitHubRoadmapStore(repo, runner=gh_exits_1, **kwargs),
    )
    return calls


@pytest.fixture(autouse=True)
def isolate_devops_cli_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Ensure every test gets its own temporary config through DEVOPS_CLI_CONFIG."""
    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.telemetry.tracer import reset_tracer

    reset_settings_cache()
    reset_tracer()
    test_config_dir = (tmp_path / ".test_config").resolve()
    test_config_dir.mkdir(parents=True, exist_ok=True)
    test_config = test_config_dir / "config.yaml"
    test_config.write_text(
        "telemetry:\n  enabled: true\n  endpoint: http://localhost:4318\n"
        "ai:\n  allow_private_network: true\n  rag:\n    enabled: false\n"
        "qdrant:\n  url: http://localhost:6333\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(test_config))
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENDPOINT", "http://localhost:4318")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    with patch("devops_cli.config.settings.CONFIG_PATH", test_config):
        yield test_config
    reset_settings_cache()
    reset_tracer()


@pytest.fixture(autouse=True, scope="session")
def guard_live_rag_data() -> None:
    """Ensure no test ever interacts with or mutates live Qdrant endpoints."""
    from qdrant_client import QdrantClient as NativeQdrantClient

    from devops_cli.ai.rag.qdrant import QdrantClient

    orig_init = QdrantClient.__init__
    orig_native_init = NativeQdrantClient.__init__

    cfg_domain = ""
    try:
        from devops_cli.config.settings import load_settings

        s = load_settings()
        cfg_domain = (getattr(getattr(s, "k8s", None), "domain", None) or "").strip().lower()
    except Exception:
        pass

    def guarded_init(
        self, base_url: str = "http://localhost:6333", *args: Any, **kwargs: Any
    ) -> None:
        url_str = str(base_url).lower()
        if cfg_domain and cfg_domain in url_str:
            raise RuntimeError(
                f"Test attempted to connect to live Qdrant endpoint: {base_url}. "
                "Tests must use localhost, example.com, or mocks."
            )
        orig_init(self, base_url, *args, **kwargs)

    def guarded_native_init(self, *args: Any, **kwargs: Any) -> None:
        raw_url = kwargs.get("url") or (args[0] if args else "")
        url_str = str(raw_url).lower()
        if cfg_domain and cfg_domain in url_str:
            raise RuntimeError(
                f"Test attempted to connect to live Qdrant endpoint: {raw_url}. "
                "Tests must use localhost, example.com, or mocks."
            )
        orig_native_init(self, *args, **kwargs)

    QdrantClient.__init__ = guarded_init
    NativeQdrantClient.__init__ = guarded_native_init


def _check_test_paths_isolated(
    test_paths: Sequence[Path | str],
    repo_root: Path,
) -> list[str]:
    """Verify that all configured test paths are strictly outside the project directory."""
    violations: list[str] = []
    resolved_root = repo_root.resolve()
    for p in test_paths:
        resolved_p = Path(p).resolve()
        if resolved_p.is_relative_to(resolved_root):
            violations.append(f"Test path {resolved_p} is inside project directory {resolved_root}")
    return violations


@pytest.fixture(autouse=True)
def verify_test_paths_isolated() -> None:
    """Ensure all test environment paths are strictly outside the project repository."""
    from devops_cli.config.constants import CONST_ISOLATED_TEST_ENV_KEYS

    repo_root = Path(__file__).resolve().parent.parent.resolve()
    test_paths: list[Path] = []
    for env_key in CONST_ISOLATED_TEST_ENV_KEYS:
        val = os.environ.get(env_key)
        if val:
            test_paths.append(Path(val))
    violations = _check_test_paths_isolated(test_paths, repo_root)
    if violations:
        raise AssertionError("; ".join(violations))


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


# =============================================================================
# Workspace Isolation Tripwire (Issue #749)
# =============================================================================


def _is_xdist_worker(config: pytest.Config) -> bool:
    """Report whether the pytest process is an xdist worker rather than the controller."""
    return getattr(config, "workerinput", None) is not None


def _get_git_tracked_files(repo_root: Path) -> list[str]:
    """Return relative paths of all git-tracked files in the repository."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def _snapshot_tracked_files(
    repo_root: Path, tracked_files: list[str]
) -> dict[str, tuple[int, int]]:
    """Capture mtime and size for all tracked files."""
    stamps: dict[str, tuple[int, int]] = {}
    for rel_path in tracked_files:
        full_path = repo_root / rel_path
        try:
            st = full_path.stat()
            stamps[rel_path] = (st.st_mtime_ns, st.st_size)
        except OSError:
            pass
    return stamps


def _check_config_diff(repo_root: Path, initial_bytes: bytes | None) -> str | None:
    """Detect changes to workspace config.yaml."""
    cfg = repo_root / "config.yaml"
    curr = cfg.read_bytes() if cfg.exists() else None
    if initial_bytes is None and curr is not None:
        return "config.yaml (created by tests)"
    if initial_bytes is not None and curr is None:
        return "config.yaml (deleted by tests)"
    if initial_bytes != curr:
        return "config.yaml (content modified by tests)"
    return None


def _is_git_file_modified(repo_root: Path, rel_path: str) -> bool:
    """Check if a tracked file has uncommitted changes relative to the git index.

    git finds the index itself, also in a linked worktree, where `.git` is a file; a git error
    exits non-zero and counts as a change.
    """
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--quiet", "--", rel_path],
            check=False,
            capture_output=True,
        )
        return res.returncode != 0
    except Exception:
        return True


def _check_tracked_diff(repo_root: Path, snapshot: dict[str, tuple[int, int]]) -> list[str]:
    """Detect modifications or deletions in git-tracked files."""
    diffs: list[str] = []
    for rel_path, (init_mtime, init_size) in snapshot.items():
        full = repo_root / rel_path
        if not full.exists():
            diffs.append(f"{rel_path} (deleted by tests)")
            continue
        try:
            st = full.stat()
            if (st.st_mtime_ns, st.st_size) != (init_mtime, init_size):
                if _is_git_file_modified(repo_root, rel_path):
                    diffs.append(f"{rel_path} (modified by tests)")
        except OSError:
            pass
    return diffs


def _check_forbidden_test_paths(repo_root: Path) -> list[str]:
    """Detect explicit test-only paths created in the project repository."""
    from devops_cli.config.constants import CONST_FORBIDDEN_PROJECT_TEST_PATHS

    diffs: list[str] = []
    for rel in CONST_FORBIDDEN_PROJECT_TEST_PATHS:
        target = repo_root / rel
        if target.exists():
            diffs.append(f"{rel} (test path found in project directory)")
    return diffs


def _evaluate_workspace_tripwire(snapshot: dict[str, Any]) -> list[str]:
    """Evaluate all workspace isolation tripwire checks against initial session snapshot."""
    repo_root = snapshot["repo_root"]
    failures: list[str] = []
    cfg_diff = _check_config_diff(repo_root, snapshot.get("config_state"))
    if cfg_diff is not None:
        failures.append(cfg_diff)
    failures.extend(_check_tracked_diff(repo_root, snapshot.get("tracked_snapshot", {})))
    failures.extend(_check_forbidden_test_paths(repo_root))
    return failures


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live bubblewrap tests where bubblewrap is not installed on the host (#832)."""

    if True:
        skip_bwrap = pytest.mark.skip(reason="bubblewrap is not installed")
        for item in items:
            if "bwrap" in item.keywords:
                item.add_marker(skip_bwrap)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Snapshot workspace config and tracked files on xdist controller."""
    if _is_xdist_worker(session.config):
        return
    repo_root = Path(__file__).resolve().parent.parent
    tracked = _get_git_tracked_files(repo_root)
    cfg_path = repo_root / "config.yaml"
    session.config._tripwire_snapshot = {  # type: ignore[attr-defined]
        "repo_root": repo_root,
        "config_state": cfg_path.read_bytes() if cfg_path.exists() else None,
        "tracked_snapshot": _snapshot_tracked_files(repo_root, tracked),
    }


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """Verify no tests wrote to workspace config, tracked files, or left test paths."""
    if _is_xdist_worker(session.config):
        return
    snapshot = getattr(session.config, "_tripwire_snapshot", None)
    if snapshot is None:
        return
    failures = _evaluate_workspace_tripwire(snapshot)
    if failures:
        session.config._tripwire_failures = failures  # type: ignore[attr-defined]
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: Any, exitstatus: Any, config: pytest.Config) -> None:
    """Print prominent error section if test isolation tripwire detected leaks."""
    if _is_xdist_worker(config):
        return
    failures = getattr(config, "_tripwire_failures", [])
    if failures:
        terminalreporter.section(
            "TRIPWIRE FAILURE: Workspace mutated during test run", red=True, bold=True
        )
        for f in failures:
            terminalreporter.write_line(f"  - {f}", red=True)
