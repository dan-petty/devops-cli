"""Unit tests for configurable data directory resolution and environment variable overrides."""

from __future__ import annotations

from pathlib import Path


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
    assert data_cfg.audit_log_path == DEFAULT_AUDIT_LOG_PATH
    assert data_cfg.feedback_dataset_path == DEFAULT_FEEDBACK_DATASET_PATH

    settings = Settings()
    assert settings.data.dir == DEFAULT_DATA_DIR

    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_DIR] == env_mod.ENV_DATA_DIR
    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_REVIEWS_DIR] == env_mod.ENV_DATA_REVIEWS_DIR
    assert env_mod.OPTION_TO_ENV_VAR[opt.DATA_LOGS_DIR] == env_mod.ENV_DATA_LOGS_DIR


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
    assert cfg.audit_log_path == custom_base / "logs" / "audit.jsonl"
    assert cfg.feedback_dataset_path == custom_base / "feedback_dataset.jsonl"

    # Explicit child override should be preserved
    explicit_reviews = Path("/var/log/reviews")
    cfg_explicit = DataConfig(dir=custom_base, reviews_dir=explicit_reviews)
    assert cfg_explicit.dir == custom_base
    assert cfg_explicit.reviews_dir == explicit_reviews
    assert cfg_explicit.benchmarks_dir == custom_base / "benchmarks"
