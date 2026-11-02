"""Unit tests for EmbeddingsEngine (Ollama, OpenAI, and the EmbeddingsError a failure raises)."""

from __future__ import annotations

import contextlib
import json
import re
import sqlite3
import threading
from collections.abc import Callable
from typing import Any

import h11
import httpcore2
import httpx2
import pytest
from fakeredis import FakeServer

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config import defaults
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_SERVED_BY_HEADER,
    CONST_RAG_MAX_CHUNK_TOKENS,
)
from devops_cli.config.settings import AIConfig
from devops_cli.telemetry.instruments import EMBEDDING_CACHE_LOOKUPS_TOTAL
from devops_cli.telemetry.tracer import get_recent_spans
from devops_cli.valkey.client import ValkeyClient
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.otlp import FakeCollector
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS
from tests.web_fakes import PUBLIC_ADDRESS, scripted_resolver

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_embedder_protocol_and_fake() -> None:
    from devops_cli.ai.rag.embeddings import (
        EmbedderProtocol,
        EmbeddingsEngine,
        create_embedder,
        get_embedder_override,
        install_embedder,
        reset_embedder,
    )
    from tests.support.fakes.embeddings import FakeEmbedder

    fake = FakeEmbedder()
    assert isinstance(fake, EmbedderProtocol)
    vecs = fake.embed_texts(["hello"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 4

    install_embedder(fake)
    assert get_embedder_override() is fake
    assert create_embedder() is fake
    reset_embedder()
    assert get_embedder_override() is None
    engine = create_embedder()
    assert isinstance(engine, EmbeddingsEngine)


def test_embedder_fixture(embedder: Any) -> None:
    from devops_cli.ai.rag.embeddings import create_embedder

    client = create_embedder()
    assert client is embedder
    vectors = client.embed_texts(["test text"])
    assert len(vectors) == 1


def _fixed_vectors(width: int, value: float = 0.5) -> Any:
    """A `_dispatch_embed` stand-in that answers every text with the same vector."""
    return lambda self, texts: [[value] * width for _ in texts]


def test_no_provider_configured_raises_and_caches_nothing() -> None:
    """With no provider and no Ollama URLs, embedding raises rather than inventing a vector."""
    mock_valkey = _MockValkey()
    engine = EmbeddingsEngine(
        AIConfig(provider="custom", ollama_urls=[]), valkey_client=mock_valkey
    )

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["hello world", "test query"])

    assert (raised.value.message, raised.value.details, engine._cache.size, mock_valkey.store) == (
        f"Embedding model {engine.model} has no provider: the embedding task's provider 'custom' "
        "is not ollama, openai, copilot or gateway, and no Ollama URLs are set. "
        "Set ai.tasks.embedding.provider",
        {"model": engine.model, "provider": "custom"},
        0,
        {},
    )


def test_ollama_provider_with_no_url_raises_embeddings_error_naming_the_setting() -> None:
    """With the Ollama provider and no Ollama URL, embedding raises an error that names the setting."""
    mock_valkey = _MockValkey()
    engine = EmbeddingsEngine(
        AIConfig(provider="ollama", ollama_urls=[]), valkey_client=mock_valkey
    )

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["hello world"])

    assert (raised.value.message, raised.value.details, engine._cache.size, mock_valkey.store) == (
        f"Embedding model {engine.model} has no Ollama URL: ai.provider is 'ollama' and "
        "ai.ollama_urls is empty. Set ai.ollama_urls",
        {"model": engine.model, "provider": "ollama"},
        0,
        {},
    )


def _ollama_engine(monkeypatch: pytest.MonkeyPatch, nodes: list[str]) -> EmbeddingsEngine:
    """An Ollama engine over `nodes`."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=nodes, allow_private_network=True)
    ai_cfg.tasks.embedding.model = "bge-m3"
    return EmbeddingsEngine(ai_cfg, valkey_client=None)


def test_ollama_raises_after_every_node_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """When every node fails a single text, the error names the model and each node's failure.

    The batch of two is halved once, and the first text failing everywhere ends the call: no
    further request is sent for the second text.
    """
    posts: list[str] = []

    def fake_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        if url.endswith("/api/embed"):
            posts.append(url)
        if url.startswith("http://example.com:11434/"):
            return httpx2.Response(404, json={"error": 'model "bge-m3" not found'})
        raise httpx2.ConnectError("connection refused")

    monkeypatch.setattr(httpx2.Client, "post", fake_post)
    engine = _ollama_engine(monkeypatch, ["http://example.com:11434", "http://example.com:11435"])

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["first chunk", "second chunk"])

    assert (raised.value.message, raised.value.details["model"], len(posts)) == (
        "Embedding model bge-m3 produced no embeddings: "
        "http://example.com:11434/api/embed answered HTTP 404: "
        '{"error":"model \\"bge-m3\\" not found"}; '
        "http://example.com:11435/api/embed failed: ConnectError: connection refused",
        "bge-m3",
        4,
    )


@pytest.mark.parametrize("userinfo", ["bench-user:FAKE-2481-value", "FAKE-2481-value"])
def test_an_embedding_error_names_its_endpoint_without_the_userinfo_of_the_url(
    monkeypatch: pytest.MonkeyPatch, userinfo: str
) -> None:
    """The endpoint that an error names is the URL without its userinfo, which the client sends
    as Basic authentication: a password and a user name alone, such as a token, stay out (#2481)."""

    def fake_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        if httpx2.URL(url).port == 11434:
            return httpx2.Response(500, json={"error": "model failed"})
        raise httpx2.ConnectError("connection refused")

    monkeypatch.setattr(httpx2.Client, "post", fake_post)
    engine = _ollama_engine(
        monkeypatch, [f"http://{userinfo}@example.com:11434", "http://example.com:11435"]
    )

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["first chunk"])

    assert (raised.value.message, "FAKE-2481-value" in repr(raised.value.details)) == (
        "Embedding model bge-m3 produced no embeddings: "
        'http://example.com:11434/api/embed answered HTTP 500: {"error":"model failed"}; '
        "http://example.com:11435/api/embed failed: ConnectError: connection refused",
        False,
    )


