"""Centralized GitHub CLI rate limiter, pacing, backoff, and caching subsystem."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_CACHE_DIR_NAME,
    CONST_GH_CLI,
    CONST_GH_QUOTA_CACHE_FILENAME,
    CONST_GITHUB_RATE_LIMIT_PATTERNS,
)
from devops_cli.config.defaults import (
    DEFAULT_DATA_DIR,
    DEFAULT_GH_BURST_MULTIPLIER,
    DEFAULT_GH_CACHE_TTL_SECONDS,
    DEFAULT_GH_GRAPHQL_COST_FACTOR,
    DEFAULT_GH_MIN_INTERVAL_SECONDS,
    DEFAULT_GH_SHAPING_K,
)
from devops_cli.core.process import run_subprocess

logger = logging.getLogger(__name__)


@dataclass
class _CacheEntry:
    data: str
    expires_at: float


@dataclass
class QuotaState:
    """Tracked rate limit quota metrics for a specific GitHub API resource."""

    limit: int = 5000
    remaining: int = 5000
    used: int = 0
    reset_epoch: float = 0.0
    window_seconds: float = 0.0
    last_updated: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize quota metrics to dictionary."""
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "used": self.used,
            "reset_epoch": self.reset_epoch,
            "window_seconds": self.window_seconds,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuotaState:
        """Construct QuotaState from serialized dictionary."""
        return cls(
            limit=int(data.get("limit", 5000)),
            remaining=int(data.get("remaining", 5000)),
            used=int(data.get("used", 0)),
            reset_epoch=float(data.get("reset_epoch", 0.0)),
            window_seconds=float(data.get("window_seconds", 0.0)),
            last_updated=float(data.get("last_updated", 0.0)),
        )


def _load_disk_quota(path: Path) -> dict[str, QuotaState]:
    """Safely load cached quota metrics from disk."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {k: QuotaState.from_dict(v) for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _save_disk_quota(quotas: dict[str, QuotaState], path: Path) -> None:
    """Safely persist tracked quota metrics to disk cache."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {k: v.to_dict() for k, v in quotas.items()}
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        temp_path.replace(path)
    except Exception:
        pass


def extract_json_payload(raw_stdout: str) -> Any:
    """Extract JSON object or array from CLI output that may contain diagnostic preamble."""
    if not raw_stdout:
        return {}
    clean = raw_stdout.strip()
    idx_obj = clean.find("{")
    idx_arr = clean.find("[")
    if idx_obj == -1 and idx_arr == -1:
        return {}
    start_idx = idx_obj if (idx_arr == -1 or (idx_obj != -1 and idx_obj < idx_arr)) else idx_arr
    try:
        return json.loads(clean[start_idx:])
    except Exception:
        return {}


