"""Persistent and in-memory LLM response cache with warm starting point formatting."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.defaults import (
    DEFAULT_LLM_CACHE_ENABLED,
    DEFAULT_LLM_CACHE_MAX_ENTRIES,
    DEFAULT_LLM_CACHE_TTL_SECONDS,
)
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import record_metric

logger = logging.getLogger(__name__)


class CachedLLMResponse(BaseModel):
    """Structured data container for cached LLM inference responses."""

    model_config = ConfigDict(frozen=False)

    key: str
    provider: str
    model: str
    system_hash: str
    prompt_hash: str
    content: str
    thinking: str | None = None
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)
    hit_count: int = 0
    context_tag: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tokens: dict[str, int | None] = Field(default_factory=dict)
    wall_seconds: float = 0.0
    backend_info: str | None = None

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if this cached response has exceeded its time-to-live."""
        if ttl_seconds <= 0:
            return False
        return (time.time() - self.created_at) > ttl_seconds


class ResponseCacheStats(BaseModel):
    """Performance metrics, hit rates, and disk utilization for LLM response cache."""

    model_config = ConfigDict(frozen=True)

    enabled: bool
    memory_entries: int
    disk_entries: int
    hits: int
    misses: int
    total_lookups: int
    hit_rate_percent: float
    disk_size_bytes: int
    cache_directory: str
    ttl_seconds: float
    max_entries: int


def _matches_context_or_prefix(
    entry: CachedLLMResponse, context_tag: str | None, key_prefix: str | None
) -> bool:
    """Check if cache entry matches specified context tag or key prefix."""
    if context_tag and entry.context_tag == context_tag:
        return True
    if key_prefix and entry.key.startswith(key_prefix):
        return True
    return False


def _clear_disk_cache(cdir: Path) -> int:
    """Unlink all disk cache files and return deleted file count."""
    if not cdir.is_dir():
        return 0
    count = 0
    for p in cdir.glob("llm_*.json"):
        try:
            p.unlink()
            count += 1
        except OSError:
            pass
    return count


def _evict_excess_disk_files(cdir: Path, max_entries: int) -> None:
    """Prune oldest disk cache files when count exceeds max_entries."""
    if not cdir.is_dir():
        return
    disk_files = sorted(cdir.glob("llm_*.json"), key=lambda p: p.stat().st_mtime)
    excess = len(disk_files) - max_entries
    if excess <= 0:
        return
    for p in disk_files[:excess]:
        try:
            p.unlink()
        except OSError:
            pass


def _find_starting_point_candidates(
    memory_cache: dict[str, CachedLLMResponse],
    disk_entries: list[CachedLLMResponse],
    ttl_seconds: float,
    context_tag: str | None,
    key_prefix: str | None,
) -> list[CachedLLMResponse]:
    """Find and return valid candidate cache entries matching tag or prefix."""
    candidates = [
        entry
        for entry in memory_cache.values()
        if not entry.is_expired(ttl_seconds)
        and _matches_context_or_prefix(entry, context_tag, key_prefix)
    ]
    if candidates:
        return candidates
    return [
        entry
        for entry in disk_entries
        if _matches_context_or_prefix(entry, context_tag, key_prefix)
    ]


