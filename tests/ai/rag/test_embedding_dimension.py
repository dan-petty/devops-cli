"""An engine learns the dimension of its model from a probe, and remembers it."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.constants import (
    CONST_RAG_MAX_CHUNK_TOKENS,
)
from devops_cli.config.settings import AIConfig
from tests.support.embedding_replies import (
    SERVING_BACKEND,
    answer_posts,
    ollama_engine,
    ollama_reply,
    serve,
)
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_dynamic_probe_ollama_embed(web: WebFake) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        if "/api/embed" in url:
            return httpx2.Response(200, json={"embeddings": [[0.05] * 512]})
        return httpx2.Response(404)

    answer_posts(web, fake_post)
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "unknown-custom-model"
    engine = EmbeddingsEngine(ai_cfg)
    assert engine.dimension == 512


def test_dynamic_probe_ollama_show_metadata(web: WebFake) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        if "/api/embed" in url:
            return httpx2.Response(500, text="Internal Error")
        if "/api/show" in url:
            return httpx2.Response(200, json={"model_info": {"custom.embedding_length": 1024}})
        return httpx2.Response(404)

    answer_posts(web, fake_post)
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "custom-ollama-model"
    engine = EmbeddingsEngine(ai_cfg)
    assert engine.dimension == 1024


def test_dynamic_probe_openai_embeddings(web: WebFake) -> None:

    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 1536}]})

    answer_posts(web, fake_post)
    ai_cfg = AIConfig(provider="openai", allow_private_network=True)
    ai_cfg.tasks.embedding.model = "arbitrary-openai-model"
    engine = EmbeddingsEngine(ai_cfg, api_key="test-key")
    assert engine.dimension == 1536


def test_runtime_dimension_cache_and_learning(web: WebFake) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(200, json={"embeddings": [[0.1] * 256]})

    answer_posts(web, fake_post)
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "dynamic-cached-model"
    engine1 = EmbeddingsEngine(ai_cfg)
    embs = engine1.embed_texts(["sample"])
    assert len(embs[0]) == 256
    assert engine1.dimension == 256

    # Second instance with same model reuses cached dimension
    ai_offline = AIConfig(provider="ollama", ollama_urls=[], allow_private_network=True)
    ai_offline.tasks.embedding.model = "dynamic-cached-model"
    engine2 = EmbeddingsEngine(ai_offline)
    assert engine2.dimension == 256


def test_qwen3_embedding_dimension_pinned() -> None:
    """CONST_KNOWN_EMBEDDING_DIMENSIONS["qwen3-embedding"] is pinned to 1024."""
    from devops_cli.config.constants import CONST_KNOWN_EMBEDDING_DIMENSIONS

    assert CONST_KNOWN_EMBEDDING_DIMENSIONS.get("qwen3-embedding") == 1024


def test_the_dimension_probe_of_an_ollama_node_passes_num_ctx(web: WebFake) -> None:
    """Probing the dimension of an Ollama model sends options.num_ctx like any embedding request."""
    sent = serve(web, ollama_reply)

    dimension = ollama_engine([SERVING_BACKEND]).dimension

    assert (dimension, len(sent), json.loads(sent[0].content).get("options")) == (
        4,
        1,
        {"num_ctx": CONST_RAG_MAX_CHUNK_TOKENS},
    )
