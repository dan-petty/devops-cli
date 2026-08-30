"""Unit tests for in-memory SHA-256 keyed EmbeddingCache."""

from __future__ import annotations

from devops_cli.ai.rag.cache import EmbeddingCache


def test_embedding_cache_set_and_get() -> None:
    """EmbeddingCache should store and retrieve vectors keyed by model and text hash."""
    cache = EmbeddingCache(max_size=100)
    vec = [0.1, 0.2, 0.3, 0.4]

    assert cache.get("model-a", "hello world") is None

    cache.set("model-a", "hello world", vec)
    retrieved = cache.get("model-a", "hello world")

    assert retrieved == vec
    stats = cache.stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.size == 1


def test_embedding_cache_lru_eviction() -> None:
    """EmbeddingCache should evict least recently used entries when capacity is exceeded."""
    cache = EmbeddingCache(max_size=2)
    cache.set("m", "chunk1", [1.0])
    cache.set("m", "chunk2", [2.0])

    # Touch chunk1 to make chunk2 LRU
    assert cache.get("m", "chunk1") == [1.0]

    # Insert chunk3, which should evict chunk2
    cache.set("m", "chunk3", [3.0])

    assert cache.get("m", "chunk1") == [1.0]
    assert cache.get("m", "chunk2") is None
    assert cache.get("m", "chunk3") == [3.0]


def test_embedding_cache_clear() -> None:
    """clear() should empty the cache and reset counters."""
    cache = EmbeddingCache()
    cache.set("m", "text", [1.0])
    cache.get("m", "text")
    cache.clear()

    stats = cache.stats()
    assert stats.size == 0
    assert stats.hits == 0
    assert stats.misses == 0
