"""Valkey distributed AI caching provider for embeddings, review findings, and LLM responses."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from itertools import batched
from typing import Any

from devops_cli.cache import TieredCache, build_cache_key, digest_key
from devops_cli.config.defaults import DEFAULT_AI_CACHE_TTL_SECONDS
from devops_cli.config.settings import Settings, get_valkey_password, load_settings
from devops_cli.exceptions.valkey import ValkeyError
from devops_cli.valkey.client import ValkeyClient

logger = logging.getLogger(__name__)

# Cache namespaces. Keys are built by the shared builder in devops_cli.cache so every
# namespace is invalidatable as a unit and no two call sites can disagree on placement.
CACHE_NS_EMBEDDING = "ai:embedding"
CACHE_NS_FINDING = "ai:finding"
CACHE_NS_LLM = "ai:llm"
PREFIX_ALL = f"{build_cache_key('ai')}:*"


def _compute_sha256(data: str) -> str:
    """Compute SHA-256 hex digest for key derivation."""
    return hashlib.sha256(data.encode("utf-8"), usedforsecurity=False).hexdigest()


class ValkeyCacheProvider:
    """High-performance Valkey cache provider for AI operations with fail-soft semantics."""

    def __init__(
        self,
        client: ValkeyClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._client = client or self._build_client()
        self._tiered: TieredCache | None = None

    def _build_client(self) -> ValkeyClient:
        """Instantiate Valkey client from settings."""
        cfg = self._settings.valkey
        pwd = get_valkey_password(self._settings)
        return ValkeyClient(
            host=cfg.host,
            port=cfg.port,
            password=pwd,
            db=cfg.db,
            timeout=cfg.timeout,
        )

    def is_available(self) -> bool:
        """Check if Valkey server is reachable and responsive."""
        try:
            return self._client.ping()
        except ValkeyError as exc:
            logger.debug("Valkey is unavailable: %s", exc)
            return False

    def _cache(self) -> TieredCache:
        """Resolve the shared tiered cache, binding this provider's client as its L2."""
        if self._tiered is None:
            self._tiered = TieredCache(backend=self._client)
        return self._tiered

    def get_embedding(self, text: str, model: str) -> list[float] | None:
        """Retrieve a cached embedding vector by text and model."""
        value = self._cache().get(digest_key(CACHE_NS_EMBEDDING, f"{model}:{text}"))
        return value if isinstance(value, list) else None

    def set_embedding(
        self,
        text: str,
        model: str,
        vector: list[float],
        ttl_seconds: int = DEFAULT_AI_CACHE_TTL_SECONDS,
    ) -> bool:
        """Store an embedding vector with a TTL."""
        return self._store(digest_key(CACHE_NS_EMBEDDING, f"{model}:{text}"), vector, ttl_seconds)

    def get_embeddings(self, texts: Sequence[str], model: str) -> dict[str, list[float]]:
        """Retrieve many embeddings in a single round trip.

        Batching is what makes bulk embedding lookups viable: fetching N vectors
        sequentially costs N network round trips, which dominates the lookup itself.
        """
        keys = {digest_key(CACHE_NS_EMBEDDING, f"{model}:{text}"): text for text in texts}
        found = self._cache().get_many(keys)
        return {keys[key]: value for key, value in found.items() if isinstance(value, list)}

    def get_review_findings(
        self,
        file_path: str,
        content_hash: str,
        persona: str,
    ) -> list[dict[str, Any]] | None:
        """Retrieve cached review findings for a file content hash and persona."""
        value = self._cache().get(
            digest_key(CACHE_NS_FINDING, f"{persona}:{file_path}:{content_hash}")
        )
        return value if isinstance(value, list) else None

    def set_review_findings(
        self,
        file_path: str,
        content_hash: str,
        persona: str,
        findings: list[dict[str, Any]],
        ttl_seconds: int = DEFAULT_AI_CACHE_TTL_SECONDS,
    ) -> bool:
        """Store review findings in the cache with a TTL."""
        return self._store(
            digest_key(CACHE_NS_FINDING, f"{persona}:{file_path}:{content_hash}"),
            findings,
            ttl_seconds,
        )

    def get_llm_response(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve a cached LLM response dictionary by key."""
        value = self._cache().get(build_cache_key(CACHE_NS_LLM, cache_key))
        return value if isinstance(value, dict) else None

    def set_llm_response(
        self,
        cache_key: str,
        response_data: dict[str, Any],
        ttl_seconds: int = DEFAULT_AI_CACHE_TTL_SECONDS,
    ) -> bool:
        """Store an LLM response dictionary in the cache with a TTL."""
        return self._store(build_cache_key(CACHE_NS_LLM, cache_key), response_data, ttl_seconds)

    def _store(self, key: str, value: Any, ttl_seconds: int) -> bool:
        """Write through both cache tiers, reporting whether the write succeeded.

        Caching is an optimisation, so a write failure is logged and reported rather than
        raised: losing a cache entry must never fail the operation that produced it.
        """
        try:
            self._cache().set(key, value, ttl=float(ttl_seconds))
        except (ValkeyError, TypeError) as exc:
            logger.debug("Failed caching value under %s: %s", key, exc)
            return False
        return True

    def flush_ai_cache(self) -> int:
        """Remove all AI cached items (embeddings, findings, LLM responses) using non-blocking SCAN."""
        try:
            keys = self._client.scan_iter(match=PREFIX_ALL)
            if not keys:
                return 0
            deleted = 0
            for chunk in batched(keys, 500):
                deleted += self._client.delete(*chunk)
            return deleted
        except ValkeyError as exc:
            logger.debug("Failed flushing AI cache: %s", exc)
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Collect caching statistics and server diagnostics using non-blocking SCAN."""
        try:
            info = self._client.info("memory")
            keys = self._client.scan_iter(match=PREFIX_ALL)
            key_count = len(keys) if isinstance(keys, list) else sum(1 for _ in keys)
            return {
                "available": True,
                "ai_keys_count": key_count,
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "total_system_memory_human": info.get("total_system_memory_human", "unknown"),
            }
        except ValkeyError as exc:
            return {
                "available": False,
                "error": str(exc),
                "ai_keys_count": 0,
            }
