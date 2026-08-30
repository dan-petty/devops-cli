"""Unit tests for configurable data directory resolution and environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clean_data_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure data directory environment variables are completely clean between tests."""
    for k in list(os.environ.keys()):
        if (
            k.startswith("DEVOPS_CLI_DATA")
            or k.startswith("DEVOPS_DATA")
            or k == "DEVOPS_CLI_CONFIG"
        ):
            monkeypatch.delenv(k, raising=False)


def test_default_data_constants_and_settings() -> None:
    """Verify DEFAULT data constants, DataConfig model, and Settings defaults."""
    from devops_cli.config import (
        DEFAULT_ANALYSIS_DATA_DIR,
        DEFAULT_AUDIT_LOG_PATH,
        DEFAULT_BENCHMARKS_DATA_DIR,
        DEFAULT_CACHE_DATA_DIR,
        DEFAULT_DATA_DIR,
        DEFAULT_FEEDBACK_DATASET_PATH,
        DEFAULT_LLM_CACHE_DATA_DIR,
        DEFAULT_LOGS_DATA_DIR,
        DEFAULT_MODELS_DATA_DIR,
        DEFAULT_RAG_DATA_DIR,
        DEFAULT_REVIEWS_DATA_DIR,
        DEFAULT_TLS_DATA_DIR,
        DataConfig,
        Settings,
    )
    from devops_cli.config import env as env_mod
    from devops_cli.config import options as opt

    assert DEFAULT_DATA_DIR == Path(".data")
    assert DEFAULT_ANALYSIS_DATA_DIR == Path(".data/analysis")
    assert DEFAULT_REVIEWS_DATA_DIR == Path(".data/reviews")
    assert DEFAULT_LOGS_DATA_DIR == Path(".data/logs")
    assert DEFAULT_MODELS_DATA_DIR == Path(".data/models")
    assert DEFAULT_CACHE_DATA_DIR == Path(".data/cache")
    assert DEFAULT_LLM_CACHE_DATA_DIR == Path(".data/cache/llm")
    assert DEFAULT_BENCHMARKS_DATA_DIR == Path(".data/benchmarks")
    assert DEFAULT_RAG_DATA_DIR == Path(".data/rag")
    assert DEFAULT_AUDIT_LOG_PATH == Path(".data/logs/audit.jsonl")
    assert DEFAULT_FEEDBACK_DATASET_PATH == Path(".data/feedback_dataset.jsonl")
    assert DEFAULT_TLS_DATA_DIR == Path(".data/tls")

    data_cfg = DataConfig()
    assert data_cfg.dir == DEFAULT_DATA_DIR
    assert data_cfg.analysis_dir == DEFAULT_ANALYSIS_DATA_DIR
    assert data_cfg.reviews_dir == DEFAULT_REVIEWS_DATA_DIR
    assert data_cfg.logs_dir == DEFAULT_LOGS_DATA_DIR
    assert data_cfg.models_dir == DEFAULT_MODELS_DATA_DIR
    assert data_cfg.cache_dir == DEFAULT_CACHE_DATA_DIR
    assert data_cfg.benchmarks_dir == DEFAULT_BENCHMARKS_DATA_DIR
    assert data_cfg.rag_dir == DEFAULT_RAG_DATA_DIR
    assert data_cfg.tls_dir == DEFAULT_TLS_DATA_DIR
    assert data_cfg.audit_log_path == DEFAULT_AUDIT_LOG_PATH
    assert data_cfg.feedback_dataset_path == DEFAULT_FEEDBACK_DATASET_PATH

    settings = Settings()
    assert settings.data.dir == DEFAULT_DATA_DIR
    assert settings.data.tls_dir == DEFAULT_TLS_DATA_DIR
    assert settings.data.rag_dir == DEFAULT_RAG_DATA_DIR

    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_DIR] == env_mod.ENV_DATA_DIR
    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_REVIEWS_DIR] == env_mod.ENV_DATA_REVIEWS_DIR
    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_LOGS_DIR] == env_mod.ENV_DATA_LOGS_DIR
    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_RAG_DIR] == env_mod.ENV_DATA_RAG_DIR
    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_TLS_DIR] == env_mod.ENV_DATA_TLS_DIR


