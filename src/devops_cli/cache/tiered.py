"""Tiered L1/L2 cache with unified key namespacing.

Cache helpers had grown independently across the AI, RAG, and review modules, each
formatting its own key prefix and deciding its own TTL. Two call sites could therefore
write the same logical value under different keys, and nothing could invalidate a
namespace as a whole.

L1 is a bounded in-process LRU serving repeat reads within a command without touching the
network; L2 is Valkey, shared across processes and machines.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar

from devops_cli.config.constants import (
    CONST_CACHE_KEY_SEPARATOR,
    CONST_CACHE_NAMESPACE_ROOT,
    CONST_CACHE_TIER_L1,
    CONST_CACHE_TIER_L1_L2,
    CONST_CACHE_TIER_L2,
    CONST_CACHE_TIERS,
)
from devops_cli.config.defaults import (
    DEFAULT_CACHE_L1_MAX_ENTRIES,
    DEFAULT_CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


# =============================================================================
# Key Namespacing
# =============================================================================


def build_cache_key(namespace: str, *parts: Any) -> str:
    """Build a namespaced cache key from its component parts.

    One key builder for every cache means a namespace can be invalidated wholesale and
    two call sites cannot disagree about where a value lives.
    """
    segments = [CONST_CACHE_NAMESPACE_ROOT, namespace]
    segments.extend(str(part) for part in parts if str(part))
    return CONST_CACHE_KEY_SEPARATOR.join(segments)


def digest_key(namespace: str, payload: Any) -> str:
    """Build a namespaced key whose final segment is a stable digest of a payload.

    Used when the natural key is unbounded — a prompt, a file body, an embedding input —
    so keys stay short and free of characters the wire protocol would have to escape.
    """
    if isinstance(payload, str):
        material = payload
    else:
        material = json.dumps(payload, sort_keys=True, default=str)
    return build_cache_key(namespace, hashlib.sha256(material.encode("utf-8")).hexdigest())


# =============================================================================
# Statistics
# =============================================================================


@dataclass
class CacheStats:
    """Hit and miss counters, separated by tier so their value is individually visible."""

    l1_hits: int = 0
    l2_hits: int = 0
    misses: int = 0
    evictions: int = 0
    writes: int = 0

    @property
    def total_lookups(self) -> int:
        """Total number of reads served."""
        return self.l1_hits + self.l2_hits + self.misses

    @property
    def hit_ratio(self) -> float:
        """Fraction of reads answered from either tier."""
        total = self.total_lookups
        return round((self.l1_hits + self.l2_hits) / total, 4) if total else 0.0


# =============================================================================
# L1: In-process LRU
# =============================================================================


class LRUCache:
    """Bounded, thread-safe, TTL-aware in-process cache."""

    def __init__(self, max_entries: int = DEFAULT_CACHE_L1_MAX_ENTRIES) -> None:
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_entries = max(1, max_entries)
        self._lock = threading.Lock()
        self.evictions = 0

    def get(self, key: str) -> Any | None:
        """Return a live value, refreshing its recency, or None when absent or expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        """Store a value, evicting the least recently used entry when at capacity."""
        with self._lock:
            self._entries.pop(key, None)
            self._entries[key] = (time.monotonic() + ttl, value)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
                self.evictions += 1

    def delete(self, key: str) -> bool:
        """Remove one entry, reporting whether it was present."""
        with self._lock:
            return self._entries.pop(key, None) is not None

    def delete_namespace(self, prefix: str) -> int:
        """Remove every entry under a key prefix."""
        with self._lock:
            matched = [key for key in self._entries if key.startswith(prefix)]
            for key in matched:
                del self._entries[key]
            return len(matched)

    def clear(self) -> None:
        """Discard every entry."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


# =============================================================================
# Tiered Cache
# =============================================================================


class TieredCache:
    """An in-process LRU backed by Valkey, presented as one cache.

    A read checks L1, then L2, promoting an L2 hit into L1 so a repeated lookup within
    the same command costs nothing. Every L2 failure degrades to a miss rather than
    propagating: a cache is an optimisation, and an unreachable one must not break the
    operation it was accelerating.
    """

    def __init__(
        self,
        backend: Any | None = None,
        l1_max_entries: int = DEFAULT_CACHE_L1_MAX_ENTRIES,
        default_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        """Build a tiered cache.

        `backend` is anything exposing ``execute(*parts)`` — a connection pool or a direct
        client. When omitted, the shared process-wide pool is resolved on first use.
        """
        self.l1 = LRUCache(max_entries=l1_max_entries)
        self.default_ttl = default_ttl
        self.stats = CacheStats()
        self._backend = backend

    def _resolve_backend(self) -> Any | None:
        """Resolve the L2 backend lazily, tolerating an unconfigured environment."""
        if self._backend is not None:
            return self._backend
        try:
            from devops_cli.valkey.pool import get_pool

            self._backend = get_pool()
        except Exception as exc:
            logger.debug("Valkey backend unavailable; operating L1-only: %s", exc)
            return None
        return self._backend

    def _l2_get(self, key: str) -> Any | None:
        """Read one key from Valkey, decoding the stored JSON envelope."""
        backend = self._resolve_backend()
        if backend is None:
            return None
        try:
            raw = backend.execute("GET", key)
        except Exception as exc:
            logger.debug("Valkey read failed for %s: %s", key, exc)
            return None
        return _decode(raw)

    def _l2_set(self, key: str, value: Any, ttl: float) -> None:
        """Write one key to Valkey with an expiry."""
        backend = self._resolve_backend()
        if backend is None:
            return
        try:
            backend.execute("SET", key, json.dumps(value, default=str), "EX", int(ttl))
        except Exception as exc:
            logger.debug("Valkey write failed for %s: %s", key, exc)

    def get(self, key: str) -> Any | None:
        """Read through L1 then L2, promoting an L2 hit into L1."""
        value = self.l1.get(key)
        if value is not None:
            self.stats.l1_hits += 1
            return value

        value = self._l2_get(key)
        if value is not None:
            self.stats.l2_hits += 1
            self.l1.set(key, value, self.default_ttl)
            return value

        self.stats.misses += 1
        return None

    def set(
        self, key: str, value: Any, ttl: float | None = None, tier: str = CONST_CACHE_TIER_L1_L2
    ) -> None:
        """Write a value to the requested tiers."""
        if tier not in CONST_CACHE_TIERS:
            raise ValueError(
                f"Unknown cache tier '{tier}'. Choose from {sorted(CONST_CACHE_TIERS)}."
            )

        effective_ttl = self.default_ttl if ttl is None else ttl
        self.stats.writes += 1
        if tier in (CONST_CACHE_TIER_L1, CONST_CACHE_TIER_L1_L2):
            self.l1.set(key, value, effective_ttl)
        if tier in (CONST_CACHE_TIER_L2, CONST_CACHE_TIER_L1_L2):
            self._l2_set(key, value, effective_ttl)

    def get_many(self, keys: Iterable[str]) -> dict[str, Any]:
        """Read many keys, fetching every L1 miss from L2 in a single round trip.

        This is the batching path for mass embedding and AST symbol lookups, where N
        sequential reads would otherwise cost N network round trips.
        """
        requested = list(keys)
        found: dict[str, Any] = {}
        pending: list[str] = []

        for key in requested:
            value = self.l1.get(key)
            if value is not None:
                self.stats.l1_hits += 1
                found[key] = value
            else:
                pending.append(key)

        if not pending:
            return found

        backend = self._resolve_backend()
        if backend is None:
            self.stats.misses += len(pending)
            return found

        try:
            raw_values = backend.execute("MGET", *pending)
        except Exception as exc:
            logger.debug("Valkey batch read failed for %d key(s): %s", len(pending), exc)
            self.stats.misses += len(pending)
            return found

        values = raw_values if isinstance(raw_values, list) else [raw_values]
        for key, raw in zip(pending, values, strict=False):
            decoded = _decode(raw)
            if decoded is None:
                self.stats.misses += 1
                continue
            self.stats.l2_hits += 1
            self.l1.set(key, decoded, self.default_ttl)
            found[key] = decoded
        return found

    def delete(self, key: str) -> bool:
        """Remove a key from both tiers."""
        removed = self.l1.delete(key)
        backend = self._resolve_backend()
        if backend is not None:
            try:
                removed = bool(backend.execute("DEL", key)) or removed
            except Exception as exc:
                logger.debug("Valkey delete failed for %s: %s", key, exc)
        return removed

    def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate every key under a namespace across both tiers.

        Namespaced invalidation is what the ad-hoc prefixes could not express: each call
        site formatted its own keys, so nothing could clear a logical group as a whole.
        """
        prefix = build_cache_key(namespace)
        removed = self.l1.delete_namespace(prefix)

        backend = self._resolve_backend()
        if backend is None:
            return removed
        try:
            keys = backend.execute("KEYS", f"{prefix}{CONST_CACHE_KEY_SEPARATOR}*")
            names = [k.decode() if isinstance(k, bytes) else str(k) for k in (keys or [])]
            if names:
                removed += int(backend.execute("DEL", *names) or 0)
        except Exception as exc:
            logger.debug("Valkey namespace invalidation failed for %s: %s", namespace, exc)
        return removed

    def get_stats(self) -> CacheStats:
        """Snapshot cache counters, including L1 evictions."""
        return CacheStats(
            l1_hits=self.stats.l1_hits,
            l2_hits=self.stats.l2_hits,
            misses=self.stats.misses,
            evictions=self.l1.evictions,
            writes=self.stats.writes,
        )


