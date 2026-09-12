"""Valkey distributed AI caching provider for embeddings, review findings, and LLM responses."""

from __future__ import annotations

import hashlib
import json
import logging
from itertools import batched
from typing import Any

from devops_cli.config.settings import Settings, get_valkey_password, load_settings
from devops_cli.exceptions.valkey import ValkeyError
from devops_cli.valkey.client import ValkeyClient

logger = logging.getLogger(__name__)

PREFIX_EMBEDDING = "devops:ai:embedding:"
PREFIX_FINDING = "devops:ai:finding:"
PREFIX_LLM = "devops:ai:llm:"
PREFIX_ALL = "devops:ai:*"


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

    def get_embedding(self, text: str, model: str) -> list[float] | None:
        """Retrieve cached embedding vector by text and model."""
        key = f"{PREFIX_EMBEDDING}{_compute_sha256(f'{model}:{text}')}"
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            val = json.loads(raw)
            return val if isinstance(val, list) else None
        except (ValkeyError, json.JSONDecodeError) as exc:
            logger.debug("Failed retrieving cached embedding for %s: %s", model, exc)
            return None

    def set_embedding(
        self,
        text: str,
        model: str,
        vector: list[float],
        ttl_seconds: int = 86400,
    ) -> bool:
        """Store embedding vector with TTL."""
        key = f"{PREFIX_EMBEDDING}{_compute_sha256(f'{model}:{text}')}"
        try:
            payload = json.dumps(vector)
            return self._client.set(key, payload, ex_seconds=ttl_seconds)
        except (ValkeyError, TypeError) as exc:
            logger.debug("Failed caching embedding for %s: %s", model, exc)
            return False

    def get_review_findings(
        self,
        file_path: str,
        content_hash: str,
        persona: str,
    ) -> list[dict[str, Any]] | None:
        """Retrieve cached review findings for a file content hash and persona."""
        key = f"{PREFIX_FINDING}{_compute_sha256(f'{persona}:{file_path}:{content_hash}')}"
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            val = json.loads(raw)
            return val if isinstance(val, list) else None
        except (ValkeyError, json.JSONDecodeError) as exc:
            logger.debug("Failed retrieving review findings: %s", exc)
            return None

    def set_review_findings(
        self,
        file_path: str,
        content_hash: str,
        persona: str,
        findings: list[dict[str, Any]],
        ttl_seconds: int = 86400,
    ) -> bool:
        """Store review findings in cache with TTL."""
        key = f"{PREFIX_FINDING}{_compute_sha256(f'{persona}:{file_path}:{content_hash}')}"
        try:
            payload = json.dumps(findings)
            return self._client.set(key, payload, ex_seconds=ttl_seconds)
        except (ValkeyError, TypeError) as exc:
            logger.debug("Failed caching review findings: %s", exc)
            return False

    def get_llm_response(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve cached LLM response dictionary by key."""
        key = f"{PREFIX_LLM}{cache_key}"
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            val = json.loads(raw)
            return val if isinstance(val, dict) else None
        except (ValkeyError, json.JSONDecodeError) as exc:
            logger.debug("Failed retrieving cached LLM response: %s", exc)
            return None

    def set_llm_response(
        self,
        cache_key: str,
        response_data: dict[str, Any],
        ttl_seconds: int = 86400,
    ) -> bool:
        """Store LLM response dictionary in cache with TTL."""
        key = f"{PREFIX_LLM}{cache_key}"
        try:
            payload = json.dumps(response_data)
            return self._client.set(key, payload, ex_seconds=ttl_seconds)
        except (ValkeyError, TypeError) as exc:
            logger.debug("Failed caching LLM response: %s", exc)
            return False

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
