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
    ai_cfg.tasks.embedding.model = "unknown-custom-model"
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
    ai_cfg.tasks.embedding.model = "custom-ollama-model"
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
    ai_cfg.tasks.embedding.model = "arbitrary-openai-model"
    engine = EmbeddingsEngine(ai_cfg, api_key="test-key")
    assert engine.dimension == 1536


def test_runtime_dimension_cache_and_learning(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(200, json={"embeddings": [[0.1] * 256]})

    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))
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
    monkeypatch.setattr(
        EmbeddingsEngine,
        "_dispatch_embed",
        lambda self, texts: [[0.3] * 512 for _ in texts],
    )
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg)

    embedder = engine.to_embedder()
    assert isinstance(embedder, Embedder)

    res = embedder.embed_query_sync("Engine test")
    assert len(res) == 1
    assert len(res[0]) == 512
    assert res["Engine test"] == [0.3] * 512


def test_embed_texts_vector_count_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify EmbeddingsEngine raises EmbeddingsError when provider returns vector count mismatch."""
    from devops_cli.ai.rag.embeddings import EmbeddingsError

    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg)

    monkeypatch.setattr(engine, "_dispatch_embed", lambda texts: [[0.1] * 768])

    with pytest.raises(EmbeddingsError, match="returned 1 vectors for 2 texts"):
        engine.embed_texts(["text1", "text2"])


def test_embeddings_engine_timeout_configuration() -> None:
    """Verify bounded default timeout and configuration precedence."""
    from devops_cli.config.defaults import DEFAULT_RAG_EMBEDDING_TIMEOUT

    # Default timeout is bounded to 15.0s
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg)
    assert engine.timeout == DEFAULT_RAG_EMBEDDING_TIMEOUT

    # Custom embedding task timeout in config
    ai_cfg.tasks.embedding.timeout = 8.0
    engine2 = EmbeddingsEngine(ai_cfg)
    assert engine2.timeout == 8.0

    # Explicit timeout parameter overrides config
    engine3 = EmbeddingsEngine(ai_cfg, timeout=25.0)
    assert engine3.timeout == 25.0


def test_ollama_batch_fast_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify failed/timing-out candidate node automatically fails over to next candidate."""
    ai_cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://example.com:11434", "http://example.com:11435"],
        allow_private_network=True,
    )
    engine = EmbeddingsEngine(ai_cfg)

    calls: list[str] = []

    def fake_query_node(base_url: str, batch_texts: list[str]) -> list[list[float]] | None:
        calls.append(base_url)
        if ":11434" in base_url:
            raise httpx2.ReadTimeout("Simulated read timeout")
        return [[0.2] * 384 for _ in batch_texts]

    monkeypatch.setattr(engine, "_query_ollama_node_batch", fake_query_node)

    results = engine._embed_ollama(["test chunk"])
    assert len(results) == 1
    assert len(results[0]) == 384
    assert results[0] == [0.2] * 384
    assert calls == ["http://example.com:11434", "http://example.com:11435"]


# =============================================================================
# Tests: Adaptive Batch Sizing, Circuit Breaker, Backoff & Valkey L2 (Issue #117)
# =============================================================================


def test_calculate_backoff_delay_bounded() -> None:
    """Verify exponential backoff delay scales exponentially and respects max cap."""
    from devops_cli.ai.rag.embeddings import _calculate_backoff_delay

    d0 = _calculate_backoff_delay(0, base=0.5, max_delay=2.0)
    assert 0.5 <= d0 <= 0.6  # 0.5 + up to 10% jitter

    d1 = _calculate_backoff_delay(1, base=0.5, max_delay=2.0)
    assert 1.0 <= d1 <= 1.15  # 1.0 + up to 10% jitter

    d2 = _calculate_backoff_delay(2, base=0.5, max_delay=2.0)
    assert 2.0 <= d2 <= 2.25  # capped at 2.0 + jitter


