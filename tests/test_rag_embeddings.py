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
    assert len(embs[0]) == 768
    # Ensure cosine normalization (~1.0 magnitude)
    norm = sum(v * v for v in embs[0]) ** 0.5
    assert 0.99 <= norm <= 1.01


def test_dynamic_probe_ollama_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        if "/api/embed" in url:
            return httpx2.Response(200, json={"embeddings": [[0.05] * 512]})
        return httpx2.Response(404)

    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    ai_cfg.rag.embedding_model = "unknown-custom-model"
    engine = EmbeddingsEngine(ai_cfg)
    assert engine.dimension == 512


def test_dynamic_probe_ollama_show_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        if "/api/embed" in url:
            return httpx2.Response(500, text="Internal Error")
        if "/api/show" in url:
            return httpx2.Response(200, json={"model_info": {"custom.embedding_length": 1024}})
        return httpx2.Response(404)

    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    ai_cfg.rag.embedding_model = "custom-ollama-model"
    engine = EmbeddingsEngine(ai_cfg)
    assert engine.dimension == 1024


def test_dynamic_probe_openai_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devops_cli.ai.rag.embeddings.validate_service_url", lambda *args, **kwargs: None
    )

    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 1536}]})

    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))
    ai_cfg = AIConfig(provider="openai", allow_private_network=True)
    ai_cfg.rag.embedding_model = "arbitrary-openai-model"
    engine = EmbeddingsEngine(ai_cfg, api_key="test-key")
    assert engine.dimension == 1536


def test_runtime_dimension_cache_and_learning(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(200, json={"embeddings": [[0.1] * 256]})

    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    ai_cfg.rag.embedding_model = "dynamic-cached-model"
    engine1 = EmbeddingsEngine(ai_cfg)
    embs = engine1.embed_texts(["sample"])
    assert len(embs[0]) == 256
    assert engine1.dimension == 256

    # Second instance with same model reuses cached dimension
    ai_offline = AIConfig(provider="ollama", ollama_urls=[], allow_private_network=True)
    ai_offline.rag.embedding_model = "dynamic-cached-model"
    engine2 = EmbeddingsEngine(ai_offline)
    assert engine2.dimension == 256


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


# =============================================================================
# Tests: _EmbeddingLRUCache
# =============================================================================


def test_embedding_lru_cache_basic_put_get() -> None:
    """Cache stores and retrieves vectors by (text, model) key."""
    from devops_cli.ai.rag.embeddings import _EmbeddingLRUCache

    cache = _EmbeddingLRUCache(maxsize=10)
    vec = [0.1, 0.2, 0.3]
    cache.put("hello", "qwen", vec)
    assert cache.get("hello", "qwen") == vec
    assert cache.get("world", "qwen") is None


def test_embedding_lru_cache_overwrite_updates_vector() -> None:
    """Cache updates stored vector when key already exists."""
    from devops_cli.ai.rag.embeddings import _EmbeddingLRUCache

    cache = _EmbeddingLRUCache(maxsize=10)
    cache.put("hello", "qwen", [0.1, 0.2])
    assert cache.get("hello", "qwen") == [0.1, 0.2]

    # Overwrite with new vector
    cache.put("hello", "qwen", [0.9, 0.8])
    assert cache.get("hello", "qwen") == [0.9, 0.8]


def test_embedding_lru_cache_hit_miss_counters() -> None:
    """Cache accurately tracks hit and miss counters."""
    from devops_cli.ai.rag.embeddings import _EmbeddingLRUCache

    cache = _EmbeddingLRUCache(maxsize=5)
    cache.put("a", "m", [1.0])
    cache.get("a", "m")  # hit
    cache.get("b", "m")  # miss
    cache.get("a", "m")  # hit
    assert cache.hits == 2
    assert cache.misses == 1


def test_embedding_lru_cache_eviction() -> None:
    """LRU eviction removes the least-recently-used entry when at capacity."""
    from devops_cli.ai.rag.embeddings import _EmbeddingLRUCache

    cache = _EmbeddingLRUCache(maxsize=3)
    cache.put("a", "m", [1.0])
    cache.put("b", "m", [2.0])
    cache.put("c", "m", [3.0])
    # Access 'a' to make it recently used
    cache.get("a", "m")
    # Inserting 'd' should evict 'b' (LRU)
    cache.put("d", "m", [4.0])
    assert cache.get("b", "m") is None  # evicted
    assert cache.get("a", "m") == [1.0]  # still present
    assert cache.get("d", "m") == [4.0]


def test_embedding_lru_cache_clear() -> None:
    """Clear empties the cache and resets counters."""
    from devops_cli.ai.rag.embeddings import _EmbeddingLRUCache

    cache = _EmbeddingLRUCache(maxsize=5)
    cache.put("x", "m", [0.5])
    cache.get("x", "m")
    cache.clear()
    assert cache.size == 0
    assert cache.hits == 0
    assert cache.misses == 0


def test_embedding_lru_cache_model_isolation() -> None:
    """Cache keys include the model name to prevent cross-model collisions."""
    from devops_cli.ai.rag.embeddings import _EmbeddingLRUCache

    cache = _EmbeddingLRUCache(maxsize=10)
    cache.put("hello", "model-a", [1.0, 0.0])
    cache.put("hello", "model-b", [0.0, 1.0])
    assert cache.get("hello", "model-a") == [1.0, 0.0]
    assert cache.get("hello", "model-b") == [0.0, 1.0]


def test_embeddings_engine_cache_hits_avoid_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """EmbeddingsEngine returns cached results without re-calling the provider."""
    call_count = 0

    def fake_deterministic(
        self: object, texts: list[str], dimensions: int | None = None
    ) -> list[list[float]]:
        nonlocal call_count
        call_count += 1
        return [[float(i) for i in range(4)] for _ in texts]

    monkeypatch.setattr(EmbeddingsEngine, "_deterministic_fallback", fake_deterministic)
    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg)

    first = engine.embed_texts(["hello", "world"])
    assert call_count == 1  # first call hits provider

    second = engine.embed_texts(["hello", "world"])
    assert call_count == 1  # second call should be fully cached
    assert first == second


