"""Shared test fixtures."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


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


@pytest.fixture(autouse=True, scope="session")
def prevent_external_network_calls():
    """Guarantee that tests never hit external APIs or endpoints."""
    import ipaddress
    import socket

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_getaddrinfo = socket.getaddrinfo

    def _is_loopback(host: str) -> bool:
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def _is_ip_literal(host: str) -> bool:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return False
        return True

    # A blocked connect still pays for a real DNS query first, and the extractor resolves every
    # domain-like token it scans: each lookup costs a round trip per xdist worker. Fail external
    # names the way an unresolvable one does, so callers take their existing gaierror path at once.
    def guarded_getaddrinfo(host, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else str(host)
        if host is None or _is_loopback(name) or _is_ip_literal(name):
            return orig_getaddrinfo(host, *args, **kwargs)
        raise socket.gaierror(
            socket.EAI_NONAME,
            f"External DNS lookup blocked during test execution: {name}. "
            "All external APIs and endpoints must be mocked in tests.",
        )

    def guarded_connect(self, address):
        if isinstance(address, tuple) and len(address) >= 2:
            host = str(address[0])
            if _is_loopback(host):
                return orig_connect(self, address)
            raise RuntimeError(
                f"External network call blocked during test execution: attempt to connect to {host}:{address[1]}. "
                "All external APIs and endpoints must be mocked in tests."
            )
        return orig_connect(self, address)

    def guarded_connect_ex(self, address):
        if isinstance(address, tuple) and len(address) >= 2:
            host = str(address[0])
            if _is_loopback(host):
                return orig_connect_ex(self, address)
            raise RuntimeError(
                f"External network call blocked during test execution: attempt to connect to {host}:{address[1]}. "
                "All external APIs and endpoints must be mocked in tests."
            )
        return orig_connect_ex(self, address)

    with (
        patch.object(socket.socket, "connect", guarded_connect),
        patch.object(socket.socket, "connect_ex", guarded_connect_ex),
        patch.object(socket, "getaddrinfo", guarded_getaddrinfo),
    ):
        yield


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
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, number))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    return address


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
    import devops_cli.output.console as console_module

    os.environ.update(_TERMINAL_ENV)
    os.environ.pop("DEVOPS_CLI_DRY_RUN", None)
    console_module._CONSOLE = None
    console_module._STDERR_CONSOLE = None
    yield
    os.environ.pop("DEVOPS_CLI_DRY_RUN", None)


@pytest.fixture(autouse=True)
def isolate_llm_response_cache(tmp_path: Path):
    """Ensure LLM response cache is isolated per test to prevent cross-test cache hits."""
    from devops_cli.ai.response_cache import get_llm_response_cache, reset_llm_response_cache

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
def isolate_session_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep tests off the devcontainer's session bus, where gnome-keyring holds real secrets."""
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))  # the bus fallback is $XDG_RUNTIME_DIR/bus


@pytest.fixture(autouse=True)
def isolate_gh_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep tests from reading the developer's gh login, which may hold a plaintext token."""
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "gh-config"))


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
        "ai:\n  allow_private_network: true\n  rag:\n    enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(test_config))
    monkeypatch.setenv("DEVOPS_OTEL_ENDPOINT", "http://localhost:4318")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    with patch("devops_cli.config.settings.CONFIG_PATH", test_config):
        yield test_config
    reset_settings_cache()
    reset_tracer()


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
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
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
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n', encoding="utf-8"
    )
    git(main, "add", ".")
    git(main, "commit", "--quiet", "-m", "first")
    nested = main / ".claude" / "worktrees" / "wt"
    git(main, "worktree", "add", "--quiet", "-b", "nested", str(nested))
    return main, nested


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
    """Check if a tracked file has uncommitted changes relative to the git index."""
    git_index = repo_root / ".git" / "index"
    if not git_index.exists():
        return True
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
    if not snapshot.get("had_index_lock", False) and (repo_root / ".git" / "index.lock").exists():
        failures.append(".git/index.lock (left behind by tests)")
    failures.extend(_check_tracked_diff(repo_root, snapshot.get("tracked_snapshot", {})))
    failures.extend(_check_forbidden_test_paths(repo_root))
    return failures


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
        "had_index_lock": (repo_root / ".git" / "index.lock").exists(),
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