def test_ollama_parallel_batches_raise_when_one_fails_everywhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batches embedded in parallel fail the call with the failing batch's EmbeddingsError."""

    def fake_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        if "unservable" in kwargs["json"]["input"][0]:
            return httpx2.Response(404, json={"error": "model not found"})
        return httpx2.Response(
            200, json={"embeddings": [[0.5] * 4 for _ in kwargs["json"]["input"]]}
        )

    monkeypatch.setattr(httpx2.Client, "post", fake_post)
    engine = _ollama_engine(monkeypatch, ["http://example.com:11434"])
    engine._current_batch_size = 1

    with pytest.raises(EmbeddingsError, match=re.escape("answered HTTP 404")):
        engine.embed_texts(["chunk one", "unservable chunk", "chunk three"])


@pytest.mark.parametrize(
    ("reply", "failure", "waits"),
    [
        (
            httpx2.Response(
                400, json={"error": {"message": "model 'bge-m3:latest' is not loaded"}}
            ),
            'answered HTTP 400: {"error":{"message":"model \'bge-m3:latest\' is not loaded"}}',
            0,
        ),
        (httpx2.Response(200, json={"data": []}), "returned 0 embeddings for 1 texts", 0),
        (
            httpx2.Response(200, text="<html>bad gateway</html>"),
            "returned 0 embeddings for 1 texts",
            0,
        ),
        (
            httpx2.ConnectError("connection refused"),
            "failed: ConnectError: connection refused",
            3,
        ),
    ],
    ids=["http-400", "no-data", "not-json", "unreachable"],
)
def test_gateway_failures_raise_naming_model_endpoint_and_error(
    monkeypatch: pytest.MonkeyPatch, reply: httpx2.Response | Exception, failure: str, waits: int
) -> None:
    """A gateway that answers with an error, a malformed reply or not at all raises.

    An unreachable gateway is retried: each backoff returns at once and is recorded.
    """

    def fake_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(httpx2.Client, "post", fake_post)
    backoffs: list[float] = []
    monkeypatch.setattr("time.sleep", backoffs.append)
    ai_cfg = AIConfig(provider="gateway", gateway_url="https://example.com/v1")
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-gateway", valkey_client=None)

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_query("where is the retry policy")

    assert (raised.value.message, raised.value.details["model"], len(backoffs)) == (
        "Embedding model bge-m3:latest produced no embeddings: "
        f"https://example.com/v1/embeddings {failure}",
        "bge-m3:latest",
        waits,
    )


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

    def fake_dispatch(self: object, texts: list[str]) -> list[list[float]]:
        nonlocal call_count
        call_count += 1
        return [[float(i) for i in range(4)] for _ in texts]

    monkeypatch.setattr(EmbeddingsEngine, "_dispatch_embed", fake_dispatch)
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

    def fake_dispatch(self: object, texts: list[str]) -> list[list[float]]:
        nonlocal call_count
        call_count += 1
        return [[0.5] * 8 for _ in texts]

    monkeypatch.setattr(EmbeddingsEngine, "_dispatch_embed", fake_dispatch)
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

    monkeypatch.setattr(EmbeddingsEngine, "_dispatch_embed", _fixed_vectors(384, 0.2))
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

    # Document embedding
    docs = ["Doc 1", "Doc 2"]
    res_docs = await model.embed(docs, input_type="document")
    assert len(res_docs.embeddings) == 2
    assert res_docs.inputs == docs
    assert res_docs.input_type == "document"


def test_embeddings_engine_to_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify EmbeddingsEngine.to_embedder returns an operational Pydantic AI Embedder."""
    from devops_cli.ai.agents.embeddings import Embedder

    monkeypatch.setattr(EmbeddingsEngine, "_dispatch_embed", _fixed_vectors(512, 0.3))
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
    backoffs: list[float] = []
    monkeypatch.setattr("time.sleep", backoffs.append)

    results = engine._embed_ollama(["test chunk"])
    assert len(results) == 1
    assert len(results[0]) == 384
    assert results[0] == [0.2] * 384
    assert calls == ["http://example.com:11434", "http://example.com:11435"]
    assert len(backoffs) == 1


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


def test_sub_batch_splitting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify failing large batches automatically subdivide into smaller slices."""
    ai_cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://example.com:11434"],
        allow_private_network=True,
    )
    engine = EmbeddingsEngine(ai_cfg, batch_size=4)

    # Monkeypatch node batch query: fails for batches of size >= 4, succeeds for batches < 4
    def fake_query_batch(base_url: str, batch_texts: list[str]) -> list[list[float]]:
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


def _valkey_cache_cooldown() -> float:
    """The cooldown of the breaker of the Valkey cache tier, in seconds.

    The import is local, so the module loads on a base without the default.
    """
    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS

    return DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS


def test_a_valkey_outage_turns_the_embedding_l2_cache_off_for_a_cooldown(
    monkeypatch: pytest.MonkeyPatch,
    valkey_server: FakeServer,
    valkey_client: ValkeyClient,
    clock: ClockFake,
) -> None:
    """A failed read sends texts to the provider for the cooldown; a read after it serves from Valkey.

    A first engine embeds three texts, which puts their vectors in Valkey. A second engine, with an
    empty memory cache, then embeds one of them in each phase, so each request that the provider
    receives is a text that Valkey did not answer.
    """
    sent = _serve(monkeypatch, _gateway_reply)
    EmbeddingsEngine(
        _gateway_config(), api_key="sk-gateway", valkey_client=valkey_client
    ).embed_texts(["in the outage", "in the cooldown", "after the cooldown"])
    engine = EmbeddingsEngine(_gateway_config(), api_key="sk-gateway", valkey_client=valkey_client)

    valkey_server.connected = False
    engine.embed_texts(["in the outage"])
    valkey_server.connected = True
    engine.embed_texts(["in the cooldown"])
    clock.shift(_valkey_cache_cooldown())
    engine.embed_texts(["after the cooldown"])

    assert [_inputs(request) for request in sent] == [
        ["in the outage", "in the cooldown", "after the cooldown"],
        ["in the outage"],
        ["in the cooldown"],
    ]