def test_embeddings_engine_embed_query_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """embed_query returns from cache on repeated calls without re-calling the provider."""
    call_count = 0

    def fake_deterministic(
        self: object, texts: list[str], dimensions: int | None = None
    ) -> list[list[float]]:
        nonlocal call_count
        call_count += 1
        return [[0.5] * 8 for _ in texts]

    monkeypatch.setattr(EmbeddingsEngine, "_deterministic_fallback", fake_deterministic)
    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg)

    v1 = engine.embed_query("test query")
    v2 = engine.embed_query("test query")
    assert v1 == v2
    assert call_count == 1


@pytest.mark.anyio
async def test_ollama_embedding_model_properties_and_embed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OllamaEmbeddingModel conforms to Pydantic AI EmbeddingModel protocol."""
    from devops_cli.ai.rag.embeddings import OllamaEmbeddingModel

    def fake_deterministic(
        self: object, texts: list[str], dimensions: int | None = None
    ) -> list[list[float]]:
        return [[0.2] * 384 for _ in texts]

    monkeypatch.setattr(EmbeddingsEngine, "_deterministic_fallback", fake_deterministic)
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[])
    model = OllamaEmbeddingModel(model_name="all-minilm", ai_config=ai_cfg, dimensions=384)

    assert model.model_name == "all-minilm"
    assert model.system == "ollama"

    # Query embedding
    res_query = await model.embed("What is Kubernetes?", input_type="query")
    assert len(res_query.embeddings) == 1
    assert len(res_query.embeddings[0]) == 384
    assert res_query.inputs == ["What is Kubernetes?"]
    assert res_query.input_type == "query"
    assert res_query.model_name == "all-minilm"
    assert res_query.provider_name == "ollama"
    assert res_query.usage.input_tokens > 0

    # Document embedding
    docs = ["Doc 1", "Doc 2"]
    res_docs = await model.embed(docs, input_type="document")
    assert len(res_docs.embeddings) == 2
    assert res_docs.inputs == docs
    assert res_docs.input_type == "document"


def test_embeddings_engine_to_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify EmbeddingsEngine.to_embedder returns an operational Pydantic AI Embedder."""
    from devops_cli.ai.agents import Embedder

    def fake_deterministic(
        self: object, texts: list[str], dimensions: int | None = None
    ) -> list[list[float]]:
        return [[0.3] * 512 for _ in texts]

    monkeypatch.setattr(EmbeddingsEngine, "_deterministic_fallback", fake_deterministic)
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg)

    embedder = engine.to_embedder()
    assert isinstance(embedder, Embedder)

    res = embedder.embed_query_sync("Engine test")
    assert len(res) == 1
    assert len(res[0]) == 512
    assert res["Engine test"] == [0.3] * 512