class GitHubAdaptiveLimiter:
    """Dynamic rate limiter with exponential decay based on actual time remaining until reset.

    Implements adaptive velocity scaling with dynamic time windows, calculating natural
    and burst baselines from live GitHub response headers (remaining tokens and seconds_until_reset).
    """

    def __init__(
        self,
        initial_quota: int = 5000,
        quota: int | None = None,
        window_seconds: float | None = None,
        burst_multiplier: float = DEFAULT_GH_BURST_MULTIPLIER,
        k: float | None = None,
        reset_epoch: float | None = None,
    ) -> None:
        # Fallback values until first live update
        actual_quota = quota if quota is not None else initial_quota
        self.quota = max(1, actual_quota)
        self.remaining = self.quota
        self.burst_multiplier = max(0.1, burst_multiplier)

        now = time.time()
        if reset_epoch is not None and reset_epoch > now:
            self.seconds_until_reset = max(1.0, float(reset_epoch - now))
        elif window_seconds is not None and window_seconds > 0:
            self.seconds_until_reset = max(1.0, window_seconds)
        else:
            self.seconds_until_reset = 60.0 if self.quota <= 100 else 3600.0

        self.k = k if k is not None else (DEFAULT_GH_SHAPING_K * (self.quota / 5000.0))
        self.lock = asyncio.Lock()

    def update_window_state(self, remaining: int, limit: int, epoch_reset: float | int) -> None:
        """Call this using headers parsed from your HTTP responses or gh api."""
        self.quota = max(1, limit)
        self.remaining = max(0, remaining)
        self.seconds_until_reset = max(1.0, float(epoch_reset - time.time()))
        self.k = DEFAULT_GH_SHAPING_K * (self.quota / 5000.0)

    @property
    def window_seconds(self) -> float:
        return self.seconds_until_reset

    @window_seconds.setter
    def window_seconds(self, val: float) -> None:
        self.seconds_until_reset = max(1.0, val)

    @property
    def natural_rate(self) -> float:
        return self.quota / self.seconds_until_reset

    @property
    def initial_burst_rate(self) -> float:
        return self.burst_multiplier * self.natural_rate

    @property
    def requests_consumed(self) -> int:
        return max(0, self.quota - self.remaining)

    @requests_consumed.setter
    def requests_consumed(self, val: int) -> None:
        self.remaining = max(0, self.quota - val)

    def get_allowed_rate(self) -> float:
        """Calculate context-aware natural and burst baselines based on actual time remaining."""
        if self.remaining <= 0:
            return 0.0001

        # Calculate context-aware natural and burst baselines based on actual time remaining
        natural_rate = self.remaining / max(1.0, self.seconds_until_reset)
        initial_burst_rate = self.burst_multiplier * natural_rate

        # Express consumption as distance from absolute threshold zero
        consumed_tokens = self.quota - self.remaining
        total_quota = max(1, self.quota)

        if consumed_tokens >= total_quota:
            return 0.0001

        effective_k = (
            self.k if self.k is not None else (DEFAULT_GH_SHAPING_K * (total_quota / 5000.0))
        )
        exponent = -effective_k * ((1.0 / (total_quota - consumed_tokens)) - (1.0 / total_quota))
        if exponent < -700.0:
            return 0.0001
        return initial_burst_rate * math.exp(exponent)

    async def acquire(self) -> float:
        """Blocks until a request is permitted based on the dynamic throttle."""
        async with self.lock:
            current_rate = self.get_allowed_rate()

            # Reciprocal conversion into specific inter-request delay
            delay = 1.0 / current_rate
            if delay > 10.0:
                logger.warning("[Adaptive] Brake engaged. Tight throttling. Delaying %.2fs", delay)

            await asyncio.sleep(delay)
            self.remaining = max(0, self.remaining - 1)
            return delay

    def acquire_sync(self) -> float:
        """Blocks synchronously until a request is permitted based on the dynamic throttle."""
        current_rate = self.get_allowed_rate()
        delay = 1.0 / current_rate
        if delay > 10.0:
            logger.warning("[Adaptive] Brake engaged. Tight throttling. Delaying %.2fs", delay)
        time.sleep(delay)
        self.remaining = max(0, self.remaining - 1)
        return delay


AdaptiveRateLimiter = GitHubAdaptiveLimiter


def calculate_allowed_rate(
    used: int,
    remaining: int,
    limit: int,
    time_left: float | None = None,
    burst_multiplier: float = DEFAULT_GH_BURST_MULTIPLIER,
    k: float | None = None,
    window_seconds: float | None = None,
) -> float:
    """Calculate allowed requests per second using GitHubAdaptiveLimiter."""
    effective_window = time_left if (time_left and time_left > 0) else window_seconds
    limiter = GitHubAdaptiveLimiter(
        initial_quota=limit,
        window_seconds=effective_window,
        burst_multiplier=burst_multiplier,
        k=k,
    )
    limiter.remaining = remaining
    return limiter.get_allowed_rate()


def calculate_exponential_backoff(
    used: int,
    remaining: int,
    limit: int,
    time_left: float | None = None,
    min_interval: float = 0.0,
    max_delay: float = 60.0,
    burst_multiplier: float = DEFAULT_GH_BURST_MULTIPLIER,
    k: float | None = None,
    window_seconds: float | None = None,
) -> float:
    """Calculate inter-request delay in seconds from the reciprocal of allowed request rate."""
    clean_limit = max(1, limit)
    clean_rem = max(0, remaining)
    clean_used = max(0, used)

    if clean_rem <= 0 or clean_used >= clean_limit:
        return max_delay

    rate = calculate_allowed_rate(
        used=clean_used,
        remaining=clean_rem,
        limit=clean_limit,
        time_left=time_left,
        burst_multiplier=burst_multiplier,
        k=k,
        window_seconds=window_seconds,
    )
    if rate <= 0.001:
        return max_delay
    return min(max_delay, max(min_interval, 1.0 / rate))


