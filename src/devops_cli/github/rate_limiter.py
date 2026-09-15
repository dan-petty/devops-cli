"""GitHub CLI rate limiter and request pacing subsystem.

Institutes a mandatory pause on gh requests calculated strictly from:
    request delay = time in seconds until next quota reset for this subcommand / remaining requests

No initial quotas, no hardcoded default windows, default request rate, or bursting.
"""

from __future__ import annotations

import json
import logging
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
    DEFAULT_GH_CACHE_TTL_SECONDS,
    DEFAULT_GH_NO_DELAY_USED_PERCENT,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubRateLimitError

logger = logging.getLogger(__name__)


@dataclass
class _CacheEntry:
    data: str
    expires_at: float


@dataclass
class QuotaState:
    """Tracked rate limit metrics for a GitHub API resource / subcommand."""

    remaining: int | None = None
    limit: int | None = None
    reset_epoch: float = 0.0
    last_updated: float = 0.0
    used: int = 0

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "remaining" and value is not None and value < 0:
            raise ValueError(f"remaining requests must be non-negative, got {value}")
        if name == "limit" and value is not None and value < 0:
            raise ValueError(f"rate limit must be non-negative, got {value}")
        if name == "used" and value is not None and value < 0:
            raise ValueError(f"used requests must be non-negative, got {value}")
        if name == "reset_epoch" and value is not None and value < 0.0:
            raise ValueError(f"reset_epoch must be non-negative, got {value}")
        super().__setattr__(name, value)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate that all quota metrics are strictly non-negative."""
        if self.remaining is not None and self.remaining < 0:
            raise ValueError(f"remaining requests must be non-negative, got {self.remaining}")
        if self.limit is not None and self.limit < 0:
            raise ValueError(f"rate limit must be non-negative, got {self.limit}")
        if self.used < 0:
            raise ValueError(f"used requests must be non-negative, got {self.used}")
        if self.reset_epoch < 0.0:
            raise ValueError(f"reset_epoch must be non-negative, got {self.reset_epoch}")

    def is_valid(self, now: float | None = None) -> bool:
        """Return True if cached quota is active and has not expired past reset epoch.

        Cached values that are not updated on every request or past reset epoch
        should never be used or relied on.
        """
        current_time = now if now is not None else time.time()
        return self.remaining is not None and self.reset_epoch > current_time

    def record_utilization(self, cost: int = 1) -> None:
        """Update quota utilization: decrement remaining and increment used."""
        if cost < 0:
            raise ValueError(f"utilization cost must be non-negative, got {cost}")
        if self.remaining is not None:
            self.remaining = max(0, self.remaining - cost)
        self.used += cost
        self.last_updated = time.time()
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "used": self.used,
            "reset_epoch": self.reset_epoch,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuotaState:
        try:
            limit_val = data.get("limit")
            limit = int(limit_val) if limit_val is not None else None
            rem_val = data.get("remaining")
            remaining = int(rem_val) if rem_val is not None else None
            used_val = data.get("used", 0)
            used = int(used_val) if used_val is not None else 0
            reset_val = data.get("reset_epoch", 0.0)
            reset_epoch = float(reset_val) if reset_val is not None else 0.0
            updated_val = data.get("last_updated", 0.0)
            last_updated = float(updated_val) if updated_val is not None else 0.0
            return cls(
                limit=limit,
                remaining=remaining,
                used=used,
                reset_epoch=reset_epoch,
                last_updated=last_updated,
            )
        except (TypeError, ValueError) as err:
            raise ValueError(f"Malformed quota state dictionary: {err}") from err


def _load_disk_quota(path: Path) -> dict[str, QuotaState]:
    """Load persistent rate limit quota state from disk, discarding expired or stale entries."""
    if not path.is_file():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        raw = json.loads(content)
        now = time.time()
        if isinstance(raw, dict):
            valid_quotas: dict[str, QuotaState] = {}
            for k, v in raw.items():
                if isinstance(v, dict):
                    try:
                        state = QuotaState.from_dict(v)
                        # Cached values not updated or past reset must never be relied on
                        if state.is_valid(now):
                            valid_quotas[k] = state
                    except TypeError, ValueError:
                        continue
            return valid_quotas
    except OSError, json.JSONDecodeError, ValueError, TypeError:
        pass
    return {}


def _save_disk_quota(quotas: dict[str, QuotaState], path: Path) -> None:
    """Persist rate limit quota state to disk atomically."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v.to_dict() for k, v in quotas.items()}
        tmp = path.with_suffix(f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError, TypeError, ValueError:
        pass


def extract_json_payload(raw_stdout: str) -> Any:
    """Extract first valid JSON object or array from output, ignoring preambles."""
    if not raw_stdout:
        return None
    trimmed = raw_stdout.strip()
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        pass

    first_obj = trimmed.find("{")
    first_arr = trimmed.find("[")
    starts = [idx for idx in (first_obj, first_arr) if idx != -1]
    if not starts:
        return None
    start_pos = min(starts)
    candidate = trimmed[start_pos:]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    return None


def calculate_request_delay(
    time_until_reset: float,
    remaining: int,
    limit: int | None = None,
    no_delay_percent_used_threshold: float | None = None,
) -> float:
    """Calculate request delay = time until reset / remaining requests.

    Raises ValueError if time_until_reset, remaining, limit, or threshold is negative.
    When under the no-delay percent used threshold, returns 0.0 (no delay applied).
    When quota is exhausted (remaining == 0), delay is the full time until reset,
    forcing the rate to zero until requests become available under the reset.
    """
    if time_until_reset < 0.0:
        raise ValueError(f"time_until_reset must be non-negative, got {time_until_reset}")
    if remaining < 0:
        raise ValueError(f"remaining requests must be non-negative, got {remaining}")
    if limit is not None and limit < 0:
        raise ValueError(f"rate limit must be non-negative, got {limit}")
    if no_delay_percent_used_threshold is not None and no_delay_percent_used_threshold < 0.0:
        raise ValueError(
            f"no_delay_percent_used_threshold must be non-negative, got {no_delay_percent_used_threshold}"
        )

    if limit is not None and limit > 0 and no_delay_percent_used_threshold is not None:
        used = max(0, limit - remaining)
        percent_used = (used / limit) * 100.0
        norm_threshold = (
            no_delay_percent_used_threshold
            if no_delay_percent_used_threshold > 1.0
            else no_delay_percent_used_threshold * 100.0
        )
        if percent_used < norm_threshold:
            return 0.0

    if remaining == 0:
        return time_until_reset
    if time_until_reset == 0.0:
        return 0.0
    return time_until_reset / remaining


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
    """Determine the GitHub API rate limit resource / subcommand category."""
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
        clean = reset_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.timestamp()
    except ValueError, TypeError:
        return 0.0


def _extract_graphql_ratelimit_json(output: str, limiter: GitHubRateLimiter) -> None:
    """Extract GraphQL rateLimit from response and update tracked state."""
    payload = extract_json_payload(output)
    if not isinstance(payload, dict):
        return
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return
    rl = data.get("rateLimit")
    if isinstance(rl, dict):
        rem = rl.get("remaining")
        lim = rl.get("limit")
        used = rl.get("used")
        reset_at = rl.get("resetAt")
        if rem is not None:
            epoch = _parse_reset_epoch(str(reset_at)) if reset_at else 0.0
            limiter.update_quota(
                "graphql",
                remaining=int(rem),
                reset_epoch=epoch,
                limit=int(lim) if lim is not None else None,
                used=int(used) if used is not None else None,
            )


def _parse_int_safe(value: str, default: int | None = None) -> int | None:
    """Parse string integer safely without exceptions."""
    try:
        return int(value.strip())
    except ValueError, TypeError:
        return default


def _parse_float_safe(value: str, default: float = 0.0) -> float:
    """Parse string float safely without exceptions."""
    try:
        return float(value.strip())
    except ValueError, TypeError:
        return default


def _parse_header_line(line: str) -> tuple[str, str] | None:
    """Split and normalize header name and value if present."""
    if ":" not in line:
        return None
    name, val = line.split(":", 1)
    return name.strip().lower(), val.strip()


def _process_header_metrics(output: str) -> dict[str, Any]:
    """Parse header lines into raw rate limit metric dictionary using table-driven dispatch."""
    metrics: dict[str, Any] = {}
    parsers = {
        "x-ratelimit-remaining": ("remaining", _parse_int_safe),
        "x-ratelimit-limit": ("limit", _parse_int_safe),
        "x-ratelimit-used": ("used", _parse_int_safe),
        "x-ratelimit-reset": ("reset_epoch", _parse_float_safe),
    }
    for line in output.splitlines():
        parsed = _parse_header_line(line)
        if not parsed:
            continue
        hdr, val = parsed
        if hdr in parsers:
            field, parser_fn = parsers[hdr]
            metrics[field] = parser_fn(val)
    return metrics


def _extract_header_ratelimit(output: str, resource: str, limiter: GitHubRateLimiter) -> None:
    """Parse HTTP headers from output for x-ratelimit metrics."""
    metrics = _process_header_metrics(output)
    if metrics.get("remaining") is not None:
        limiter.update_quota(
            resource,
            remaining=metrics["remaining"],
            reset_epoch=metrics.get("reset_epoch", 0.0) or 0.0,
            limit=metrics.get("limit"),
            used=metrics.get("used"),
        )


def _parse_rate_limit_from_output(output: str, resource: str, limiter: GitHubRateLimiter) -> None:
    """Inspect output for rate limit headers or GraphQL payloads."""
    if not output:
        return
    if resource == "graphql":
        _extract_graphql_ratelimit_json(output, limiter)
    _extract_header_ratelimit(output, resource, limiter)


class GitHubRateLimiter:
    """GitHub rate limiter that institutes a mandatory pause on gh requests.

    Formula:
        request delay = time in seconds until next quota reset for this subcommand / remaining requests

    No initial quotas, no hardcoded default windows, default request rate, or bursting.
    """

    def __init__(
        self,
        persist_path: Path | None = None,
        min_interval: float = 0.0,
        fallback_delay: float = 1.0,
        no_delay_percent_used_threshold: float = DEFAULT_GH_NO_DELAY_USED_PERCENT,
    ) -> None:
        if no_delay_percent_used_threshold < 0.0:
            raise ValueError(
                f"no_delay_percent_used_threshold must be non-negative, got {no_delay_percent_used_threshold}"
            )
        self.persist_path = persist_path
        self.min_interval = min_interval
        self.fallback_delay = fallback_delay
        self.no_delay_percent_used_threshold = no_delay_percent_used_threshold
        self._lock = threading.RLock()
        self._cache: dict[str, _CacheEntry] = {}
        self._next_allowed_time: dict[str, float] = {}
        self._is_refreshing: bool = False
        disk_quotas = _load_disk_quota(persist_path) if persist_path else {}
        self._quotas: dict[str, QuotaState] = {**disk_quotas}

    def _resolve_quota_state(self, subcommand: str) -> QuotaState:
        """Retrieve or refresh quota state for subcommand under lock.

        Raises GitHubRateLimitError if state is broken or unknown and cannot be refreshed.
        """
        now = time.time()
        state = self._quotas.get(subcommand)
        if state and state.is_valid(now):
            return state

        if self.persist_path:
            disk_quotas = _load_disk_quota(self.persist_path)
            if disk_quotas:
                self._quotas.update(disk_quotas)
                state = self._quotas.get(subcommand)
                if state and state.is_valid(now):
                    return state

        if not self._is_refreshing:
            self._is_refreshing = True
            try:
                self._refresh_from_github()
            finally:
                self._is_refreshing = False
            state = self._quotas.get(subcommand)
            if state and state.is_valid(now):
                return state

        raise GitHubRateLimitError(
            f"Rate limit state for subcommand '{subcommand}' is in an unknown or broken state "
            f"and could not be refreshed from GitHub",
            subcommand=subcommand,
            details={
                "subcommand": subcommand[:256],
                "remaining": str(getattr(state, "remaining", None)),
                "reset_epoch": str(getattr(state, "reset_epoch", 0.0)),
            },
        )

    def _refresh_from_github(self) -> None:
        """Query GitHub /rate_limit endpoint to resolve unknown or broken quota state.

        Raises GitHubRateLimitError if refresh fails so the underlying cause can be identified.
        """
        proc = run_subprocess(
            [CONST_GH_CLI, "api", "rate_limit"],
            check=False,
            quiet=True,
            timeout=10.0,
        )
        if proc.returncode != 0:
            err_msg = (
                proc.stderr.strip()
                if proc.stderr
                else f"Process exited with code {proc.returncode}"
            )
            raise GitHubRateLimitError(
                f"Failed to refresh rate limits from GitHub API: {err_msg}",
                operation="refresh_quota",
                details={
                    "exit_code": proc.returncode,
                    "stderr": proc.stderr[:256] if proc.stderr else "",
                },
            )
        if not proc.stdout:
            raise GitHubRateLimitError(
                "GitHub rate_limit API returned empty output",
                operation="refresh_quota",
            )
        _extract_rate_limit_endpoint_response(proc.stdout, self)

    def calculate_delay(self, subcommand: str = "core") -> float:
        """Calculate request delay = time until reset / remaining requests.

        If in a broken or unknown state, attempts to refresh rate limit info,
        or raises GitHubRateLimitError so the underlying cause can be identified.
        """
        with self._lock:
            state = self._resolve_quota_state(subcommand)
            now = time.time()
            time_left = state.reset_epoch - now
            if time_left < 0.0:
                raise GitHubRateLimitError(
                    f"time until reset must be non-negative, got {time_left:.2f}s for '{subcommand}'",
                    subcommand=subcommand,
                    details={"subcommand": subcommand[:256], "time_left": f"{time_left:.2f}"},
                )
            if state.remaining is None:
                raise GitHubRateLimitError(
                    f"remaining requests is unknown for subcommand '{subcommand}'",
                    subcommand=subcommand,
                )
            if state.remaining < 0:
                raise ValueError(f"remaining requests must be non-negative, got {state.remaining}")

            delay = calculate_request_delay(
                time_until_reset=time_left,
                remaining=state.remaining,
                limit=state.limit,
                no_delay_percent_used_threshold=self.no_delay_percent_used_threshold,
            )
            return max(self.min_interval, delay)

    def acquire(self, subcommand: str = "core", resource: str | None = None) -> float:
        """Institute mandatory pause of the request delay calculated for that subcommand.

        Serializes concurrent requests using _next_allowed_time scheduling to eliminate
        the race condition where concurrent subcommands execute simultaneously with no delay.
        """
        target = resource or subcommand
        with self._lock:
            now = time.time()
            try:
                delay = self.calculate_delay(target)
            except GitHubRateLimitError, TypeError, ValueError:
                delay = self.min_interval

            prev_scheduled = self._next_allowed_time.get(target, 0.0)
            scheduled_time = max(now, prev_scheduled) + delay
            self._next_allowed_time[target] = scheduled_time

            state = self._quotas.get(target)
            if state and state.is_valid(now):
                state.record_utilization(cost=1)
                if self.persist_path:
                    _save_disk_quota(self._quotas, self.persist_path)

            sleep_duration = max(0.0, scheduled_time - now)

        if sleep_duration > 0.0:
            logger.info(
                "[RateLimit] Mandatory pause for '%s': delaying %.2fs",
                target,
                sleep_duration,
            )
            time.sleep(sleep_duration)

        return sleep_duration

    def update_quota(
        self,
        subcommand: str,
        *,
        remaining: int,
        reset_epoch: float = 0.0,
        limit: int | None = None,
        used: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Update tracked remaining tokens and reset epoch from live response."""
        if remaining < 0:
            raise ValueError(f"remaining requests must be non-negative, got {remaining}")
        if limit is not None and limit < 0:
            raise ValueError(f"rate limit must be non-negative, got {limit}")
        if reset_epoch < 0.0:
            raise ValueError(f"reset_epoch must be non-negative, got {reset_epoch}")
        if used is not None and used < 0:
            raise ValueError(f"used requests must be non-negative, got {used}")

        now = time.time()
        with self._lock:
            state = self._quotas.setdefault(subcommand, QuotaState())
            state.remaining = remaining
            state.reset_epoch = reset_epoch
            if limit is not None:
                state.limit = limit
            if used is not None:
                state.used = used
            elif limit is not None:
                state.used = max(0, limit - state.remaining)
            state.last_updated = now
            state.validate()
            if self.persist_path:
                _save_disk_quota(self._quotas, self.persist_path)

    def record_utilization(self, subcommand: str, cost: int = 1) -> None:
        """Increment used count and decrement remaining quota based on request utilization.

        Cached values that are not updated on every request should never be used or relied on,
        so every request decrements remaining and increments used to maintain fresh utilization tracking.
        """
        with self._lock:
            state = self._quotas.get(subcommand)
            if state and state.is_valid():
                state.record_utilization(cost=cost)
                if self.persist_path:
                    _save_disk_quota(self._quotas, self.persist_path)

    def decrement_quota_estimate(self, subcommand: str, cost: int = 1) -> None:
        """Pessimistically decrement quota estimate when a command lacks rate limit headers."""
        self.record_utilization(subcommand, cost=cost)

    def get_quota(self, subcommand: str) -> QuotaState:
        """Retrieve a copy of current quota state for a subcommand."""
        with self._lock:
            state = self._quotas.setdefault(subcommand, QuotaState())
            return QuotaState(
                limit=state.limit,
                remaining=state.remaining,
                used=state.used,
                reset_epoch=state.reset_epoch,
                last_updated=state.last_updated,
            )

    def is_rate_limit_error(self, message: str) -> bool:
        """Detect whether an error output indicates primary or secondary GitHub rate limits."""
        if not message:
            return False
        clean = message.lower()
        return any(pattern in clean for pattern in CONST_GITHUB_RATE_LIMIT_PATTERNS)

    def calculate_backoff_delay(
        self, message: str, attempt: int = 1, subcommand: str = "core"
    ) -> float:
        """Calculate backoff delay for secondary rate limits or wait until reset."""
        if not self.is_rate_limit_error(message):
            return 0.0
        with self._lock:
            state = self._quotas.get(subcommand)
            if state and state.reset_epoch > 0.0:
                now = time.time()
                if state.reset_epoch > now:
                    return float(state.reset_epoch - now)
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
        """Store stdout payload into the ephemeral in-memory cache."""
        with self._lock:
            self._cache[key] = _CacheEntry(data=data, expires_at=time.time() + ttl)

    def clear_cache(self) -> None:
        """Clear all in-memory cached responses."""
        with self._lock:
            self._cache.clear()


_GLOBAL_RATE_LIMITER: GitHubRateLimiter | None = None
_GLOBAL_LOCK = threading.RLock()


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
            _GLOBAL_RATE_LIMITER = GitHubRateLimiter(
                persist_path=resolve_quota_cache_path(),
            )
        return _GLOBAL_RATE_LIMITER


def _should_cache(args: list[str], use_cache: bool, input: str | None = None) -> bool:
    """Determine whether a command is eligible for response caching."""
    if not use_cache or input:
        return False
    if not args:
        return False

    combined_args = " ".join(args).lower()
    sensitive_markers = ("token", "authorization", "bearer", "password", "secret", "cookie")
    if any(marker in combined_args for marker in sensitive_markers):
        return False

    first = args[0]
    if first in ("pr", "issue", "project", "label", "milestone", "repo", "workflow", "run"):
        read_verbs = {
            "view",
            "list",
            "status",
            "checks",
            "diff",
            "show",
            "item-list",
            "field-list",
        }
        return any(arg in read_verbs for arg in args[1:])

    if first == "api":
        has_post = any(
            arg.upper() == "POST"
            or arg.startswith("-XPOST")
            or arg == "--method=POST"
            or arg.startswith("-X=POST")
            for arg in args
        )
        has_field = any(arg in ("-f", "--field", "-F", "--raw-field") for arg in args)
        if has_post or has_field:
            return False
        return True

    return False


def _build_cache_key(args: list[str], input: str | None = None) -> str:
    """Construct deterministic cache key from command arguments."""
    key = "gh:" + ":".join(args)
    if input:
        key += f":{hash(input)}"
    return key


def _normalize_gh_args(args: list[str]) -> list[str]:
    """Strip redundant leading gh CLI executable if present in argument list."""
    if args and (args[0] == CONST_GH_CLI or args[0] == "gh"):
        return list(args[1:])
    return list(args)


def _validate_gh_cwd(cwd: Path | None) -> Path | None:
    """Validate that cwd exists, is a directory, and does not target forbidden system paths."""
    if cwd is None:
        return None
    p = Path(cwd)
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Invalid cwd directory: '{cwd}'")
    resolved = p.resolve()
    resolved_str = str(resolved)
    forbidden_prefixes = ("/etc", "/root", "/boot", "/dev", "/proc", "/sys")
    if any(resolved_str == f or resolved_str.startswith(f + "/") for f in forbidden_prefixes):
        raise ValueError(f"Prohibited system path for cwd: '{cwd}'")
    return resolved


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
        if isinstance(r_info, dict) and "remaining" in r_info:
            limiter.update_quota(
                r_name,
                remaining=int(r_info["remaining"]),
                limit=int(r_info["limit"]) if "limit" in r_info else None,
                used=int(r_info["used"]) if "used" in r_info else None,
                reset_epoch=float(r_info.get("reset", 0.0)),
            )


def _extract_page_per_page(url_or_endpoint: str) -> int:
    """Extract per_page from query string or default to 100."""
    if "per_page=" in url_or_endpoint:
        try:
            part = url_or_endpoint.split("per_page=", 1)[1].split("&", 1)[0]
            return int(part)
        except ValueError, IndexError:
            pass
    return 100


def _build_paginated_url(endpoint: str, page: int) -> str:
    """Append or update page query parameter in endpoint URL."""
    if "page=" in endpoint:
        import re

        return re.sub(r"([?&])page=\d+", rf"\g<1>page={page}", endpoint)
    sep = "&" if "?" in endpoint else "?"
    return f"{endpoint}{sep}page={page}"


def _find_api_endpoint_idx(args: list[str]) -> int:
    """Find index of API endpoint path within gh api argument list."""
    for idx, arg in enumerate(args):
        if idx > 0 and not arg.startswith("-"):
            return idx
    return -1


def _execute_single_page(
    base_args: list[str],
    endpoint_idx: int,
    base_endpoint: str,
    page: int,
    limiter: GitHubRateLimiter,
    target_resource: str,
    cwd: Path | None,
    quiet: bool,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Prepend calculated delay and execute a single page request."""
    page_endpoint = _build_paginated_url(base_endpoint, page)
    page_args = list(base_args)
    page_args[endpoint_idx] = page_endpoint

    limiter.acquire(subcommand=target_resource)
    proc = run_subprocess(
        [CONST_GH_CLI, *page_args],
        cwd=cwd,
        check=False,
        quiet=quiet,
        timeout=timeout,
    )
    _post_process_run(proc, target_resource, limiter, cost=1)
    return proc


def _run_gh_paginated(
    clean_args: list[str],
    limiter: GitHubRateLimiter,
    target_resource: str,
    cwd: Path | None = None,
    quiet: bool = False,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Execute a paginated gh api request page-by-page with mandatory delay prepended."""
    args_no_paginate = [a for a in clean_args if a != "--paginate"]
    endpoint_idx = _find_api_endpoint_idx(args_no_paginate)
    if endpoint_idx == -1:
        return run_subprocess(
            [CONST_GH_CLI, *clean_args], cwd=cwd, check=False, quiet=quiet, timeout=timeout
        )

    base_endpoint = args_no_paginate[endpoint_idx]
    per_page = _extract_page_per_page(base_endpoint)
    combined_items: list[Any] = []
    page = 1
    last_proc: subprocess.CompletedProcess[str] | None = None

    while True:
        proc = _execute_single_page(
            args_no_paginate,
            endpoint_idx,
            base_endpoint,
            page,
            limiter,
            target_resource,
            cwd,
            quiet,
            timeout,
        )
        last_proc = proc
        if proc.returncode != 0:
            return proc

        stdout_trimmed = (proc.stdout or "").strip()
        if not stdout_trimmed or stdout_trimmed == "[]":
            break

        data = extract_json_payload(stdout_trimmed)
        if not isinstance(data, list):
            return proc

        combined_items.extend(data)
        if len(data) < per_page:
            break
        page += 1

    return subprocess.CompletedProcess(
        args=[CONST_GH_CLI, *clean_args],
        returncode=0,
        stdout=json.dumps(combined_items),
        stderr=last_proc.stderr if last_proc else "",
    )


def _post_process_run(
    proc: subprocess.CompletedProcess[str],
    resource: str,
    limiter: GitHubRateLimiter,
    is_rate_limit_check: bool = False,
    cost: int = 1,
) -> None:
    """Extract rate limit metrics or record quota utilization."""
    if is_rate_limit_check and proc.stdout:
        _extract_rate_limit_endpoint_response(proc.stdout, limiter)
        return

    _parse_rate_limit_from_output(proc.stdout, resource, limiter)
    stdout_clean = proc.stdout or ""
    if "rateLimit" not in stdout_clean and "x-ratelimit-remaining" not in stdout_clean.lower():
        try:
            limiter.record_utilization(resource, cost=cost)
        except TypeError, ValueError:
            pass


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
    cost: int = 1,
) -> subprocess.CompletedProcess[str]:
    """Execute a GitHub CLI command via centralized rate limiting, pacing, backoff, and caching.

    Enforces mandatory pause calculated from:
        request delay = time in seconds until next quota reset for this subcommand / remaining requests
    """
    if cwd is not None:
        cwd = _validate_gh_cwd(cwd)
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

    if not is_check and "--paginate" in clean_args:
        proc = _run_gh_paginated(
            clean_args,
            limiter=limiter,
            target_resource=target_resource,
            cwd=cwd,
            quiet=quiet,
            timeout=timeout,
        )
        if _should_cache(clean_args, use_cache, input) and proc.returncode == 0 and proc.stdout:
            limiter.set_cached(cache_key, proc.stdout, ttl=cache_ttl)
        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, full_cmd, output=proc.stdout, stderr=proc.stderr
            )
        return proc

    for attempt in range(max_retries + 1):
        if not is_check:
            limiter.acquire(subcommand=target_resource)
        proc = run_subprocess(
            full_cmd, input=input, cwd=cwd, check=False, quiet=quiet, timeout=timeout
        )
        last_res = proc
        _post_process_run(proc, target_resource, limiter, is_rate_limit_check=is_check)

        if proc.returncode == 0:
            if _should_cache(clean_args, use_cache, input) and proc.stdout:
                limiter.set_cached(cache_key, proc.stdout, ttl=cache_ttl)
            return proc

        combined_err = (proc.stderr or "") + " " + (proc.stdout or "")
        if not limiter.is_rate_limit_error(combined_err) or attempt >= max_retries:
            break

        backoff = limiter.calculate_backoff_delay(
            combined_err, attempt=attempt + 1, subcommand=target_resource
        )
        logger.warning(
            "[RateLimit] Rate limit encountered on attempt %d for '%s'. Pausing %.2fs",
            attempt + 1,
            target_resource,
            backoff,
        )
        time.sleep(backoff)

    if check and last_res is not None and last_res.returncode != 0:
        raise subprocess.CalledProcessError(
            last_res.returncode,
            full_cmd,
            output=last_res.stdout,
            stderr=last_res.stderr,
        )

    return last_res or subprocess.CompletedProcess(
        args=full_cmd, returncode=1, stdout="", stderr=""
    )