class LLMResponseCache:
    """Multi-tiered in-memory and persistent disk cache for LLM responses."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        enabled: bool = DEFAULT_LLM_CACHE_ENABLED,
        ttl_seconds: float = float(DEFAULT_LLM_CACHE_TTL_SECONDS),
        max_entries: int = DEFAULT_LLM_CACHE_MAX_ENTRIES,
    ) -> None:
        if cache_dir is not None:
            self.cache_dir = cache_dir
        else:
            from devops_cli.config.constants import CONST_LLM_CACHE_DIR_NAME
            from devops_cli.config.settings import load_settings

            self.cache_dir = load_settings().data.cache_dir / CONST_LLM_CACHE_DIR_NAME
        self.enabled = enabled
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = max_entries
        self._memory_cache: dict[str, CachedLLMResponse] = {}
        self._lock = threading.RLock()
        self._hits: int = 0
        self._misses: int = 0

    def _resolve_cache_dir(self) -> Path:
        """Resolve top-level repository cache directory."""
        if self.cache_dir.is_absolute():
            return self.cache_dir
        top_root = find_top_level_repo_root(Path.cwd())
        resolved = (top_root / self.cache_dir).resolve()
        return resolved

    @staticmethod
    def generate_key(
        provider: str,
        model: str,
        system: str,
        messages_or_prompt: list[ChatMessage] | str,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate a deterministic SHA-256 cache key for an LLM request."""
        hasher = hashlib.sha256(usedforsecurity=False)
        p_str = str(provider) if not isinstance(provider, str) else provider
        m_str = str(model) if not isinstance(model, str) else model
        s_str = str(system) if not isinstance(system, str) else system
        hasher.update(p_str.strip().lower().encode("utf-8"))
        hasher.update(b"|")
        hasher.update(m_str.strip().lower().encode("utf-8"))
        hasher.update(b"|")
        hasher.update(s_str.strip().encode("utf-8"))
        hasher.update(b"|")

        if isinstance(messages_or_prompt, str):
            hasher.update(messages_or_prompt.strip().encode("utf-8"))
        else:
            for msg in messages_or_prompt:
                role = getattr(msg, "role", "user")
                content = getattr(msg, "content", "")
                hasher.update(f"{role}:{content.strip()}|".encode())

        if options:
            sorted_opts = json.dumps(options, sort_keys=True, default=str)
            hasher.update(sorted_opts.encode("utf-8"))

        return f"llm_{hasher.hexdigest()}"

    def get(self, key: str) -> CachedLLMResponse | None:
        """Retrieve a cached LLM response by key if valid and not expired."""
        if not self.enabled:
            return None

        with self._lock:
            # 1. Check memory cache first
            cached = self._memory_cache.get(key)
            if cached is not None:
                if cached.is_expired(self.ttl_seconds):
                    del self._memory_cache[key]
                    self._delete_disk_file(key)
                    self._misses += 1
                    return None
                cached.hit_count += 1
                cached.last_accessed = time.time()
                self._hits += 1
                self._save_to_disk(cached)
                record_metric("devops_cli_llm_cache_hits", 1.0, attributes={"source": "memory"})
                return cached

            # 2. Check disk cache
            disk_entry = self._load_from_disk(key)
            if disk_entry is not None:
                if disk_entry.is_expired(self.ttl_seconds):
                    self._delete_disk_file(key)
                    self._misses += 1
                    return None
                disk_entry.hit_count += 1
                disk_entry.last_accessed = time.time()
                self._memory_cache[key] = disk_entry
                self._hits += 1
                self._save_to_disk(disk_entry)
                record_metric("devops_cli_llm_cache_hits", 1.0, attributes={"source": "disk"})
                return disk_entry

            self._misses += 1
            record_metric("devops_cli_llm_cache_misses", 1.0)
            return None

    def set(
        self,
        key: str,
        provider: str,
        model: str,
        system: str,
        prompt: str,
        content: str,
        thinking: str | None = None,
        context_tag: str | None = None,
        metadata: dict[str, Any] | None = None,
        tokens: dict[str, int | None] | None = None,
        wall_seconds: float = 0.0,
        backend_info: str | None = None,
    ) -> CachedLLMResponse:
        """Persist an LLM response into memory and disk cache."""
        sys_hash = hashlib.sha256(system.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
        prompt_hash = hashlib.sha256(prompt.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]

        entry = CachedLLMResponse(
            key=key,
            provider=provider,
            model=model,
            system_hash=sys_hash,
            prompt_hash=prompt_hash,
            content=content,
            thinking=thinking,
            created_at=time.time(),
            last_accessed=time.time(),
            hit_count=0,
            context_tag=context_tag,
            metadata=metadata or {},
            tokens=tokens or {},
            wall_seconds=wall_seconds,
            backend_info=backend_info,
        )

        if not self.enabled:
            return entry

        with self._lock:
            self._memory_cache[key] = entry
            self._save_to_disk(entry)
            self._enforce_capacity()
            record_metric("devops_cli_llm_cache_writes", 1.0)
            return entry

    def get_starting_point(
        self,
        context_tag: str | None = None,
        key_prefix: str | None = None,
    ) -> str | None:
        """Retrieve the most recent cached response to provide as a starting point."""
        if not self.enabled:
            return None

        with self._lock:
            candidates = _find_starting_point_candidates(
                self._memory_cache,
                self._load_all_valid_disk_entries(),
                self.ttl_seconds,
                context_tag,
                key_prefix,
            )
            if not candidates:
                return None

            candidates.sort(key=lambda x: x.last_accessed, reverse=True)
            return candidates[0].content

    @staticmethod
    def format_starting_point_prompt(
        prompt: str,
        starting_point: str,
        instruction: str | None = None,
    ) -> str:
        """Wrap prompt with prior cached starting point as a baseline for refinement."""
        default_inst = (
            "Use the baseline starting point below as prior reference. "
            "Review the current context, retain valid conclusions, correct outdated findings, "
            "and produce the complete updated response."
        )
        inst_text = instruction or default_inst
        return (
            f"<starting_point>\n"
            f"{starting_point.strip()}\n"
            f"</starting_point>\n\n"
            f"<current_request>\n"
            f"{prompt.strip()}\n"
            f"</current_request>\n\n"
            f"Instruction: {inst_text}"
        )

    def clear(self) -> int:
        """Clear all memory and persistent disk cache entries."""
        with self._lock:
            count = len(self._memory_cache)
            self._memory_cache.clear()
            self._hits = 0
            self._misses = 0

            cdir = self._resolve_cache_dir()
            count += _clear_disk_cache(cdir)
            return count

    def get_stats(self) -> ResponseCacheStats:
        """Compute performance statistics, hit rates, and disk utilization."""
        with self._lock:
            cdir = self._resolve_cache_dir()
            disk_files = list(cdir.glob("llm_*.json")) if cdir.is_dir() else []
            total_disk_bytes = sum(p.stat().st_size for p in disk_files if p.is_file())
            total_lookups = self._hits + self._misses
            hit_rate_pct = (self._hits / total_lookups * 100.0) if total_lookups > 0 else 0.0

            return ResponseCacheStats(
                enabled=self.enabled,
                memory_entries=len(self._memory_cache),
                disk_entries=len(disk_files),
                hits=self._hits,
                misses=self._misses,
                total_lookups=total_lookups,
                hit_rate_percent=round(hit_rate_pct, 1),
                disk_size_bytes=total_disk_bytes,
                cache_directory=str(cdir),
                ttl_seconds=self.ttl_seconds,
                max_entries=self.max_entries,
            )

    def _save_to_disk(self, entry: CachedLLMResponse) -> None:
        """Save a single cached response entry to disk atomically."""
        try:
            cdir = self._resolve_cache_dir()
            cdir.mkdir(parents=True, exist_ok=True)
            target_file = cdir / f"{entry.key}.json"
            temp_file = cdir / f"{entry.key}.tmp"
            temp_file.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
            temp_file.replace(target_file)
        except Exception as exc:
            logger.debug("Failed to write LLM response cache to disk: %s", exc)

    def _load_from_disk(self, key: str) -> CachedLLMResponse | None:
        """Load a cached response entry from disk if present."""
        try:
            target_file = self._resolve_cache_dir() / f"{key}.json"
            if not target_file.is_file():
                return None
            data = target_file.read_text(encoding="utf-8")
            return CachedLLMResponse.model_validate_json(data)
        except Exception as exc:
            logger.debug("Failed to load LLM response cache file for key '%s': %s", key, exc)
            return None

    def _load_all_valid_disk_entries(self) -> list[CachedLLMResponse]:
        """Load all valid, non-expired cache entries from disk."""
        entries: list[CachedLLMResponse] = []
        cdir = self._resolve_cache_dir()
        if not cdir.is_dir():
            return entries
        for p in cdir.glob("llm_*.json"):
            try:
                data = p.read_text(encoding="utf-8")
                item = CachedLLMResponse.model_validate_json(data)
                if not item.is_expired(self.ttl_seconds):
                    entries.append(item)
            except Exception:
                pass
        return entries

    def _delete_disk_file(self, key: str) -> None:
        """Delete a single cache file on disk."""
        try:
            target = self._resolve_cache_dir() / f"{key}.json"
            if target.exists():
                target.unlink()
        except OSError:
            pass

    def _enforce_capacity(self) -> None:
        """Prune least recently accessed entries if capacity exceeds max_entries."""
        if self.max_entries <= 0:
            return

        if len(self._memory_cache) > self.max_entries:
            sorted_items = sorted(
                self._memory_cache.items(), key=lambda item: item[1].last_accessed
            )
            excess = len(self._memory_cache) - self.max_entries
            for k, _ in sorted_items[:excess]:
                del self._memory_cache[k]

        cdir = self._resolve_cache_dir()
        _evict_excess_disk_files(cdir, self.max_entries)


_GLOBAL_LLM_CACHE: LLMResponseCache | None = None
_CACHE_LOCK = threading.Lock()


def get_llm_response_cache(
    cache_dir: Path | None = None,
    enabled: bool = DEFAULT_LLM_CACHE_ENABLED,
    ttl_seconds: float = float(DEFAULT_LLM_CACHE_TTL_SECONDS),
    max_entries: int = DEFAULT_LLM_CACHE_MAX_ENTRIES,
) -> LLMResponseCache:
    """Retrieve global singleton LLM response cache instance."""
    global _GLOBAL_LLM_CACHE
    with _CACHE_LOCK:
        if _GLOBAL_LLM_CACHE is None:
            _GLOBAL_LLM_CACHE = LLMResponseCache(
                cache_dir=cache_dir,
                enabled=enabled,
                ttl_seconds=ttl_seconds,
                max_entries=max_entries,
            )
        return _GLOBAL_LLM_CACHE


def reset_llm_response_cache() -> None:
    """Reset the global singleton LLM response cache (useful in tests)."""
    global _GLOBAL_LLM_CACHE
    with _CACHE_LOCK:
        if _GLOBAL_LLM_CACHE is not None:
            _GLOBAL_LLM_CACHE.clear()
        _GLOBAL_LLM_CACHE = None
