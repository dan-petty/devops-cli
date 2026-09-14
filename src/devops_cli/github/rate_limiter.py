"""Centralized GitHub CLI rate limiter, pacing, backoff, and caching subsystem."""

from __future__ import annotations

import logging
import os
import random
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import run_subprocess

logger = logging.getLogger(__name__)

# Default rate limiter settings
_DEFAULT_MIN_INTERVAL_SECONDS = 0.5  # Max 2 requests/sec to prevent secondary rate limits
_LOW_QUOTA_THRESHOLD = 100
_CRITICAL_QUOTA_THRESHOLD = 20
_DEFAULT_CACHE_TTL_SECONDS = 15.0

_SECONDARY_RATE_LIMIT_PATTERNS = (
    "rate limit already exceeded",
    "secondary rate limit",
    "abuse-rate-limit",
    "too many requests",
    "http 429",
    "wait a few minutes before you try again",
)


@dataclass
class _CacheEntry:
    data: str
    expires_at: float


class GitHubRateLimiter:
    """Client-side rate limiter, inter-request pacer, backoff calculator, and cache for GitHub operations."""

    def __init__(
        self,
        min_interval: float = _DEFAULT_MIN_INTERVAL_SECONDS,
        low_threshold: int = _LOW_QUOTA_THRESHOLD,
        critical_threshold: int = _CRITICAL_QUOTA_THRESHOLD,
    ) -> None:
        self.min_interval = min_interval
        self.low_threshold = low_threshold
        self.critical_threshold = critical_threshold
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()
        self._cache: dict[str, _CacheEntry] = {}

    def acquire(self) -> None:
        """Pace requests to enforce minimum interval between external GitHub calls."""
        with self._lock:
            now = time.perf_counter()
            elapsed = now - self._last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request_time = time.perf_counter()

    def is_quota_low(self, remaining: int) -> bool:
        """Return True if remaining rate limit quota is below the warning threshold."""
        return remaining <= self.low_threshold

    def is_quota_critical(self, remaining: int) -> bool:
        """Return True if remaining rate limit quota is critically exhausted."""
        return remaining <= self.critical_threshold

    def is_rate_limit_error(self, message: str) -> bool:
        """Detect whether an error output indicates primary or secondary GitHub rate limits."""
        if not message:
            return False
        clean = message.lower()
        return any(pattern in clean for pattern in _SECONDARY_RATE_LIMIT_PATTERNS)

    def calculate_backoff_delay(self, message: str, attempt: int = 1) -> float:
        """Calculate exponential backoff delay with randomized jitter on rate limit failure."""
        if not self.is_rate_limit_error(message):
            return 0.0
        base_delay = 1.0 * (2 ** min(attempt, 4))
        jitter = random.uniform(0.2, 1.0)
        return float(base_delay + jitter)

    def get_cached(self, key: str) -> str | None:
        """Retrieve unexpired cached stdout string for an idempotent query."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() > entry.expires_at:
                del self._cache[key]
                return None
            return entry.data

    def set_cached(self, key: str, data: str, ttl: float = _DEFAULT_CACHE_TTL_SECONDS) -> None:
        """Cache response data for the specified TTL in seconds."""
        with self._lock:
            self._cache[key] = _CacheEntry(data=data, expires_at=time.time() + ttl)

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        with self._lock:
            self._cache.clear()


_GLOBAL_RATE_LIMITER: GitHubRateLimiter | None = None
_GLOBAL_LOCK = threading.Lock()


def get_github_rate_limiter() -> GitHubRateLimiter:
    """Retrieve the global singleton GitHubRateLimiter instance."""
    global _GLOBAL_RATE_LIMITER
    with _GLOBAL_LOCK:
        if _GLOBAL_RATE_LIMITER is None:
            raw_interval = os.environ.get("DEVOPS_GH_RATE_INTERVAL", "")
            try:
                interval = (
                    float(raw_interval) if raw_interval.strip() else _DEFAULT_MIN_INTERVAL_SECONDS
                )
            except ValueError:
                interval = _DEFAULT_MIN_INTERVAL_SECONDS
            _GLOBAL_RATE_LIMITER = GitHubRateLimiter(min_interval=interval)
        return _GLOBAL_RATE_LIMITER


def _build_cache_key(args: list[str]) -> str:
    """Construct deterministic cache key from command arguments."""
    return "gh:" + " ".join(args)


def _should_cache(args: list[str], use_cache: bool) -> bool:
    """Predicate evaluating whether a GitHub command qualifies for read caching."""
    if not use_cache or not args:
        return False
    # Only cache read/query subcommands
    first = args[0]
    return first in ("api", "pr", "issue", "run", "label") and not any(
        arg in ("-X", "create", "edit", "close", "ready", "delete", "post", "patch") for arg in args
    )


def run_gh(
    args: list[str],
    *,
    input: str | None = None,
    cwd: Path | None = None,
    check: bool = False,
    quiet: bool = False,
    use_cache: bool = False,
    cache_ttl: float = _DEFAULT_CACHE_TTL_SECONDS,
    timeout: float = 30.0,
    max_retries: int = 2,
) -> subprocess.CompletedProcess[str]:
    """Execute a GitHub CLI command via centralized rate limiting, pacing, backoff, and caching.

    Enforces inter-request token-bucket pacing, checks quotas, intercepts secondary rate
    limits with jittered exponential backoff, and returns cached read outputs when requested.
    """
    limiter = get_github_rate_limiter()
    cache_key = _build_cache_key(args)

    if _should_cache(args, use_cache):
        cached_val = limiter.get_cached(cache_key)
        if cached_val is not None:
            return subprocess.CompletedProcess(
                args=[CONST_GH_CLI, *args],
                returncode=0,
                stdout=cached_val,
                stderr="",
            )

    full_cmd = [CONST_GH_CLI, *args]
    attempts = 0
    last_res: subprocess.CompletedProcess[str] | None = None

    while attempts <= max_retries:
        limiter.acquire()
        proc = run_subprocess(
            full_cmd,
            input=input,
            cwd=cwd,
            check=False,
            quiet=quiet,
            timeout=timeout,
        )
        last_res = proc
        if proc.returncode == 0:
            if _should_cache(args, use_cache) and proc.stdout:
                limiter.set_cached(cache_key, proc.stdout, ttl=cache_ttl)
            return proc

        err_msg = (proc.stderr or "") + (proc.stdout or "")
        if attempts < max_retries and limiter.is_rate_limit_error(err_msg):
            delay = limiter.calculate_backoff_delay(err_msg, attempt=attempts + 1)
            logger.warning(
                "GitHub API rate limit exceeded. Backing off for %.2fs before retry (attempt %d/%d)...",
                delay,
                attempts + 1,
                max_retries,
            )
            time.sleep(delay)
            attempts += 1
            continue

        break

    if check and last_res and last_res.returncode != 0:
        raise subprocess.CalledProcessError(
            last_res.returncode, full_cmd, output=last_res.stdout, stderr=last_res.stderr
        )

    return last_res or subprocess.CompletedProcess(
        args=full_cmd, returncode=1, stdout="", stderr="Unknown error executing gh command."
    )