def _calculate_budget_delay(
    remaining: int,
    limit: int,
    reset_epoch: float,
    min_interval: float = 0.0,
    resource: str = "core",
    burst_multiplier: float = DEFAULT_GH_BURST_MULTIPLIER,
    window_seconds: float | None = None,
) -> float:
    """Calculate pacing delay based on actual GitHub rate limit response values."""
    now = time.time()
    time_left = max(1.0, reset_epoch - now) if reset_epoch > now else 0.0

    if remaining <= 0:
        return min(60.0, max(5.0, time_left)) if time_left > 0 else 60.0

    clean_limit = max(1, limit)
    used = max(0, clean_limit - remaining)
    exponential_delay = calculate_exponential_backoff(
        used=used,
        remaining=remaining,
        limit=clean_limit,
        time_left=time_left if time_left > 0 else None,
        min_interval=min_interval,
        burst_multiplier=burst_multiplier,
        window_seconds=window_seconds,
    )

    cost_factor = DEFAULT_GH_GRAPHQL_COST_FACTOR if resource == "graphql" else 1.0
    if time_left > 0.0:
        budget_delay = (time_left / max(1, remaining)) * cost_factor
        return min(60.0, max(min_interval, exponential_delay, budget_delay))

    return min(60.0, max(min_interval, exponential_delay))


def _is_graphql_command(clean_args: list[str]) -> bool:
    """Predicate checking if command targets GraphQL."""
    return clean_args[0] == "project" or any("graphql" in arg for arg in clean_args)


def _is_code_search_command(clean_args: list[str]) -> bool:
    """Predicate checking if command targets code search."""
    if len(clean_args) >= 2 and clean_args[0] == "search" and clean_args[1] == "code":
        return True
    return any("search/code" in arg for arg in clean_args)


def _is_code_scanning_autofix_command(clean_args: list[str]) -> bool:
    """Predicate checking if command targets code scanning autofix."""
    return any(
        ("code-scanning" in arg or "code_scanning" in arg) and "autofix" in arg
        for arg in clean_args
    )


def _is_general_search_command(clean_args: list[str]) -> bool:
    """Predicate checking if command targets general search."""
    return clean_args[0] == "search" or any("search/" in arg for arg in clean_args)


def _detect_resource(args: list[str]) -> str:
    """Determine the GitHub API rate limit resource type for a command.

    Maps CLI subcommands and API endpoints to their rate-limiting resource category:
    'graphql', 'search', 'code_search', 'code_scanning_autofix', 'dependency_sbom', or 'core'.
    """
    if not args:
        return "core"
    clean_args = [a.lower() for a in args if a not in (CONST_GH_CLI, "gh")]
    if not clean_args:
        return "core"

    if _is_graphql_command(clean_args):
        return "graphql"
    if _is_code_search_command(clean_args):
        return "code_search"
    if _is_code_scanning_autofix_command(clean_args):
        return "code_scanning_autofix"
    if _is_general_search_command(clean_args):
        return "search"
    if any("dependency-graph/sbom" in arg for arg in clean_args):
        return "dependency_sbom"

    return "core"


def _parse_reset_epoch(reset_at: str | None) -> float:
    """Parse ISO resetAt string into epoch timestamp."""
    if not reset_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def _has_graphql_rate_limit_error(errors: Any, limiter: GitHubRateLimiter) -> bool:
    """Predicate checking if GraphQL error list contains rate limit exhaustion."""
    if not isinstance(errors, list):
        return False
    for err in errors:
        if not isinstance(err, dict):
            continue
        err_msg = str(err.get("message", "")).lower()
        if err.get("type") == "RATE_LIMIT" or limiter.is_rate_limit_error(err_msg):
            return True
    return False


