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
def isolate_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure tests run against an isolated temporary .data/ directory to protect user reviews."""
    test_data_dir = (tmp_path / ".data").resolve()
    test_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(test_data_dir))
    monkeypatch.setenv("DEVOPS_DATA_DIR", str(test_data_dir))
    monkeypatch.setenv("DEVOPS_CLI_DATA_REVIEWS_DIR", str(test_data_dir / "reviews"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(test_data_dir / "analysis"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_LOGS_DIR", str(test_data_dir / "logs"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_MODELS_DIR", str(test_data_dir / "models"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_CACHE_DIR", str(test_data_dir / "cache"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_BENCHMARKS_DIR", str(test_data_dir / "benchmarks"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_RAG_DIR", str(test_data_dir / "rag"))
    monkeypatch.setenv(
        "DEVOPS_CLI_DATA_AUDIT_LOG_PATH", str(test_data_dir / "logs" / "audit.jsonl")
    )
    monkeypatch.setenv(
        "DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH", str(test_data_dir / "feedback_dataset.jsonl")
    )
    yield test_data_dir


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
    """Ensure tests do not load or mutate local workspace config.yaml or ~/.config."""
    from devops_cli.telemetry.tracer import reset_tracer

    reset_tracer()
    with (
        patch.dict(
            os.environ,
            {
                "DEVOPS_CLI_CONFIG": str(session_isolated_config),
                "DEVOPS_OTEL_ENDPOINT": "http://localhost:4318",
                "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK": "true",
            },
        ),
        patch("devops_cli.config.settings.CONFIG_PATH", session_isolated_config),
        patch("devops_cli.config.settings.CONFIG_DIR", session_isolated_config.parent),
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