def test_data_config_cascades_custom_base_dir() -> None:
    """Verify that customizing data.dir cascades to child directories unless explicitly overridden."""
    from devops_cli.config import DataConfig

    custom_base = Path("/workspace/.data/agent")
    cfg = DataConfig(dir=custom_base)

    assert cfg.dir == custom_base
    assert cfg.analysis_dir == custom_base / "analysis"
    assert cfg.reviews_dir == custom_base / "reviews"
    assert cfg.logs_dir == custom_base / "logs"
    assert cfg.models_dir == custom_base / "models"
    assert cfg.cache_dir == custom_base / "cache"
    assert cfg.benchmarks_dir == custom_base / "benchmarks"
    assert cfg.rag_dir == custom_base / "rag"
    assert cfg.tls_dir == custom_base / "tls"
    assert cfg.audit_log_path == custom_base / "logs" / "audit.jsonl"
    assert cfg.feedback_dataset_path == custom_base / "feedback_dataset.jsonl"

    # Explicit child override should be preserved
    explicit_reviews = Path("/var/log/reviews")
    cfg_explicit = DataConfig(dir=custom_base, reviews_dir=explicit_reviews)
    assert cfg_explicit.dir == custom_base
    assert cfg_explicit.reviews_dir == explicit_reviews
    assert cfg_explicit.benchmarks_dir == custom_base / "benchmarks"
    assert cfg_explicit.tls_dir == custom_base / "tls"


def test_load_settings_cascades_devops_cli_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that DEVOPS_CLI_DATA_DIR populates all 10 child data paths."""
    from devops_cli.config.settings import load_settings

    custom_dir = tmp_path / "custom_agent_dir"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(custom_dir))

    settings = load_settings()
    assert settings.data.dir == custom_dir
    assert settings.data.analysis_dir == custom_dir / "analysis"
    assert settings.data.reviews_dir == custom_dir / "reviews"
    assert settings.data.logs_dir == custom_dir / "logs"
    assert settings.data.models_dir == custom_dir / "models"
    assert settings.data.cache_dir == custom_dir / "cache"
    assert settings.data.benchmarks_dir == custom_dir / "benchmarks"
    assert settings.data.rag_dir == custom_dir / "rag"
    assert settings.data.tls_dir == custom_dir / "tls"
    assert settings.data.audit_log_path == custom_dir / "logs" / "audit.jsonl"
    assert settings.data.feedback_dataset_path == custom_dir / "feedback_dataset.jsonl"


def test_load_settings_cascades_devops_data_dir_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that DEVOPS_DATA_DIR alias populates all 10 child data paths."""
    from devops_cli.config.settings import load_settings

    custom_dir = tmp_path / "custom_alias_dir"
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.setenv("DEVOPS_DATA_DIR", str(custom_dir))

    settings = load_settings()
    assert settings.data.dir == custom_dir
    assert settings.data.reviews_dir == custom_dir / "reviews"
    assert settings.data.benchmarks_dir == custom_dir / "benchmarks"
    assert settings.data.tls_dir == custom_dir / "tls"


def test_load_settings_preserves_explicit_child_env_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that specific child directory environment variables override the base cascade."""
    from devops_cli.config.settings import load_settings

    custom_base = tmp_path / "base_agent_dir"
    explicit_reviews = tmp_path / "custom_reviews_dir"
    explicit_rag = tmp_path / "custom_rag_dir"

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(custom_base))
    monkeypatch.setenv("DEVOPS_CLI_DATA_REVIEWS_DIR", str(explicit_reviews))
    monkeypatch.setenv("DEVOPS_CLI_DATA_RAG_DIR", str(explicit_rag))

    settings = load_settings()
    assert settings.data.dir == custom_base
    assert settings.data.reviews_dir == explicit_reviews
    assert settings.data.rag_dir == explicit_rag
    # Other unmentioned paths should still cascade to custom_base
    assert settings.data.benchmarks_dir == custom_base / "benchmarks"
    assert settings.data.analysis_dir == custom_base / "analysis"
    assert settings.data.tls_dir == custom_base / "tls"


def test_load_settings_cascades_yaml_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that data.dir configured in config.yaml populates all child data paths."""
    from devops_cli.config.settings import load_settings

    custom_cfg = tmp_path / "config.yaml"
    custom_data = tmp_path / "yaml_custom_data"
    custom_cfg.write_text(f"data:\n  dir: {custom_data}\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(custom_cfg))
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.delenv("DEVOPS_DATA_DIR", raising=False)

    settings = load_settings()
    assert settings.data.dir == custom_data
    assert settings.data.reviews_dir == custom_data / "reviews"
    assert settings.data.benchmarks_dir == custom_data / "benchmarks"
    assert settings.data.analysis_dir == custom_data / "analysis"
    assert settings.data.rag_dir == custom_data / "rag"
    assert settings.data.tls_dir == custom_data / "tls"


def test_get_benchmarks_base_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _get_benchmarks_base_dir routes to isolated data dir."""
    from devops_cli.ai.benchmark.runner import _get_benchmarks_base_dir

    isolated_data = tmp_path / "custom_data_agent"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(isolated_data))

    bench_dir = _get_benchmarks_base_dir()
    assert bench_dir.is_absolute()
    assert str(bench_dir).startswith(str(isolated_data))
    assert bench_dir == isolated_data / "benchmarks"
    assert bench_dir.exists()
