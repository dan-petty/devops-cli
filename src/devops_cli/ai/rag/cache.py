"""In-memory SHA-256 keyed embedding cache for chunk deduplication and acceleration."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict

from pydantic import BaseModel

from devops_cli.telemetry import record_metric


class EmbeddingCacheStats(BaseModel):
    """Telemetry and hit-rate statistics for the in-memory embedding cache."""

    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 10000
    hit_rate: float = 0.0


class EmbeddingCache:
    """Thread-safe LRU embedding vector cache keyed by text content and model hash."""

    def __init__(self, max_size: int = 10000) -> None:
        self.max_size = max(1, max_size)
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _compute_key(model: str, text: str) -> str:
        """Generate deterministic SHA-256 cache key from model identifier and text content."""
        hasher = hashlib.sha256()
        hasher.update(model.encode("utf-8"))
        hasher.update(b"::")
        hasher.update(text.encode("utf-8"))
        return hasher.hexdigest()

    def get(self, model: str, text: str) -> list[float] | None:
        """Retrieve cached embedding vector if present, updating LRU recency."""
        key = self._compute_key(model, text)
        with self._lock:
            if key in self._cache:
                self._hits += 1
                self._cache.move_to_end(key)
                vec = list(self._cache[key])
                record_metric("rag.embedding_cache.hit", 1.0, attributes={"model": model})
                return vec
            self._misses += 1
            record_metric("rag.embedding_cache.miss", 1.0, attributes={"model": model})
            return None

    def set(self, model: str, text: str, vector: list[float]) -> None:
        """Store embedding vector in cache, evicting least recently used entries if full."""
        key = self._compute_key(model, text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = list(vector)
                return

            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = list(vector)

    def clear(self) -> None:
        """Clear all cached embeddings and reset hit/miss counters."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> EmbeddingCacheStats:
        """Compute current cache statistics and hit-rate percentage."""
        with self._lock:
            total = self._hits + self._misses
            rate = (self._hits / total) if total > 0 else 0.0
            return EmbeddingCacheStats(
                hits=self._hits,
                misses=self._misses,
                size=len(self._cache),
                max_size=self.max_size,
                hit_rate=round(rate, 4),
            )


_GLOBAL_EMBEDDING_CACHE = EmbeddingCache()


def get_embedding_cache() -> EmbeddingCache:
    """Retrieve global singleton embedding cache instance."""
    return _GLOBAL_EMBEDDING_CACHE
