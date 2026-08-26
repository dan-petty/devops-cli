"""Shared test fixtures."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_dry_run_state():
    """Ensure dry-run environment variable is cleared and terminal width/color is standardized."""
    os.environ["COLUMNS"] = "250"
    os.environ["NO_COLOR"] = "1"
    os.environ["TERM"] = "dumb"
    os.environ.pop("DEVOPS_CLI_DRY_RUN", None)
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
def clean_test_artifacts():
    """Ensure any test output file artifacts created in workspace .data/ are cleaned up after every test."""
    import shutil

    from devops_cli.config.constants import CONST_DATA_DIR

    yield

    if CONST_DATA_DIR.exists() and CONST_DATA_DIR.is_dir():
        for subdir_name in ["reviews", "analysis", "benchmarks", "cache", "logs"]:
            sub = CONST_DATA_DIR / subdir_name
            if sub.exists() and sub.is_dir():
                for item in sub.iterdir():
                    try:
                        if item.is_file():
                            item.unlink(missing_ok=True)
                        elif item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                    except Exception:
                        pass


@pytest.fixture(scope="session")
def session_isolated_config(tmp_path_factory: pytest.TempPathFactory) -> Path:
    config_dir = tmp_path_factory.mktemp("devops_cli_isolated_config")
    dummy_config = config_dir / "config.yaml"
    dummy_config.write_text(
        "telemetry:\n  enabled: true\n  endpoint: http://localhost:4318\nai:\n  allow_private_network: true\n",
        encoding="utf-8",
    )
    return dummy_config


@pytest.fixture(autouse=True)
def isolate_devops_cli_config(session_isolated_config: Path):
    """Ensure tests do not load local workspace config.yaml with live network endpoints."""
    from devops_cli.telemetry.tracer import reset_tracer

    reset_tracer()
    with patch.dict(
        os.environ,
        {
            "DEVOPS_CLI_CONFIG": str(session_isolated_config),
            "DEVOPS_OTEL_ENDPOINT": "http://localhost:4318",
            "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK": "true",
        },
    ):
        yield
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