def test_valkey_l2_cache_query_vs_document_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify query vectors and document vectors have distinct Valkey L2 cache keys."""
    mock_valkey = _MockValkey()
    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    engine = EmbeddingsEngine(ai_cfg, valkey_client=mock_valkey)

    doc_key = engine._valkey_key("sample text", engine.model, is_query=False)
    query_key = engine._valkey_key("sample text", engine.model, is_query=True)

    assert doc_key != query_key
    assert ":d:" not in doc_key  # hex hash formatted
    # Embed document
    doc_vec = [0.1] * 64
    monkeypatch.setattr(engine, "_dispatch_embed", lambda texts: [doc_vec for _ in texts])
    engine.embed_texts(["sample text"], is_query=False)
    assert doc_key in mock_valkey.store
    assert query_key not in mock_valkey.store

    # Embed query
    query_vec = [0.2] * 64
    monkeypatch.setattr(engine, "_dispatch_embed", lambda texts: [query_vec for _ in texts])
    engine.embed_texts(["sample text"], is_query=True)
    assert query_key in mock_valkey.store


def test_an_engine_whose_valkey_refuses_embeds_and_dials_it_once_in_each_cooldown(
    monkeypatch: pytest.MonkeyPatch, unexpected_loopback_connects: list[str], clock: ClockFake
) -> None:
    """The configured Valkey refuses each connection, and the engine embeds with no Valkey tier.

    A service binds and listens on the configured port through the C socket type, as a
    port-forward to a live Valkey does, so the kernel would accept a connection. The guard refuses
    each dial and reports it, and the service sees no connection. The first refused read opens the
    breaker, so the second call dials nothing, and the call after the cooldown dials once more.
    """
    import _socket
    import socket

    from devops_cli.config.settings import reset_settings_cache

    sent = _serve(monkeypatch, _gateway_reply)
    with socket.socket() as service:
        _socket.socket.bind(service, ("127.0.0.1", 0))
        _socket.socket.listen(service)
        service.setblocking(False)
        port = service.getsockname()[1]
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_URL", f"valkey://127.0.0.1:{port}")
        reset_settings_cache()
        engine = EmbeddingsEngine(_gateway_config(), api_key="sk-gateway")
        try:
            engine.embed_texts(["first"])
            engine.embed_texts(["second"])
            dials_in_the_cooldown = list(unexpected_loopback_connects)
            clock.shift(_valkey_cache_cooldown())
            engine.embed_texts(["third"])
            dials = list(unexpected_loopback_connects)
            with pytest.raises(BlockingIOError) as raised:
                service.accept()
            assert raised.value is not None
        finally:
            unexpected_loopback_connects.clear()
    dial = f"127.0.0.1:{port} (MainThread)"
    assert (len(sent), dials_in_the_cooldown, dials) == (3, [dial], [dial, dial])


def _capture_embedding_posts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """Record (url, authorization, model) for each embeddings POST and answer with a vector."""
    calls: list[tuple[str, str, str]] = []

    def fake_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        url_str = str(url)
        if "embeddings" in url_str:
            headers = kwargs.get("headers") or {}
            payload = kwargs.get("json") or {}
            calls.append((url_str, headers.get("Authorization", ""), payload.get("model", "")))
            return httpx2.Response(200, json={"data": [{"index": 0, "embedding": [0.5] * 8}]})
        return httpx2.Response(200, json={})

    monkeypatch.setattr(httpx2.Client, "post", fake_post)
    return calls


def test_gateway_embeddings_use_gateway_url_not_global_api_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify provider gateway embeds via gateway_url with the model unchanged."""
    calls = _capture_embedding_posts(monkeypatch)
    ai_cfg = AIConfig(
        provider="gateway",
        gateway_url="http://example.com:4000/v1",
        api_base_url="http://example.com:1234/v1",
        allow_private_network=True,
    )
    ai_cfg.tasks.embedding.model = "devops-embedding"

    embs = EmbeddingsEngine(ai_cfg, api_key="sk-gateway").embed_texts(["hello"])

    assert (calls[-1], len(embs[0])) == (
        ("http://example.com:4000/v1/embeddings", "Bearer sk-gateway", "devops-embedding"),
        8,
    )


def test_gateway_embeddings_prefer_task_api_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an embedding task's own api_base_url overrides the gateway URL."""
    calls = _capture_embedding_posts(monkeypatch)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "devops-embedding"
    ai_cfg.tasks.embedding.api_base_url = "http://example.com:9000/v1"

    EmbeddingsEngine(ai_cfg, api_key="sk-gateway").embed_texts(["hello"])

    assert calls[-1][0] == "http://example.com:9000/v1/embeddings"


def test_gateway_embedding_task_ignores_global_openai_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an embedding task on the gateway never embeds via another provider's base URL."""
    calls = _capture_embedding_posts(monkeypatch)
    ai_cfg = AIConfig(
        provider="openai",
        api_base_url="https://api.example.com/v1",
        gateway_url="http://example.com:4000/v1",
        allow_private_network=True,
    )
    ai_cfg.tasks.embedding.provider = "gateway"
    ai_cfg.tasks.embedding.model = "devops-embedding"

    EmbeddingsEngine(ai_cfg, api_key="sk-gateway").embed_texts(["hello"])

    assert calls[-1][0] == "http://example.com:4000/v1/embeddings"


def test_openai_embeddings_retries_transient_connection_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient ReadError, such as a connection reset, gets one more attempt after a backoff."""
    attempts = 0

    def mock_post(_client: Any, url: str, **kwargs: Any) -> httpx2.Response:
        nonlocal attempts
        if "/embeddings" not in url:
            return httpx2.Response(200, json={}, request=httpx2.Request("POST", url))
        attempts += 1
        if attempts == 1:
            raise httpx2.ReadError("[Errno 104] Connection reset by peer")
        return httpx2.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.25] * 8}]},
            request=httpx2.Request("POST", url),
        )

    monkeypatch.setattr(httpx2.Client, "post", mock_post)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-test", valkey_client=None)
    backoffs: list[float] = []
    monkeypatch.setattr("time.sleep", backoffs.append)

    vecs = engine.embed_texts(["retry me"])

    assert (attempts, len(vecs[0]), len(backoffs)) == (2, 8, 1)


def test_openai_embeddings_retries_http_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 429 rate limit responses are retried with Retry-After backoff."""
    attempts = 0

    def mock_post(_client: Any, url: str, **kwargs: Any) -> httpx2.Response:
        nonlocal attempts
        if "/embeddings" not in url:
            return httpx2.Response(200, json={}, request=httpx2.Request("POST", url))
        attempts += 1
        if attempts == 1:
            return httpx2.Response(429, headers={"retry-after": "0"}, text="rate limited")
        return httpx2.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.75] * 8}]},
            request=httpx2.Request("POST", url),
        )

    monkeypatch.setattr(httpx2.Client, "post", mock_post)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-test", valkey_client=None)

    vecs = engine.embed_texts(["rate limit me"])

    assert (attempts, len(vecs[0])) == (2, 8)


