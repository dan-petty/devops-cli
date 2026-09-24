"""Shared test fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
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

    def _is_loopback(host: str) -> bool:
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

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
    ):
        yield


# Rich reads COLUMNS once, when a console is built, and `devops_cli.output.console` caches one per
# process. Set the terminal before any test module is imported, so a console built during
# collection is not left at the 80-column non-terminal default for its whole xdist worker.
_TERMINAL_ENV = {"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"}
os.environ.update(_TERMINAL_ENV)


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
def isolate_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure tests run against an isolated temporary .data/ directory to protect user reviews."""
    test_data_dir = (tmp_path / ".data").resolve()
    test_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(test_data_dir))
    yield test_data_dir


@pytest.fixture(autouse=True)
def isolate_session_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep tests off the devcontainer's session bus, where gnome-keyring holds real secrets."""
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))  # the bus fallback is $XDG_RUNTIME_DIR/bus


@pytest.fixture(autouse=True)
def protect_workspace_config():
    """Ensure workspace config.yaml is never modified during test execution."""
    workspace_config = (Path(__file__).parent.parent / "config.yaml").resolve()
    initial_content = workspace_config.read_bytes() if workspace_config.exists() else None
    yield
    if initial_content is None:
        if workspace_config.exists():
            workspace_config.unlink(missing_ok=True)
            pytest.fail(f"Test created unauthorized workspace config at {workspace_config}!")
    elif not workspace_config.exists():
        workspace_config.write_bytes(initial_content)
        pytest.fail(f"Test deleted workspace config at {workspace_config}!")
    else:
        current_content = workspace_config.read_bytes()
        if current_content != initial_content:
            workspace_config.write_bytes(initial_content)
            pytest.fail(f"Test mutated workspace config at {workspace_config}!")


@pytest.fixture(autouse=True)
def isolate_devops_cli_config(tmp_path_factory: pytest.TempPathFactory):
    """Ensure tests do not load or mutate local workspace config.yaml or ~/.config."""
    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.telemetry.tracer import reset_tracer

    # Parsed configuration is held process-wide, so a test starts from disk rather than
    # from whatever the previous test happened to leave behind.
    reset_settings_cache()
    reset_tracer()
    config_dir = tmp_path_factory.mktemp("isolated_test_config")
    dummy_config = config_dir / "config.yaml"
    dummy_config.write_text(
        "telemetry:\n  enabled: true\n  endpoint: http://localhost:4318\nai:\n  allow_private_network: true\n  rag:\n    enabled: false\n",
        encoding="utf-8",
    )
    with (
        patch.dict(
            os.environ,
            {
                "DEVOPS_CLI_CONFIG": str(dummy_config),
                "DEVOPS_OTEL_ENDPOINT": "http://localhost:4318",
                "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK": "true",
            },
        ),
        patch("devops_cli.config.settings.CONFIG_PATH", dummy_config),
    ):
        yield dummy_config
    reset_settings_cache()
    reset_tracer()


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