def test_adaptive_batch_sizing_halves_on_timeout() -> None:
    """Verify batch size dynamically halves from 32 down to 16, 8, 4 on timeouts."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
    engine = EmbeddingsEngine(ai_cfg, batch_size=32)
    assert engine._current_batch_size == 32

    assert engine._halve_batch_size() == 16
    assert engine._current_batch_size == 16

    assert engine._halve_batch_size() == 8
    assert engine._halve_batch_size() == 4
    assert engine._halve_batch_size() == 2
    assert engine._halve_batch_size() == 1
    # Cannot drop below minimum of 1
    assert engine._halve_batch_size() == 1


def test_adaptive_batch_sizing_halves_on_latency_degradation() -> None:
    """Verify batch size halves when observed latency exceeds latency ceiling."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
    engine = EmbeddingsEngine(ai_cfg, batch_size=32)

    # Within threshold (<= 2.0s): batch size stays unchanged
    engine._record_batch_latency(1.2)
    assert engine._current_batch_size == 32

    # Exceeding threshold (> 2.0s): triggers halving
    engine._record_batch_latency(2.8)
    assert engine._current_batch_size == 16


def test_sub_batch_splitting_and_single_chunk_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify failing large batches automatically subdivide into smaller slices."""
    ai_cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://example.com:11434"],
        allow_private_network=True,
    )
    engine = EmbeddingsEngine(ai_cfg, batch_size=4)

    # Monkeypatch node batch query: fails for batches of size >= 4, succeeds for batches < 4
    def fake_query_batch(base_url: str, batch_texts: list[str]) -> list[list[float]] | None:
        if len(batch_texts) >= 4:
            raise httpx2.ReadTimeout("Timeout on large batch of 4")
        return [[0.5] * 256 for _ in batch_texts]

    monkeypatch.setattr(engine, "_query_ollama_node_batch", fake_query_batch)
    monkeypatch.setattr("time.sleep", lambda s: None)

    texts = ["chunk_1", "chunk_2", "chunk_3", "chunk_4"]
    embs = engine._embed_ollama(texts)

    assert len(embs) == 4
    for vec in embs:
        assert len(vec) == 256
        assert vec == [0.5] * 256


class _MockValkey:
    """In-memory mock for ValkeyClient."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append((key, value, ex))


def test_valkey_l2_chunk_cache_hit_avoids_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify pre-flight Valkey L2 check returns cached vector and avoids remote dispatch."""
    mock_valkey = _MockValkey()
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg, valkey_client=mock_valkey)

    cached_vec = [0.42] * 128
    import json

    # Pre-populate Valkey L2 cache
    key = engine._valkey_key("pre-cached chunk", engine.model)
    mock_valkey.store[key] = json.dumps(cached_vec)

    dispatch_called = False

    def fake_dispatch(texts: list[str]) -> list[list[float]]:
        nonlocal dispatch_called
        dispatch_called = True
        return [[0.99] * 128 for _ in texts]

    monkeypatch.setattr(engine, "_dispatch_embed", fake_dispatch)

    results = engine.embed_texts(["pre-cached chunk"])
    assert len(results) == 1
    assert results[0] == cached_vec
    assert not dispatch_called


def test_valkey_l2_chunk_cache_stores_fresh_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify fresh embeddings computed by provider are written to Valkey L2 with TTL."""
    mock_valkey = _MockValkey()
    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg, valkey_client=mock_valkey)

    fresh_vec = [0.77] * 64
    monkeypatch.setattr(engine, "_dispatch_embed", lambda texts: [fresh_vec for _ in texts])

    results = engine.embed_texts(["newly generated chunk"])
    assert len(results) == 1
    assert results[0] == fresh_vec

    # Verify write into Valkey
    key = engine._valkey_key("newly generated chunk", engine.model)
    assert key in mock_valkey.store
    import json

    assert json.loads(mock_valkey.store[key]) == fresh_vec
    assert any(c[0] == key and c[2] == 604800 for c in mock_valkey.set_calls)


def test_valkey_offline_graceful_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify engine functions normally when Valkey raises connection errors."""

    class _FailingValkey:
        def get(self, key: str) -> None:
            raise RuntimeError("Valkey socket connection refused")

        def set(self, key: str, value: str, ex: int | None = None) -> None:
            raise RuntimeError("Valkey socket connection refused")

    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg, valkey_client=_FailingValkey())

    embs = engine.embed_texts(["test text without valkey"])
    assert len(embs) == 1
    assert len(embs[0]) == 768