def test_openai_embeddings_does_not_retry_http_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-transient HTTP 400 client errors fail immediately without retry loops."""
    attempts = 0

    def mock_post(_client: Any, url: str, **kwargs: Any) -> httpx2.Response:
        nonlocal attempts
        if "/embeddings" not in url:
            return httpx2.Response(200, json={}, request=httpx2.Request("POST", url))
        attempts += 1
        return httpx2.Response(400, text="Bad Request", request=httpx2.Request("POST", url))

    monkeypatch.setattr(httpx2.Client, "post", mock_post)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-test", valkey_client=None)

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["bad request"])
    assert raised.value.error_code == "EMBEDDINGS_ERROR"

    assert attempts == 1


def test_qwen3_embedding_dimension_pinned() -> None:
    """CONST_KNOWN_EMBEDDING_DIMENSIONS["qwen3-embedding"] is pinned to 1024."""
    from devops_cli.config.constants import CONST_KNOWN_EMBEDDING_DIMENSIONS

    assert CONST_KNOWN_EMBEDDING_DIMENSIONS.get("qwen3-embedding") == 1024


@pytest.mark.parametrize(
    ("model", "text", "is_query", "expected"),
    [
        ("bge-m3", "def search():", False, "def search():"),
        ("bge-m3", "def search():", True, "def search():"),
        (
            "qwen3-embedding",
            "search query",
            True,
            "Instruct: Given a code search query, retrieve relevant code or documentation\nQuery: search query",
        ),
        ("qwen3-embedding", "doc content", False, "doc content"),
        ("nomic-embed-text", "search query", True, "search_query: search query"),
        ("nomic-embed-text", "doc content", False, "search_document: doc content"),
        ("e5-base", "search query", True, "query: search query"),
        ("e5-base", "doc content", False, "passage: doc content"),
        ("other-model", "search query", True, "search query"),
        ("other-model", "doc content", False, "doc content"),
    ],
)
def test_apply_model_prefix_families(model: str, text: str, is_query: bool, expected: str) -> None:
    """Per-model prompt prefixes for bge-m3, qwen3, nomic, e5, and others."""
    from devops_cli.ai.rag.embeddings import _apply_model_prefix

    assert _apply_model_prefix(text, model, is_query=is_query) == expected


def test_embedding_cache_keys_hash_prompted_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """The L1 and Valkey keys hash the text after its prompt is applied; same text under two prompts gives two misses."""
    mock_valkey = _MockValkey()
    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    ai_cfg.tasks.embedding.model = "qwen3-embedding"
    engine = EmbeddingsEngine(ai_cfg, valkey_client=mock_valkey)

    call_count = 0

    def fake_dispatch(texts: list[str]) -> list[list[float]]:
        nonlocal call_count
        call_count += len(texts)
        return [[0.1] * 1024 for _ in texts]

    monkeypatch.setattr(engine, "_dispatch_embed", fake_dispatch)

    doc_vec = engine.embed_texts(["common content"])
    assert call_count == 1
    assert (engine._cache.hits, engine._cache.misses) == (0, 1)

    query_vec = engine.embed_query("common content")
    assert (call_count, engine._cache.hits, engine._cache.misses) == (2, 0, 2)
    assert doc_vec[0] == query_vec


def test_embeddings_429_no_deployments_is_transient() -> None:
    """A 429 'No deployments available' counts as transient."""
    from devops_cli.ai.rag.embeddings import EmbeddingsError, _reply_vectors

    res = httpx2.Response(
        429,
        text="No deployments available",
        request=httpx2.Request("POST", "http://example.com/api/embed"),
    )
    with pytest.raises(EmbeddingsError) as exc_info:
        _reply_vectors(res, "http://example.com/api/embed", 1, lambda b: b)
    assert exc_info.value.is_transient is True


# =============================================================================
# Tests: each embedding request reaches the spend ledger (#1623)
# =============================================================================

_GATEWAY_URL = "http://example.com:4000/v1"
_SERVING_BACKEND = "http://example.com:11434"
_LEDGER_ROWS = (
    "SELECT provider, server, model, prompt_tokens, completion_tokens, cached, request_type,"
    " served_by FROM ai_spend_records ORDER BY id"
)


def _serve(
    monkeypatch: pytest.MonkeyPatch, *replies: Callable[[httpx2.Request], httpx2.Response]
) -> list[httpx2.Request]:
    """Answer the engine's requests with `replies` in turn, the last one for every later request.

    httpx2's own `MockTransport` stands behind every client the engine opens, so each reply
    passes through the real client: its headers, JSON body and status reach the engine as sent.
    """
    queued = list(replies)
    sent: list[httpx2.Request] = []

    def answer(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        reply = queued.pop(0) if len(queued) > 1 else queued[0]
        return reply(request)

    transport = httpx2.MockTransport(answer)
    monkeypatch.setattr(
        httpx2.HTTPTransport,
        "handle_request",
        lambda _self, request: transport.handle_request(request),
    )
    return sent


def _inputs(request: httpx2.Request) -> list[str]:
    return list(json.loads(request.content)["input"])


def _gateway_reply(request: httpx2.Request) -> httpx2.Response:
    """A gateway `/v1/embeddings` reply that counts seven input tokens per text."""
    texts = _inputs(request)
    return httpx2.Response(
        200,
        headers={CONST_AI_GATEWAY_SERVED_BY_HEADER: _SERVING_BACKEND},
        json={
            "data": [{"index": i, "embedding": [0.5] * 4} for i in range(len(texts))],
            "usage": {"prompt_tokens": 7 * len(texts), "total_tokens": 7 * len(texts)},
        },
    )


def _ollama_reply(request: httpx2.Request) -> httpx2.Response:
    """An Ollama `/api/embed` reply that counts five input tokens per text."""
    texts = _inputs(request)
    return httpx2.Response(
        200, json={"embeddings": [[0.5] * 4 for _ in texts], "prompt_eval_count": 5 * len(texts)}
    )


def _rate_limited(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(429, headers={"retry-after": "0"}, text="rate limited")


def _gateway_config() -> AIConfig:
    ai_cfg = AIConfig(provider="gateway", gateway_url=_GATEWAY_URL, allow_private_network=True)
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    return ai_cfg


def _gateway_engine(ai_cfg: AIConfig | None = None, **options: Any) -> EmbeddingsEngine:
    config = _gateway_config() if ai_cfg is None else ai_cfg
    return EmbeddingsEngine(config, api_key="sk-gateway", valkey_client=None, **options)


def _ollama_config() -> AIConfig:
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[_SERVING_BACKEND], allow_private_network=True)
    ai_cfg.tasks.embedding.model = "bge-m3"
    return ai_cfg


def _ledger_rows(ledger: SpendLedger) -> list[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        return conn.execute(_LEDGER_ROWS).fetchall()


_GATEWAY_ROW = (
    "gateway",
    "example.com:4000",
    "bge-m3:latest",
    7,
    0,
    0,
    "embedding",
    _SERVING_BACKEND,
)


def test_a_gateway_batch_records_one_embedding_row_with_the_replys_tokens_and_backend(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """One `/v1/embeddings` request writes one ledger row with the tokens the reply counted.

    The row names the gateway as its server and the backend the gateway's header names.
    """
    sent = _serve(monkeypatch, _gateway_reply)

    _gateway_engine().embed_texts(["first chunk", "second chunk"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (
        1,
        [(*_GATEWAY_ROW[:3], 14, *_GATEWAY_ROW[4:])],
    )


def test_a_hosted_gateway_embedding_is_priced_at_the_deployment_model_that_it_names(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """A gateway reply that a hosted API served names its deployment model in
    `x-litellm-model-name`. The row is priced at that model and keeps the requested model (#2031).
    """

    def hosted_reply(request: httpx2.Request) -> httpx2.Response:
        texts = _inputs(request)
        return httpx2.Response(
            200,
            headers={
                CONST_AI_GATEWAY_SERVED_BY_HEADER: "https://api.openai.com",
                "x-litellm-model-name": "openai/text-embedding-3-small",
            },
            json={
                "data": [{"index": i, "embedding": [0.5] * 4} for i in range(len(texts))],
                "usage": {"prompt_tokens": 1_000_000, "total_tokens": 1_000_000},
            },
        )

    _serve(monkeypatch, hosted_reply)

    _gateway_engine().embed_texts(["hosted chunk"])

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT model, served_model, pricing_source, cost_usd FROM ai_spend_records"
        ).fetchall()
    assert rows == [("bge-m3:latest", "openai/text-embedding-3-small", "genai_prices:openai", 0.02)]


def test_a_batch_retried_after_http_429_records_one_row(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """A batch the gateway refuses once and then answers is one request in the ledger."""
    sent = _serve(monkeypatch, _rate_limited, _gateway_reply)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    _gateway_engine().embed_texts(["rate limited chunk"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (2, [_GATEWAY_ROW])


def test_batches_sent_in_parallel_record_one_row_each(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Each batch the engine sends in parallel writes its own row."""
    sent = _serve(monkeypatch, _gateway_reply)
    engine = _gateway_engine()
    engine._current_batch_size = 1

    engine.embed_texts(["chunk one", "chunk two", "chunk three"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (3, [_GATEWAY_ROW] * 3)


def test_an_ollama_batch_records_the_tokens_its_reply_counted(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """An Ollama `/api/embed` batch takes its tokens from the reply's `prompt_eval_count`."""
    _serve(monkeypatch, _ollama_reply)

    EmbeddingsEngine(_ollama_config(), valkey_client=None).embed_texts(["one", "two"])

    assert _ledger_rows(spend_ledger) == [
        ("ollama", "example.com:11434", "bge-m3", 10, 0, 0, "embedding", None)
    ]


def test_an_ollama_batch_names_its_server_without_the_password_of_its_url(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger, otlp: FakeCollector
) -> None:
    """A configured URL with userinfo names its server by host and port in the ledger, the
    counters and the batch span, and no record holds the password."""
    _serve(monkeypatch, _ollama_reply)
    ai_cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://user:pw@example.com:11434"],
        allow_private_network=True,
    )
    ai_cfg.tasks.embedding.model = "bge-m3"

    EmbeddingsEngine(ai_cfg, valkey_client=None).embed_texts(["one"])

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute("SELECT server, backend_info FROM ai_spend_records").fetchall()
    (span,) = [s for s in get_recent_spans() if s["name"] == "ai.rag.ollama_embed_batch"]
    span_server = {
        a["key"]: next(iter(a["value"].values()))
        for a in span["attributes"]
        if a["key"].startswith("server.")
    }
    counter_servers = {
        attrs["server"] for attrs, _value in otlp.points("devops_cli_ai_requests_total")
    }
    assert (rows, counter_servers, span_server) == (
        [("example.com:11434", "ollama (example.com:11434)")],
        {"example.com:11434"},
        {"server.address": "example.com", "server.port": "11434"},
    )


def test_a_call_the_cache_answers_records_no_request(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Texts the cache answers send no request, so they add no row and no tokens."""
    sent = _serve(monkeypatch, _gateway_reply)
    engine = _gateway_engine()

    engine.embed_texts(["cached chunk"])
    engine.embed_texts(["cached chunk"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (1, [_GATEWAY_ROW])


@pytest.mark.parametrize(
    ("make_engine", "reply", "row"),
    [
        (_gateway_engine, _gateway_reply, _GATEWAY_ROW),
        (
            lambda: EmbeddingsEngine(_ollama_config(), valkey_client=None),
            _ollama_reply,
            ("ollama", "example.com:11434", "bge-m3", 5, 0, 0, "embedding", None),
        ),
    ],
    ids=["gateway", "ollama"],
)
def test_the_dimension_probe_records_its_request(
    monkeypatch: pytest.MonkeyPatch,
    spend_ledger: SpendLedger,
    make_engine: Callable[[], EmbeddingsEngine],
    reply: Callable[[httpx2.Request], httpx2.Response],
    row: tuple[Any, ...],
) -> None:
    """The request that probes the model's dimension is an embedding request like any other."""
    _serve(monkeypatch, reply)

    dimension = make_engine().dimension

    assert (dimension, _ledger_rows(spend_ledger)) == (4, [row])


@pytest.mark.anyio
@pytest.mark.parametrize("wrapper", ["ollama", "engine"])
async def test_the_embedding_models_report_the_tokens_the_provider_counted(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger, wrapper: str
) -> None:
    """Both pydantic-ai embedding models report the reply's token count, not an estimate."""
    from devops_cli.ai.agents.embeddings import EngineEmbeddingModel
    from devops_cli.ai.rag.embeddings import OllamaEmbeddingModel

    _serve(monkeypatch, _ollama_reply)
    model = (
        OllamaEmbeddingModel("bge-m3", ai_config=_ollama_config())
        if wrapper == "ollama"
        else EngineEmbeddingModel(EmbeddingsEngine(_ollama_config(), valkey_client=None))
    )

    result = await model.embed(["three words here", "two words"], input_type="document")

    assert result.usage.input_tokens == 10


# =============================================================================
# Tests: parallel batches share one HTTP client, and a slow batch gets its reply (#2011)
# =============================================================================

# The slowest reply that a gateway tier gave to an embedding batch on 2026-10-23: 76 s, on
# ollama-48gib-slow. On that day, the read timeout of 30 s stopped 70 other batches at 29 to 30 s.
_SLOWEST_MEASURED_BATCH_SECONDS = 76.0
_REPLY_WIDTH = 4


def _request_texts(request: bytes) -> list[str]:
    """The texts of one `/v1/embeddings` request, as the HTTP/1.1 parser of a server reads them."""
    server = h11.Connection(h11.SERVER)
    server.receive_data(request)
    body = b""
    while not isinstance(event := server.next_event(), h11.EndOfMessage):
        if event is h11.NEED_DATA:
            pytest.fail("The engine read the reply before it wrote all of its request")
        if isinstance(event, h11.Data):
            body += event.data
    return list(json.loads(body)["input"])


def _reply_bytes(texts: list[str], value: float = 0.5) -> bytes:
    """The HTTP/1.1 reply of a gateway to `texts`: one vector of `value` for each text."""
    body = json.dumps(
        {
            "data": [{"index": i, "embedding": [value] * _REPLY_WIDTH} for i in range(len(texts))],
            "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)},
        }
    ).encode()
    head = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n"
    return f"{head}\r\n".encode() + body


class _Gateway:
    """The gateway side of each connection that the HTTP client of the engine dials.

    `answer` gets the texts and the read timeout of one request. It gives the reply bytes, or it
    raises the timeout or network error that a socket read raises. `requests` holds the texts of
    each request and `read_timeouts` holds its read timeout, in the order that they came.
    `closed_before_reply` holds the first text of each request whose reply came after the client
    closed the connection.
    """

    def __init__(self, answer: Callable[[list[str], float | None], bytes]) -> None:
        self.answer = answer
        self.requests: list[list[str]] = []
        self.read_timeouts: list[float | None] = []
        self.closed_before_reply: list[str] = []
        self.lock = threading.Lock()

    def sent(self) -> list[str]:
        """The first text of each request, in the order that they came."""
        with self.lock:
            return [texts[0] for texts in self.requests]


class _GatewayConnection(httpcore2.NetworkStream):
    """One connection to `_Gateway`, in place of the socket that the dial of httpcore2 opens.

    The first read after a request gets the reply from the gateway. If the client closed the
    connection before the reply came, the read fails as a read on a closed socket fails: errno 9.
    """

    def __init__(self, gateway: _Gateway) -> None:
        self._gateway = gateway
        self._request = bytearray()
        self._reply = b""
        self._closed = False

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._request.extend(buffer)

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        if self._request:
            texts = _request_texts(bytes(self._request))
            self._request.clear()
            with self._gateway.lock:
                self._gateway.requests.append(texts)
                self._gateway.read_timeouts.append(timeout)
            self._reply = self._gateway.answer(texts, timeout)
            if self._closed:
                with self._gateway.lock:
                    self._gateway.closed_before_reply.append(texts[0])
        if self._closed:
            raise httpcore2.ReadError("[Errno 9] Bad file descriptor")
        chunk, self._reply = self._reply[:max_bytes], self._reply[max_bytes:]
        return chunk

    def close(self) -> None:
        self._closed = True

    def get_extra_info(self, info: str) -> Any:
        return None


def _dial_gateway(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[list[str], float | None], bytes]
) -> _Gateway:
    """Connect each dial of the HTTP client of the engine to one `_Gateway`.

    The httpx2 client of the engine, its egress check and the connection pool of httpcore2 stay
    real. The host of the gateway URL answers a public address to the lookup of the connect, and
    only the socket under each connection is the gateway's.
    """
    gateway = _Gateway(answer)
    scripted_resolver(monkeypatch, {httpx2.URL(_GATEWAY_URL).host: [[PUBLIC_ADDRESS]]})
    monkeypatch.setattr(
        httpcore2.SyncBackend,
        "connect_tcp",
        lambda _backend, *_args, **_kwargs: _GatewayConnection(gateway),
    )
    return gateway


def _wait_for(event: threading.Event, what: str) -> None:
    if not event.wait(THREAD_HANDOFF_BOUND_SECONDS):
        pytest.fail(f"The gateway waited {THREAD_HANDOFF_BOUND_SECONDS:g} s for {what}")


@pytest.mark.usefixtures("clock")
def test_a_batch_that_times_out_leaves_the_parallel_batches_their_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch that times out does not close the connections of the batches parallel to it.

    Four batches of one text go out in parallel. The gateway keeps the first batch without a
    reply until all four batches are sent, and then the read of that batch times out. The gateway
    replies to the other three batches only after the engine sends the first batch again. Each of
    the three batches reads its reply on its own connection. Thus the gateway gets five requests,
    and no reply comes to a closed connection.
    """
    names = [f"batch {index}" for index in range(4)]
    every_batch_sent = threading.Event()
    first_batch_sent_again = threading.Event()

    def answer(texts: list[str], _read_timeout: float | None) -> bytes:
        name, sent = texts[0], gateway.sent()
        if set(sent) == set(names):
            every_batch_sent.set()
        if name == names[0] and sent.count(name) == 1:
            _wait_for(every_batch_sent, "the first request of each batch")
            raise httpcore2.ReadTimeout("timed out")
        if name == names[0]:
            first_batch_sent_again.set()
        elif sent.count(name) == 1:
            _wait_for(first_batch_sent_again, "the second request of the first batch")
        return _reply_bytes(texts, value=float(names.index(name)))

    gateway = _dial_gateway(monkeypatch, answer)

    vectors = _gateway_engine(batch_size=1).embed_texts(names)

    assert (vectors, sorted(gateway.sent()), gateway.closed_before_reply) == (
        [[float(index)] * _REPLY_WIDTH for index in range(len(names))],
        [names[0], *names],
        [],
    )


@pytest.mark.usefixtures("clock")
def test_the_largest_intake_batch_gets_a_reply_as_slow_as_the_slowest_measured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The read timeout of a gateway batch is longer than the slowest reply measured for a batch.

    Intake sends batches of up to `DEFAULT_RAG_EMBEDDING_BATCH_SIZE` texts, and it cuts each text
    to `DEFAULT_ROADMAP_INTAKE_TEXT_CHARS` characters. The gateway replies to a batch of that size
    after 76 s, as the slowest tier did on 2026-10-23, so a request with a shorter read timeout
    times out. The batch gets its reply to its first request, which waits the named default.
    """

    def answer(texts: list[str], read_timeout: float | None) -> bytes:
        if read_timeout is not None and read_timeout < _SLOWEST_MEASURED_BATCH_SECONDS:
            raise httpcore2.ReadTimeout("timed out")
        return _reply_bytes(texts)

    gateway = _dial_gateway(monkeypatch, answer)
    texts = [
        f"item {index} ".ljust(defaults.DEFAULT_ROADMAP_INTAKE_TEXT_CHARS, "x")
        for index in range(defaults.DEFAULT_RAG_EMBEDDING_BATCH_SIZE)
    ]

    vectors = _gateway_engine().embed_texts(texts)

    assert (len(vectors), gateway.requests, gateway.read_timeouts) == (
        defaults.DEFAULT_RAG_EMBEDDING_BATCH_SIZE,
        [texts],
        [defaults.DEFAULT_RAG_EMBEDDING_BATCH_TIMEOUT],
    )


def test_a_configured_embedding_timeout_is_the_read_timeout_of_a_gateway_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ai.tasks.embedding.timeout` sets the read timeout of a gateway batch, also below 30 s."""
    gateway = _dial_gateway(monkeypatch, lambda texts, _read_timeout: _reply_bytes(texts))
    ai_cfg = _gateway_config()
    ai_cfg.tasks.embedding.timeout = 10.0

    _gateway_engine(ai_cfg).embed_texts(["one text"])

    assert gateway.read_timeouts == [10.0]


# =============================================================================
# Tests: a slow batch halves the batch size once for the size it was sent at, and the size grows
# back only after a cooldown and below a margin (#2072)
# =============================================================================

_SLOW_BATCH_SECONDS = defaults.DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS + 1.0


class _TimedNode:
    """The replies of one Ollama node, each taking the next of `seconds` on the fake clock.

    The last of `seconds` repeats for every later reply. A test sets `seconds` again between calls.
    """

    def __init__(self, clock: ClockFake, *seconds: float) -> None:
        self.clock = clock
        self.seconds = list(seconds)

    def reply(self, request: httpx2.Request) -> httpx2.Response:
        taken = self.seconds.pop(0) if len(self.seconds) > 1 else self.seconds[0]
        self.clock.shift(taken)
        return _ollama_reply(request)


def _batch_sizes(
    engine: EmbeddingsEngine, sent: list[httpx2.Request], call: int, texts: int
) -> list[int]:
    """Embed `texts` new texts in one call, and give the size of each batch it sent, largest first."""
    sent.clear()
    engine.embed_texts([f"call {call} text {index}" for index in range(texts)])
    return sorted((len(_inputs(request)) for request in sent), reverse=True)


def test_parallel_slow_batches_halve_the_batch_size_once_for_the_size_they_were_sent_at(
    monkeypatch: pytest.MonkeyPatch, clock: ClockFake
) -> None:
    """A slow batch halves the batch size only when it holds no more texts than the size in use.

    Each call cuts eight texts at the size in use, and two workers send the batches in parallel.
    Each reply takes longer than the latency threshold. The first slow batch of a call halves the
    size. The other batches of that call hold more texts than the halved size, so they do not
    halve it again. At one text, the size stays at one text.
    """
    sent = _serve(monkeypatch, _TimedNode(clock, _SLOW_BATCH_SECONDS).reply)
    engine = EmbeddingsEngine(_ollama_config(), valkey_client=None, batch_size=4)

    sizes = [_batch_sizes(engine, sent, call, 8) for call in range(4)]

    assert sizes == [[4, 4], [2, 2, 2, 2], [1] * 8, [1] * 8]


def test_parallel_batches_that_time_out_on_an_ollama_node_halve_the_batch_size_once(
    monkeypatch: pytest.MonkeyPatch, clock: ClockFake
) -> None:
    """Two batches of four texts time out in parallel on the one node, and the size halves once.

    The two batches wait their backoff at the same time, so both timeouts come before a reply.
    Then the engine sends each batch again as two halves, and the node replies at once. These
    replies come in the cooldown, so the size stays at two texts for the next call.
    """

    def reply(request: httpx2.Request) -> httpx2.Response:
        texts = _inputs(request)
        if len(texts) == 4 and texts[0].startswith("call 0 "):
            raise httpx2.ReadTimeout("timed out", request=request)
        return _ollama_reply(request)

    sent = _serve(monkeypatch, reply)
    engine = EmbeddingsEngine(_ollama_config(), valkey_client=None, batch_size=4)

    with clock.concurrent_sleeps(2):
        first_call = _batch_sizes(engine, sent, 0, 8)
    second_call = _batch_sizes(engine, sent, 1, 8)

    assert [first_call, second_call] == [[4, 4, 2, 2, 2, 2], [2, 2, 2, 2]]


def test_parallel_gateway_batches_that_time_out_halve_the_batch_size_once(
    monkeypatch: pytest.MonkeyPatch, clock: ClockFake
) -> None:
    """Two gateway batches of four texts time out in parallel, and the size halves once.

    The first request of each batch times out, the two batches wait their backoff at the same
    time, and the second request of each batch gets its reply. The next call cuts its texts into
    batches of two texts.
    """
    timed_out: set[str] = set()
    lock = threading.Lock()

    def reply(request: httpx2.Request) -> httpx2.Response:
        first_text = _inputs(request)[0]
        with lock:
            first_request = first_text not in timed_out
            timed_out.add(first_text)
        if first_request and first_text.startswith("call 0 "):
            raise httpx2.ReadTimeout("timed out", request=request)
        return _gateway_reply(request)

    sent = _serve(monkeypatch, reply)
    engine = _gateway_engine(batch_size=4)

    with clock.concurrent_sleeps(2):
        first_call = _batch_sizes(engine, sent, 0, 8)
    second_call = _batch_sizes(engine, sent, 1, 8)

    assert [first_call, second_call] == [[4, 4, 4, 4], [2, 2, 2, 2]]


def test_fast_batches_grow_the_batch_size_once_per_cooldown_up_to_the_configured_size(
    monkeypatch: pytest.MonkeyPatch, clock: ClockFake
) -> None:
    """After a change of the batch size, fast batches grow it only when the cooldown has passed.

    A slow batch halves the size from six texts to three. Fast batches in the cooldown do not
    grow it. After the cooldown, two fast batches grow it by two texts, and the cooldown starts
    again. The size grows to the configured six texts, and not more.
    """
    node = _TimedNode(clock, _SLOW_BATCH_SECONDS)
    sent = _serve(monkeypatch, node.reply)
    engine = EmbeddingsEngine(_ollama_config(), valkey_client=None, batch_size=6)
    cooldown = defaults.DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS

    sizes = [_batch_sizes(engine, sent, 0, 6)]
    node.seconds = [0.0]
    sizes.append(_batch_sizes(engine, sent, 1, 6))
    clock.shift(cooldown)
    sizes.append(_batch_sizes(engine, sent, 2, 6))
    sizes.append(_batch_sizes(engine, sent, 3, 6))
    clock.shift(cooldown)
    sizes.append(_batch_sizes(engine, sent, 4, 6))
    clock.shift(cooldown)
    sizes.append(_batch_sizes(engine, sent, 5, 12))

    assert sizes == [[6], [3, 3], [3, 3], [5, 1], [5, 1], [6, 6]]


def test_only_a_batch_within_the_margin_below_the_latency_threshold_counts_as_fast(
    monkeypatch: pytest.MonkeyPatch, clock: ClockFake
) -> None:
    """A batch counts toward growth only when it takes at most the margin share of the threshold.

    One worker sends the batches, so each latency is the latency of one batch. After a decrease
    and the cooldown, a batch at the margin counts as fast. A batch slower than the margin but not
    slower than the threshold stops the run of fast batches. The size grows only after two fast
    batches in a row.
    """
    ai_cfg = _ollama_config()
    ai_cfg.ollama_max_parallel = 1
    node = _TimedNode(clock, _SLOW_BATCH_SECONDS)
    sent = _serve(monkeypatch, node.reply)
    engine = EmbeddingsEngine(ai_cfg, valkey_client=None, batch_size=4)
    threshold = defaults.DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS
    margin = threshold * defaults.DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO

    sizes = [_batch_sizes(engine, sent, 0, 4)]
    clock.shift(defaults.DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS)
    node.seconds = [margin, (margin + threshold) / 2, margin]
    sizes.append(_batch_sizes(engine, sent, 1, 6))
    node.seconds = [margin]
    sizes.append(_batch_sizes(engine, sent, 2, 6))
    sizes.append(_batch_sizes(engine, sent, 3, 6))

    assert sizes == [[4], [2, 2, 2], [2, 2, 2], [4, 2]]


# =============================================================================
# Tests: direct Ollama embedding calls pass num_ctx option (#2089)
# =============================================================================


def test_ollama_embed_batch_sends_num_ctx_option(monkeypatch: pytest.MonkeyPatch) -> None:
    """A direct Ollama embedding batch request passes options.num_ctx defaulting to 8192."""
    sent = _serve(monkeypatch, _ollama_reply)
    engine = EmbeddingsEngine(_ollama_config(), valkey_client=None)

    engine.embed_texts(["hello world"])

    assert len(sent) == 1
    body = json.loads(sent[0].content)
    assert body.get("options") == {"num_ctx": CONST_RAG_MAX_CHUNK_TOKENS}


def test_ollama_embed_batch_sends_configured_num_ctx(monkeypatch: pytest.MonkeyPatch) -> None:
    """A direct Ollama embedding batch request passes configured num_ctx."""
    sent = _serve(monkeypatch, _ollama_reply)
    ai_cfg = _ollama_config()
    ai_cfg.tasks.embedding.num_ctx = 4096
    engine = EmbeddingsEngine(ai_cfg, valkey_client=None)

    engine.embed_texts(["hello world"])

    assert len(sent) == 1
    body = json.loads(sent[0].content)
    assert body.get("options") == {"num_ctx": 4096}


def test_probe_ollama_embed_dimension_sends_num_ctx_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Probing Ollama embed dimension passes options.num_ctx."""
    sent = _serve(monkeypatch, _ollama_reply)
    engine = EmbeddingsEngine(_ollama_config(), valkey_client=None)
    with httpx2.Client() as client:
        dim = engine._probe_ollama_embed_dimension(client, _SERVING_BACKEND)

    assert dim == 4
    assert len(sent) == 1
    body = json.loads(sent[0].content)
    assert body.get("options") == {"num_ctx": CONST_RAG_MAX_CHUNK_TOKENS}


# =============================================================================
# Tests: embedding cache lookups are one counter (#817)
# =============================================================================


def _lookups(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    """The points of the embedding cache lookup counter, hits before misses."""
    return sorted(
        otlp.points(EMBEDDING_CACHE_LOOKUPS_TOTAL.name), key=lambda point: point[0]["result"]
    )


def test_an_embedding_request_counts_each_text_once_by_its_cache_result(
    monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector
) -> None:
    """Three texts that the memory cache holds and two that it does not are three hits and two
    misses, each sent one time."""
    _serve(monkeypatch, _gateway_reply)
    engine = _gateway_engine()
    engine.embed_texts(["first", "second", "third"])
    otlp.clear()

    engine.embed_texts(["first", "second", "third", "fourth", "fifth"])

    assert _lookups(otlp) == [
        ({"result": "hit", "tier": "memory"}, 3.0),
        ({"result": "miss"}, 2.0),
    ]


def test_a_text_that_only_valkey_holds_counts_as_a_valkey_hit(
    monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector, valkey_client: ValkeyClient
) -> None:
    """A second process finds the text in Valkey and not in its own memory cache."""
    _serve(monkeypatch, _gateway_reply)
    config = _gateway_config()
    EmbeddingsEngine(config, api_key="sk-gateway", valkey_client=valkey_client).embed_texts(
        ["shared chunk"]
    )
    otlp.clear()

    EmbeddingsEngine(config, api_key="sk-gateway", valkey_client=valkey_client).embed_texts(
        ["shared chunk"]
    )

    assert _lookups(otlp) == [({"result": "hit", "tier": "valkey"}, 1.0)]


def test_an_openai_engine_without_a_key_reads_it_from_the_keyring(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    keyring_store.values["ai_api_key"] = "sk-from-keyring"

    engine = EmbeddingsEngine(
        AIConfig(provider="openai", allow_private_network=True), valkey_client=None
    )

    assert engine.api_key == "sk-from-keyring"
