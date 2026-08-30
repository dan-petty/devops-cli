"""Tests for environment variable overrides in configuration loading."""

from __future__ import annotations

from pathlib import Path

from devops_cli.config import settings


def test_load_settings_applies_env_overrides_for_non_secret_fields(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
ai:
  provider: ollama
  model: gemma4:26b
  ollama_urls:
    - http://localhost:11434
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "CONFIG_PATH", config_path)
    monkeypatch.setenv("DEVOPS_CLI_AI_MODEL", "qwen3.6:35b")
    monkeypatch.setenv("DEVOPS_CLI_AI_REASONING_EFFORT", "low")
    monkeypatch.setenv("DEVOPS_CLI_AI_OLLAMA_URLS", "http://192.168.1.4:11434")

    loaded_settings = settings.load_settings()

    assert loaded_settings.ai.model == "qwen3.6:35b"
    assert loaded_settings.ai.reasoning_effort == "low"
    assert loaded_settings.ai.get_ollama_urls == ["http://192.168.1.4:11434"]


def test_load_settings_applies_embedding_task_and_rag_url_overrides(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
ai:
  provider: ollama
  model: qwen3.8:27b
  tasks:
    embedding:
      ollama_urls:
        - http://workhorse.lan:11434
  rag:
    embedding_url: http://workhorse.lan:11434
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "CONFIG_PATH", config_path)
    loaded_settings = settings.load_settings()

    assert loaded_settings.ai.tasks.embedding.ollama_urls == ["http://workhorse.lan:11434"]
    assert loaded_settings.ai.rag.embedding_url == "http://workhorse.lan:11434"

    # Verify EmbeddingsEngine utilizes embedding task override
    from devops_cli.ai.rag.embeddings import EmbeddingsEngine

    embedder = EmbeddingsEngine(ai_config=loaded_settings.ai)
    assert embedder.ai_config.rag.embedding_url == "http://workhorse.lan:11434"


def test_ai_config_for_task_with_context_window_overrides() -> None:
    from devops_cli.config.settings import AIConfig, AITaskOverride

    base_ai = AIConfig(
        provider="ollama",
        model="base-model",
        context_window=32768,
        temperature=0.1,
    )
    base_ai.tasks.analysis = AITaskOverride(
        model="analysis-model",
        context_window=40960,
        num_ctx=40960,
        temperature=0.0,
    )

    analysis_cfg = base_ai.for_task("analysis")
    assert analysis_cfg.model == "analysis-model"
    assert analysis_cfg.context_window == 40960
    assert analysis_cfg.num_ctx == 40960
    assert analysis_cfg.temperature == 0.0

    chat_cfg = base_ai.for_task("chat")
    assert chat_cfg.model == "base-model"
    assert chat_cfg.context_window == 32768