def _extract_graphql_ratelimit_json(output: str, limiter: GitHubRateLimiter) -> None:
    """Extract rateLimit block from GraphQL JSON output or detect rate limit errors."""
    try:
        data = json.loads(output)
        if not isinstance(data, dict):
            return
        rl = data.get("data", {}).get("rateLimit") or data.get("extensions", {}).get("rateLimit")
        if isinstance(rl, dict) and "remaining" in rl:
            reset_ep = _parse_reset_epoch(rl.get("resetAt"))
            limiter.update_quota(
                "graphql",
                remaining=int(rl["remaining"]),
                limit=int(rl.get("limit", 5000)),
                reset_epoch=reset_ep,
            )
        if _has_graphql_rate_limit_error(data.get("errors"), limiter):
            limiter.update_quota("graphql", remaining=0)
    except Exception:
        pass


def _probe_live_graphql_reset_epoch() -> float:
    """Query live GraphQL resetAt epoch at zero cost when quota is exhausted."""
    try:
        proc = run_subprocess(
            [CONST_GH_CLI, "api", "graphql", "-f", "query=query { rateLimit { resetAt } }"],
            check=False,
            quiet=True,
            timeout=5.0,
        )
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            reset_at = data.get("data", {}).get("rateLimit", {}).get("resetAt")
            return _parse_reset_epoch(reset_at)
    except Exception:
        pass
    return 0.0


def _probe_live_graphql_quota() -> tuple[int, int, float] | None:
    """Query live GraphQL rate limit (remaining, limit, reset_epoch) at low cost."""
    try:
        proc = run_subprocess(
            [
                CONST_GH_CLI,
                "api",
                "graphql",
                "-f",
                "query=query { rateLimit { limit remaining resetAt } }",
            ],
            check=False,
            quiet=True,
            timeout=5.0,
        )
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            rl = data.get("data", {}).get("rateLimit", {})
            rem = int(rl.get("remaining", 0))
            lim = int(rl.get("limit", 5000))
            ep = _parse_reset_epoch(rl.get("resetAt"))
            return rem, lim, ep
    except Exception:
        pass
    return None


def _parse_int_safe(value: str, default: int | None = None) -> int | None:
    """Parse string integer without throwing exceptions on malformed input."""
    try:
        return int(value.strip())
    except ValueError, TypeError:
        return default


def _parse_float_safe(value: str, default: float = 0.0) -> float:
    """Parse string float without throwing exceptions on malformed input."""
    try:
        return float(value.strip())
    except ValueError, TypeError:
        return default


def _apply_header_metric(k: str, v: str, metrics: dict[str, Any]) -> None:
    """Parse and record an individual rate limit header key-value pair."""
    val = v.strip()
    if k == "x-ratelimit-remaining":
        metrics["remaining"] = _parse_int_safe(val)
        return
    if k == "x-ratelimit-limit":
        metrics["limit"] = _parse_int_safe(val, default=0) or 0
        return
    if k == "x-ratelimit-reset":
        metrics["reset_epoch"] = _parse_float_safe(val)
        return
    if k == "x-ratelimit-resource" and val:
        metrics["resource"] = val.lower()
        return
    if k == "x-ratelimit-used":
        metrics["used"] = _parse_int_safe(val)
        return


def _extract_header_ratelimit(output: str, resource: str, limiter: GitHubRateLimiter) -> None:
    """Extract x-ratelimit headers from response output using actual GitHub response values."""
    metrics: dict[str, Any] = {"limit": 0, "reset_epoch": 0.0, "resource": resource}
    for line in output.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            _apply_header_metric(k.strip().lower(), v, metrics)

    if metrics.get("remaining") is not None:
        rem_val = metrics["remaining"]
        used_val = metrics.get("used", 0) or 0
        lim_val = metrics["limit"] if metrics["limit"] > 0 else (rem_val + used_val)
        limiter.update_quota(
            metrics["resource"],
            remaining=rem_val,
            limit=max(1, lim_val),
            reset_epoch=metrics["reset_epoch"],
            used=metrics.get("used"),
        )


