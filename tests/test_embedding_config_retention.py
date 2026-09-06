"""Unit tests verifying embedding model configuration retention, tag preservation, and task overrides."""

from __future__ import annotations

from devops_cli.ai.agents.embeddings import Embedder
from devops_cli.ai.rag.embeddings import EmbeddingsEngine, OllamaEmbeddingModel
from devops_cli.config.settings import AIConfig, AITaskOverride, Settings


def test_embeddings_engine_defaults_to_active_settings(monkeypatch) -> None:
    """Verify that EmbeddingsEngine defaults to load_settings().ai rather than blank AIConfig."""
    custom_settings = Settings()
    custom_settings.ai.rag.embedding_model = "embeddinggemma:300m"
    custom_settings.ai.rag.embedding_url = "http://workhorse.lan:11434"
    monkeypatch.setattr("devops_cli.config.settings.load_settings", lambda: custom_settings)

    engine = EmbeddingsEngine()
    assert engine.model == "embeddinggemma:300m"
    assert engine.ai_config.rag.embedding_url == "http://workhorse.lan:11434"


def test_embeddings_engine_respects_task_override() -> None:
    """Verify that EmbeddingsEngine prioritizes ai.tasks.embedding.model if configured."""
    ai_cfg = AIConfig()
    ai_cfg.rag.embedding_model = "embeddinggemma:300m"
    ai_cfg.tasks.embedding = AITaskOverride(model="custom-task-embed:v1")

    engine = EmbeddingsEngine(ai_cfg)
    assert engine.model == "custom-task-embed:v1"


def test_ollama_embedding_model_defaults_to_active_settings(monkeypatch) -> None:
    """Verify OllamaEmbeddingModel inherits active embedding_model from settings."""
    custom_settings = Settings()
    custom_settings.ai.rag.embedding_model = "embeddinggemma:300m"
    monkeypatch.setattr("devops_cli.config.settings.load_settings", lambda: custom_settings)

    model = OllamaEmbeddingModel()
    assert model.model_name == "embeddinggemma:300m"


def test_embedder_preserves_colon_tags_in_model_name(monkeypatch) -> None:
    """Verify Embedder does not truncate model names with colon tags (e.g. embeddinggemma:300m)."""
    custom_settings = Settings()
    custom_settings.ai.rag.embedding_model = "embeddinggemma:300m"
    monkeypatch.setattr("devops_cli.config.settings.load_settings", lambda: custom_settings)

    embedder1 = Embedder("ollama:embeddinggemma:300m")
    eng1 = embedder1._get_engine()
    assert eng1.model == "embeddinggemma:300m"

    embedder2 = Embedder("ollama:qwen3:14b-q8_0")
    eng2 = embedder2._get_engine()
    assert eng2.model == "qwen3:14b-q8_0"
