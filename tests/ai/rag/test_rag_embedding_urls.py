"""Tests for direct Ollama embedding URLs resolution and configuration."""

from __future__ import annotations

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.defaults import (
    DEFAULT_OLLAMA_CLUSTER_URL,
    DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.config import ConfigurationError

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_default_embedding_ollama_urls() -> None:
    """The default embedding Ollama URL list contains the embedding cluster URL."""
    config = AIConfig()
    assert config.get_embedding_ollama_urls == [DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]


def test_custom_embedding_ollama_urls() -> None:
    """A configured embedding URL overrides the default embedding cluster URL."""
    custom_url = "http://custom-ollama:11434"
    config = AIConfig(embedding_ollama_urls=[custom_url])
    assert config.get_embedding_ollama_urls == [custom_url]


def test_invalid_embedding_ollama_urls_raises_configuration_error() -> None:
    """An invalid URL entry raises ConfigurationError with the ai.embedding_ollama_urls key."""
    config = AIConfig.model_construct(embedding_ollama_urls=["invalid-scheme-url"])
    with pytest.raises(ConfigurationError) as exc_info:
        _ = config.get_embedding_ollama_urls
    assert exc_info.value.key == "ai.embedding_ollama_urls"


def test_embeddings_engine_uses_embedding_url_not_chat_url() -> None:
    """EmbeddingsEngine._get_ollama_urls returns embedding URLs and ignores chat ollama_urls."""
    config = AIConfig(provider="ollama", ollama_urls=[DEFAULT_OLLAMA_CLUSTER_URL])
    engine = EmbeddingsEngine(config)
    assert engine._get_ollama_urls() == [DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]