def _parse_rate_limit_from_output(output: str, resource: str, limiter: GitHubRateLimiter) -> None:
    """Passively parse and update rate limit quota from command output or headers."""
    if not output:
        return
    if "rateLimit" in output:
        _extract_graphql_ratelimit_json(output, limiter)
    if "x-ratelimit-remaining" in output.lower():
        _extract_header_ratelimit(output, resource, limiter)


def _derive_window_seconds(
    state: QuotaState,
    reset_epoch: float,
    now: float,
    window_seconds: float | None = None,
) -> float:
    """Derive window duration dynamically from consecutive resets, response, or explicit param."""
    if reset_epoch > 0.0:
        time_left = max(1.0, reset_epoch - now)
        if state.reset_epoch > 0.0 and reset_epoch > state.reset_epoch:
            return reset_epoch - state.reset_epoch
        if window_seconds is not None and window_seconds > 0.0:
            return window_seconds
        if state.window_seconds <= 0.0:
            return time_left
        return state.window_seconds
    if window_seconds is not None and window_seconds > 0.0:
        return window_seconds
    return state.window_seconds


class GitHubRateLimiter:
    """Client-side rate limiter, inter-request pacer, backoff calculator, and cache for GitHub operations."""

    def __init__(
        self,
        min_interval: float = DEFAULT_GH_MIN_INTERVAL_SECONDS,
        persist_path: Path | None = None,
        burst_multiplier: float = DEFAULT_GH_BURST_MULTIPLIER,
    ) -> None:
        self.min_interval = min_interval
        self.persist_path = persist_path
        self.burst_multiplier = burst_multiplier
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()
        self._cache: dict[str, _CacheEntry] = {}
        disk_quotas = _load_disk_quota(persist_path) if persist_path else {}
        self._quotas: dict[str, QuotaState] = {
            "core": QuotaState(),
            "graphql": QuotaState(),
            **disk_quotas,
        }

    def update_quota(
        self,
        resource: str,
        *,
        remaining: int,
        limit: int = 5000,
        reset_epoch: float = 0.0,
        used: int | None = None,
        window_seconds: float | None = None,
    ) -> None:
        """Update tracked quota status for a resource using actual response values."""
        now = time.time()
        with self._lock:
            state = self._quotas.setdefault(resource, QuotaState())
            state.remaining = remaining
            state.limit = limit
            state.used = used if used is not None else max(0, limit - remaining)
            state.window_seconds = _derive_window_seconds(state, reset_epoch, now, window_seconds)
            if reset_epoch > 0.0:
                state.reset_epoch = reset_epoch
            state.last_updated = now
            if self.persist_path:
                _save_disk_quota(self._quotas, self.persist_path)

    def decrement_quota_estimate(self, resource: str, cost: int = 1) -> None:
        """Pessimistically decrement quota estimate when commands lack rate limit headers."""
        with self._lock:
            state = self._quotas.setdefault(resource, QuotaState())
            state.remaining = max(0, state.remaining - cost)
            state.used = min(state.limit, state.used + cost)
            state.last_updated = time.time()
            if self.persist_path:
                _save_disk_quota(self._quotas, self.persist_path)

    def get_quota(self, resource: str) -> QuotaState:
        """Retrieve a copy of current quota state for a resource."""
        with self._lock:
            state = self._quotas.setdefault(resource, QuotaState())
            return QuotaState(
                limit=state.limit,
                remaining=state.remaining,
                used=state.used,
                reset_epoch=state.reset_epoch,
                last_updated=state.last_updated,
            )

    def _probe_and_update_graphql(self, now: float) -> None:
        """Execute live GraphQL probe and persist refreshed quota."""
        live = _probe_live_graphql_quota()
        if live is None:
            return
        rem, lim, ep = live
        state = self._quotas.setdefault("graphql", QuotaState())
        state.remaining = rem
        state.limit = lim
        state.used = max(0, lim - rem)
        state.reset_epoch = ep
        state.last_updated = now
        if self.persist_path:
            _save_disk_quota(self._quotas, self.persist_path)

    def _sync_quota_if_stale(self, resource: str) -> None:
        """Refresh quota from disk or live GraphQL probe if missing or stale."""
        if not self.persist_path:
            return
        now = time.time()
        state = self._quotas.setdefault(resource, QuotaState())
        if state.last_updated == 0.0 or (now - state.last_updated) > 5.0:
            disk_quotas = _load_disk_quota(self.persist_path)
            if resource in disk_quotas and disk_quotas[resource].last_updated > state.last_updated:
                self._quotas[resource] = disk_quotas[resource]
                state = self._quotas[resource]

        needs_live_probe = (
            resource == "graphql" and state.reset_epoch > 0 and now >= state.reset_epoch
        )
        if needs_live_probe:
            self._probe_and_update_graphql(now)

    def calculate_adaptive_delay(self, resource: str = "core") -> float:
        """Calculate progressive request delay based on remaining quota and window budget."""
        with self._lock:
            self._sync_quota_if_stale(resource)
            state = self._quotas.get(resource)
            if state is None or state.last_updated == 0.0:
                return self.min_interval
            now = time.time()
            if state.reset_epoch > 0 and now >= state.reset_epoch:
                state.remaining = state.limit
                state.used = 0
                if state.window_seconds > 0:
                    state.reset_epoch = now + state.window_seconds
            if state.remaining <= 0:
                if state.reset_epoch > now:
                    return min(60.0, max(5.0, state.reset_epoch - now))
                return 5.0
            return _calculate_budget_delay(
                remaining=state.remaining,
                limit=state.limit,
                reset_epoch=state.reset_epoch,
                min_interval=self.min_interval,
                resource=resource,
                burst_multiplier=self.burst_multiplier,
                window_seconds=state.window_seconds if state.window_seconds > 0 else None,
            )

    def acquire(self, resource: str = "core") -> float:
        """Pace requests to enforce minimum interval and adaptive quota backoff."""
        effective_interval = self.calculate_adaptive_delay(resource)
        with self._lock:
            now = time.perf_counter()
            elapsed = now - self._last_request_time
            sleep_duration = 0.0
            if elapsed < effective_interval:
                sleep_duration = effective_interval - elapsed
                time.sleep(sleep_duration)
            self._last_request_time = time.perf_counter()
            return sleep_duration

    def is_rate_limit_error(self, message: str) -> bool:
        """Detect whether an error output indicates primary or secondary GitHub rate limits."""
        if not message:
            return False
        clean = message.lower()
        return any(pattern in clean for pattern in CONST_GITHUB_RATE_LIMIT_PATTERNS)

    def calculate_backoff_delay(
        self, message: str, attempt: int = 1, resource: str = "core"
    ) -> float:
        """Calculate exponential backoff delay with randomized jitter or quota reset window."""
        if not self.is_rate_limit_error(message):
            return 0.0
        with self._lock:
            state = self._quotas.get(resource)
            if state and state.remaining <= 0 and state.reset_epoch > 0.0:
                now = time.time()
                if state.reset_epoch > now:
                    remaining_seconds = state.reset_epoch - now
                    return float(min(60.0, max(5.0, remaining_seconds)))
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

    def set_cached(self, key: str, data: str, ttl: float = DEFAULT_GH_CACHE_TTL_SECONDS) -> None:
        """Cache response data for the specified TTL in seconds."""
        with self._lock:
            self._cache[key] = _CacheEntry(data=data, expires_at=time.time() + ttl)

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        with self._lock:
            self._cache.clear()