def _decode(raw: Any) -> Any | None:
    """Decode a stored cache envelope, treating unreadable payloads as a miss."""
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError, TypeError:
        return text or None


_DEFAULT_CACHE: TieredCache | None = None


def get_cache() -> TieredCache:
    """Return the process-wide tiered cache, constructing it on first use."""
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = TieredCache()
    return _DEFAULT_CACHE


def reset_cache() -> None:
    """Drop the process-wide cache, for clean test isolation."""
    global _DEFAULT_CACHE
    _DEFAULT_CACHE = None


def cached(
    namespace: str,
    ttl: float | None = None,
    tier: str = CONST_CACHE_TIER_L1_L2,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Memoise a function through the tiered cache under a shared namespace.

    Replaces the hand-written get/compute/set trios that each module had grown, so every
    cached value gets consistent key construction, TTL handling, and statistics.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = digest_key(namespace, {"fn": func.__qualname__, "a": args, "k": kwargs})
            cache = get_cache()
            hit = cache.get(key)
            if hit is not None:
                return hit  # type: ignore[no-any-return]
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(key, result, ttl=ttl, tier=tier)
            return result

        return wrapper

    return decorator


__all__ = [
    "CacheStats",
    "LRUCache",
    "TieredCache",
    "build_cache_key",
    "cached",
    "digest_key",
    "get_cache",
    "reset_cache",
]
