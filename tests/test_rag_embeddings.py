"""Unit tests for EmbeddingsEngine (Ollama, OpenAI, deterministic fallback)."""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.settings import AIConfig


def test_deterministic_fallback_embeddings() -> None:
    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg)
    embs = engine.embed_texts(["hello world", "test query"])
    assert len(embs) == 2
    assert len(embs[0]) == 1024
    # Ensure cosine normalization (~1.0 magnitude)
    norm = sum(v * v for v in embs[0]) ** 0.5
    assert 0.99 <= norm <= 1.01


def test_ollama_embeddings_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(200, json={"embedding": [0.1] * 384})

    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    engine = EmbeddingsEngine(ai_cfg)
    embs = engine.embed_texts(["sample text"])
    assert len(embs) == 1
    assert len(embs[0]) == 384


def test_openai_embeddings_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.2] * 1536}]},
        )

    monkeypatch.setattr(
        "devops_cli.ai.rag.embeddings.validate_service_url", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))
    ai_cfg = AIConfig(provider="openai", allow_private_network=True)
    engine = EmbeddingsEngine(ai_cfg, api_key="mock-test-key")
    embs = engine.embed_texts(["sample text"])
    assert len(embs) == 1
    assert len(embs[0]) == 1536