_GLOBAL_RATE_LIMITER: GitHubRateLimiter | None = None
_GLOBAL_LOCK = threading.Lock()


def resolve_quota_cache_path() -> Path:
    """Resolve GitHub quota cache path honoring DEVOPS_CLI_DATA_DIR."""
    env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    base_dir = Path(env_dir) if env_dir else DEFAULT_DATA_DIR
    return base_dir / CONST_CACHE_DIR_NAME / CONST_GH_QUOTA_CACHE_FILENAME


def reset_github_rate_limiter() -> None:
    """Reset the global rate limiter instance (useful for test isolation)."""
    global _GLOBAL_RATE_LIMITER
    with _GLOBAL_LOCK:
        _GLOBAL_RATE_LIMITER = None


def get_github_rate_limiter() -> GitHubRateLimiter:
    """Retrieve the global singleton GitHubRateLimiter instance."""
    global _GLOBAL_RATE_LIMITER
    with _GLOBAL_LOCK:
        if _GLOBAL_RATE_LIMITER is None:
            raw_interval = os.environ.get("DEVOPS_GH_RATE_INTERVAL", "")
            try:
                interval = (
                    float(raw_interval) if raw_interval.strip() else DEFAULT_GH_MIN_INTERVAL_SECONDS
                )
            except ValueError:
                interval = DEFAULT_GH_MIN_INTERVAL_SECONDS
            raw_burst = os.environ.get("DEVOPS_GH_BURST_MULTIPLIER", "")
            try:
                burst = float(raw_burst) if raw_burst.strip() else DEFAULT_GH_BURST_MULTIPLIER
            except ValueError:
                burst = DEFAULT_GH_BURST_MULTIPLIER
            _GLOBAL_RATE_LIMITER = GitHubRateLimiter(
                min_interval=interval,
                persist_path=resolve_quota_cache_path(),
                burst_multiplier=burst,
            )
        return _GLOBAL_RATE_LIMITER


def _build_cache_key(args: list[str], input: str | None = None) -> str:
    """Construct deterministic cache key from command arguments and optional input payload."""
    base = "gh:" + " ".join(args)
    return f"{base}::{input}" if input else base


def _should_cache(args: list[str], use_cache: bool, input: str | None = None) -> bool:
    """Predicate evaluating whether a GitHub command qualifies for read caching."""
    if not use_cache or not args or bool(input and input.strip()):
        return False
    mutating_tokens = {
        "-X",
        "--method",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "-f",
        "--field",
        "-F",
        "--raw-field",
        "--input",
        "create",
        "edit",
        "close",
        "ready",
        "delete",
        "post",
        "patch",
        "reply",
        "resolve",
        "sync",
    }
    first = args[0]
    return first in ("api", "pr", "issue", "run", "label") and not any(
        arg in mutating_tokens or arg.upper() in mutating_tokens for arg in args
    )


def _normalize_gh_args(args: list[str]) -> list[str]:
    """Strip redundant leading gh CLI executable if present in argument list."""
    if args and (args[0] == CONST_GH_CLI or args[0] == "gh"):
        return list(args[1:])
    return list(args)


def _check_cached_result(
    limiter: GitHubRateLimiter,
    args: list[str],
    input: str | None,
    use_cache: bool,
) -> subprocess.CompletedProcess[str] | None:
    """Return cached CompletedProcess if command qualifies for read caching and is cached."""
    if not _should_cache(args, use_cache, input):
        return None
    cache_key = _build_cache_key(args, input)
    cached_val = limiter.get_cached(cache_key)
    if cached_val is None:
        return None
    return subprocess.CompletedProcess(
        args=[CONST_GH_CLI, *args],
        returncode=0,
        stdout=cached_val,
        stderr="",
    )


def _is_rate_limit_check(args: list[str]) -> bool:
    """Determine whether the command is a read-only rate limit inspection."""
    clean = [a.lower() for a in args if a not in (CONST_GH_CLI, "gh")]
    return len(clean) >= 2 and clean[0] == "api" and clean[1].lstrip("/") == "rate_limit"


def _extract_rate_limit_endpoint_response(output: str, limiter: GitHubRateLimiter) -> None:
    """Update quotas directly from /rate_limit endpoint response."""
    payload = extract_json_payload(output)
    if not isinstance(payload, dict):
        return
    resources = payload.get("resources", {})
    if not isinstance(resources, dict):
        return
    for r_name, r_info in resources.items():
        if isinstance(r_info, dict) and "remaining" in r_info and "limit" in r_info:
            limiter.update_quota(
                r_name,
                remaining=int(r_info["remaining"]),
                limit=int(r_info["limit"]),
                reset_epoch=float(r_info.get("reset", 0.0)),
            )


def _post_process_run(
    proc: subprocess.CompletedProcess[str],
    resource: str,
    limiter: GitHubRateLimiter,
    is_rate_limit_check: bool = False,
) -> None:
    """Extract rate limit metrics and pessimistically decrement quota when headers are absent."""
    if is_rate_limit_check and proc.stdout:
        _extract_rate_limit_endpoint_response(proc.stdout, limiter)
        return

    _parse_rate_limit_from_output(proc.stdout, resource, limiter)
    stdout_clean = proc.stdout or ""
    if "rateLimit" not in stdout_clean and "x-ratelimit-remaining" not in stdout_clean.lower():
        cost = 2 if resource == "graphql" else 1
        limiter.decrement_quota_estimate(resource, cost=cost)


def _handle_rate_limit_retry(
    proc: subprocess.CompletedProcess[str],
    attempts: int,
    max_retries: int,
    resource: str,
    limiter: GitHubRateLimiter,
) -> bool:
    """Back off and return True if error is a rate limit and retries remain, else False."""
    err_msg = (proc.stderr or "") + (proc.stdout or "")
    if attempts >= max_retries or not limiter.is_rate_limit_error(err_msg):
        return False

    reset_ep = _probe_live_graphql_reset_epoch() if resource == "graphql" else 0.0
    limiter.update_quota(resource, remaining=0, reset_epoch=reset_ep)
    delay = limiter.calculate_backoff_delay(err_msg, attempt=attempts + 1, resource=resource)
    logger.warning(
        "GitHub API rate limit exceeded on %s. Backing off for %.2fs before retry (attempt %d/%d)...",
        resource,
        delay,
        attempts + 1,
        max_retries,
    )
    time.sleep(delay)
    return True


def _finalize_process_result(
    last_res: subprocess.CompletedProcess[str] | None,
    full_cmd: list[str],
    check: bool,
) -> subprocess.CompletedProcess[str]:
    """Enforce exit code assertions and return completed process result."""
    if check and last_res and last_res.returncode != 0:
        raise subprocess.CalledProcessError(
            last_res.returncode, full_cmd, output=last_res.stdout, stderr=last_res.stderr
        )
    return last_res or subprocess.CompletedProcess(
        args=full_cmd, returncode=1, stdout="", stderr="Unknown error executing gh command."
    )


def run_gh(
    args: list[str],
    *,
    input: str | None = None,
    cwd: Path | None = None,
    check: bool = False,
    quiet: bool = False,
    use_cache: bool = False,
    cache_ttl: float = DEFAULT_GH_CACHE_TTL_SECONDS,
    timeout: float = 30.0,
    max_retries: int = 2,
    resource: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a GitHub CLI command via centralized rate limiting, pacing, backoff, and caching.

    Enforces inter-request token-bucket pacing, checks quotas, intercepts secondary rate
    limits with jittered exponential backoff, and returns cached read outputs when requested.
    """
    clean_args = _normalize_gh_args(args)
    limiter = get_github_rate_limiter()
    cached = _check_cached_result(limiter, clean_args, input, use_cache)
    if cached is not None:
        return cached

    full_cmd = [CONST_GH_CLI, *clean_args]
    target_resource = resource or _detect_resource(clean_args)
    cache_key = _build_cache_key(clean_args, input)
    last_res: subprocess.CompletedProcess[str] | None = None
    is_check = _is_rate_limit_check(clean_args)

    for attempts in range(max_retries + 1):
        if not is_check:
            limiter.acquire(resource=target_resource)
        proc = run_subprocess(
            full_cmd, input=input, cwd=cwd, check=False, quiet=quiet, timeout=timeout
        )
        last_res = proc
        _post_process_run(proc, target_resource, limiter, is_rate_limit_check=is_check)

        if proc.returncode == 0:
            if _should_cache(clean_args, use_cache) and proc.stdout:
                limiter.set_cached(cache_key, proc.stdout, ttl=cache_ttl)
            return proc

        if not _handle_rate_limit_retry(proc, attempts, max_retries, target_resource, limiter):
            break

    return _finalize_process_result(last_res, full_cmd, check)
