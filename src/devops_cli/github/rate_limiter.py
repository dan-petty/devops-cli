"""GitHub CLI rate limiter and request pacing subsystem.

Institutes a mandatory pause on gh requests calculated strictly from:
    request delay = time in seconds until next quota reset for this subcommand / remaining requests

No initial quotas, no hardcoded default windows, default request rate, or bursting.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from aiolimiter import AsyncLimiter
from ratelimit import limits, sleep_and_retry  # type: ignore[import-untyped]
from tenacity import RetryCallState, Retrying, wait_random_exponential

from devops_cli.config.constants import (
    CONST_CACHE_DIR_NAME,
    CONST_GH_API_DEFAULT_METHOD,
    CONST_GH_API_GRAPHQL_ENDPOINT,
    CONST_GH_CLI,
    CONST_GH_QUOTA_CACHE_FILENAME,
    CONST_GH_READ_VERBS,
    CONST_GITHUB_IDENTITY_DIGEST_CHARS,
    CONST_GITHUB_RATE_LIMIT_PATTERNS,
    CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS,
)
from devops_cli.config.defaults import (
    DEFAULT_DATA_DIR,
    DEFAULT_GH_CACHE_TTL_SECONDS,
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_MAX_RATE_LIMIT_WAIT,
    DEFAULT_GH_MUTATION_MIN_INTERVAL_SECONDS,
    DEFAULT_GH_QUOTA_MAX_AGE_SECONDS,
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_GH_SECONDARY_MAX_CAP,
    DEFAULT_GH_SECONDARY_RATE_WAIT,
)
from devops_cli.core.process import github_token, is_local_gh_command, run_subprocess
from devops_cli.exceptions.git import GitHubRateLimitError
from devops_cli.github.request_classifier import (
    gh_command_words,
    incompatible_gh_api_paginate_flag,
    is_write_gh_command,
    parse_gh_api_args,
)

logger = logging.getLogger(__name__)

_BURST_LIMIT_DECORATOR: Any = limits(calls=60, period=60)
# The high-level gh groups whose reads `run_gh` may answer from its response cache.
_CACHEABLE_CLI_GROUPS = frozenset(
    {"pr", "issue", "project", "label", "milestone", "repo", "workflow", "run"}
)


@sleep_and_retry  # type: ignore[untyped-decorator]
@_BURST_LIMIT_DECORATOR  # type: ignore[untyped-decorator]
def _burst_protected_subprocess(
    cmd: list[str],
    *,
    input: str | None = None,
    cwd: Path | None = None,
    check: bool = False,
    quiet: bool = False,
    timeout: float = 30.0,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute raw gh command through ratelimit burst-ceiling protector."""
    return run_subprocess(
        cmd,
        input=input,
        cwd=cwd,
        check=check,
        quiet=quiet,
        timeout=timeout,
        capture_output=capture_output,
    )


@dataclass
class _CacheEntry:
    data: str
    expires_at: float


def _validate_attr_value(name: str, value: Any) -> None:
    """Validate numeric boundaries on quota attributes."""
    if value is None:
        return
    if name in ("remaining", "limit", "used") and value < 0:
        label = "rate limit" if name == "limit" else f"{name} requests"
        raise ValueError(f"{label} must be non-negative, got {value}")
    if name in ("reset_epoch", "last_request_epoch") and value < 0.0:
        raise ValueError(f"{name} must be non-negative, got {value}")


@dataclass
class QuotaState:
    """Tracked rate limit metrics for a GitHub API resource / subcommand."""

    remaining: int | None = None
    limit: int | None = None
    reset_epoch: float | None = None
    last_updated: float | None = None
    used: int | None = None
    last_request_epoch: float | None = None

    def __setattr__(self, name: str, value: Any) -> None:
        _validate_attr_value(name, value)
        super().__setattr__(name, value)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate that all quota metrics are strictly non-negative when present."""
        int_fields = (
            ("remaining requests", self.remaining),
            ("rate limit", self.limit),
            ("used requests", self.used),
        )
        for name, val in int_fields:
            if val is not None and val < 0:
                raise ValueError(f"{name} must be non-negative, got {val}")

        float_fields = (
            ("reset_epoch", self.reset_epoch),
            ("last_request_epoch", self.last_request_epoch),
            ("last_updated", self.last_updated),
        )
        for name, f_val in float_fields:
            if f_val is not None and f_val < 0.0:
                raise ValueError(f"{name} must be non-negative, got {f_val}")

    def is_valid(self, now: float | None = None, max_age: float | None = None) -> bool:
        """Return True if cached quota is active and has not expired past reset epoch or max age.

        Cached values that are not updated on every request or past reset epoch
        should never be used or relied on.
        """
        current_time = now if now is not None else time.time()
        if max_age is not None and self.last_updated is not None:
            if (current_time - self.last_updated) > max_age:
                return False
        return (
            self.remaining is not None
            and self.reset_epoch is not None
            and self.reset_epoch > current_time
        )

    def record_utilization(self, cost: int = 1) -> None:
        """Update quota utilization: decrement remaining and increment used."""
        if cost < 0:
            raise ValueError(f"utilization cost must be non-negative, got {cost}")
        if self.remaining is not None:
            self.remaining = max(0, self.remaining - cost)
        if self.used is not None:
            self.used += cost
        now = time.time()
        self.last_updated = now
        self.last_request_epoch = now
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "used": self.used,
            "reset_epoch": self.reset_epoch,
            "last_updated": self.last_updated,
            "last_request_epoch": self.last_request_epoch,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuotaState:
        """Construct from dictionary preserving None for unknown metrics without defaulting to 0."""
        if not isinstance(data, dict):
            raise GitHubRateLimitError(f"Expected dict for QuotaState, got {type(data).__name__}")
        try:
            limit_val = data.get("limit")
            limit = int(limit_val) if limit_val is not None else None
            rem_val = data.get("remaining")
            remaining = int(rem_val) if rem_val is not None else None
            used_val = data.get("used")
            used = int(used_val) if used_val is not None else None
            reset_val = data.get("reset_epoch")
            reset_epoch = float(reset_val) if reset_val is not None else None
            updated_val = data.get("last_updated")
            last_updated = float(updated_val) if updated_val is not None else None
            last_req_val = data.get("last_request_epoch")
            last_req = float(last_req_val) if last_req_val is not None else None
            return cls(
                limit=limit,
                remaining=remaining,
                used=used,
                reset_epoch=reset_epoch,
                last_updated=last_updated,
                last_request_epoch=last_req,
            )
        except (TypeError, ValueError) as err:
            raise ValueError(f"Malformed quota state dictionary: {err}") from err


_DISK_LOCK_STATE = threading.local()


def _acquire_advisory_lock(lock_file: Path) -> tuple[Any, bool]:
    """Acquire advisory file lock, returning file descriptor and lock status."""
    fd: Any = None
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        # Caller holds the open file to maintain the advisory flock; a with-block would close and release it.
        fd = open(lock_file, "a+", encoding="utf-8")  # noqa: SIM115
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        _DISK_LOCK_STATE.depth[lock_file] = 1
        return fd, True
    except (OSError, AttributeError) as err:
        logger.warning("Advisory file locking unavailable on %s: %s", lock_file, err)
        if fd is not None:
            try:
                fd.close()
            except OSError:
                pass
        return None, False


def _release_advisory_lock(fd: Any, lock_file: Path, locked: bool) -> None:
    """Release advisory file lock and close descriptor."""
    if locked and fd is not None:
        _DISK_LOCK_STATE.depth[lock_file] = 0
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
    if fd is not None:
        try:
            fd.close()
        except OSError:
            pass


@contextmanager
def _disk_quota_lock(path: Path) -> Generator[None]:
    """Acquire an exclusive re-entrant cross-process advisory lock on the quota cache file."""
    lock_file = path.with_suffix(".lock")
    if not hasattr(_DISK_LOCK_STATE, "depth"):
        _DISK_LOCK_STATE.depth = {}

    current_depth = _DISK_LOCK_STATE.depth.get(lock_file, 0)
    if current_depth > 0:
        _DISK_LOCK_STATE.depth[lock_file] = current_depth + 1
        try:
            yield
        finally:
            _DISK_LOCK_STATE.depth[lock_file] -= 1
        return

    fd, locked = _acquire_advisory_lock(lock_file)
    try:
        yield
    finally:
        _release_advisory_lock(fd, lock_file, locked)


def _load_disk_quota(path: Path) -> dict[str, QuotaState]:
    """Load persistent rate limit quota state from disk, discarding expired or stale entries."""
    if not path.is_file():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        raw = json.loads(content)
    except (OSError, json.JSONDecodeError) as err:
        logger.warning("Failed to read GitHub rate limit quota from %s: %s", path, err)
        return {}

    now = time.time()
    if not isinstance(raw, dict):
        logger.warning("Malformed quota cache at %s: expected JSON object", path)
        return {}

    valid_quotas: dict[str, QuotaState] = {}
    for k, v in raw.items():
        if k == "_global" or not isinstance(v, dict):
            continue
        try:
            state = QuotaState.from_dict(v)
            if state.is_valid(now):
                valid_quotas[k] = state
        except (TypeError, ValueError) as err:
            logger.warning("Discarding malformed quota entry for '%s' in %s: %s", k, path, err)
            continue
    return valid_quotas


def _load_disk_global_meta(path: Path) -> tuple[int, float, int, float]:
    """Load global request count, last request timestamp, total throttles, and wait seconds from disk."""
    if not path.is_file():
        return 0, 0.0, 0, 0.0
    try:
        content = path.read_text(encoding="utf-8")
        raw = json.loads(content)
        if isinstance(raw, dict):
            g = raw.get("_global", {})
            if isinstance(g, dict):
                total = int(g.get("total_requests", 0))
                last_epoch = float(g.get("last_request_epoch", 0.0))
                throttles = int(g.get("total_throttles", 0))
                wait_sec = float(g.get("total_wait_seconds", 0.0))
                return max(0, total), max(0.0, last_epoch), max(0, throttles), max(0.0, wait_sec)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as err:
        logger.warning("Failed to load global rate limit metadata from %s: %s", path, err)
    return 0, 0.0, 0, 0.0


def _save_disk_quota(
    quotas: dict[str, QuotaState],
    path: Path,
    total_requests: int = 0,
    last_request_epoch: float = 0.0,
    total_throttles: int = 0,
    total_wait_seconds: float = 0.0,
) -> None:
    """Persist rate limit quota state and global request metrics to disk atomically."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "_global": {
                "total_requests": max(0, total_requests),
                "last_request_epoch": max(0.0, last_request_epoch),
                "total_throttles": max(0, total_throttles),
                "total_wait_seconds": max(0.0, total_wait_seconds),
            }
        }
        for k, v in quotas.items():
            if k != "_global":
                payload[k] = v.to_dict()
        tmp = path.with_suffix(f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as err:
        logger.warning("Failed to persist GitHub rate limit quota to disk at %s: %s", path, err)


def _merge_same_epoch_quota(disk_state: QuotaState, mem_state: QuotaState) -> QuotaState:
    """Merge quota states that share the same reset epoch."""
    if disk_state.remaining is None:
        rem = mem_state.remaining
    elif mem_state.remaining is None:
        rem = disk_state.remaining
    else:
        rem = min(disk_state.remaining, mem_state.remaining)

    used_vals = [v for v in (disk_state.used, mem_state.used) if v is not None]
    used = max(used_vals) if used_vals else None
    limit = disk_state.limit or mem_state.limit
    updated_vals = [v for v in (disk_state.last_updated, mem_state.last_updated) if v is not None]
    last_updated = max(updated_vals) if updated_vals else None
    req_vals = [
        v for v in (disk_state.last_request_epoch, mem_state.last_request_epoch) if v is not None
    ]
    last_request = max(req_vals) if req_vals else None
    return QuotaState(
        limit=limit,
        remaining=rem,
        used=used,
        reset_epoch=disk_state.reset_epoch,
        last_updated=last_updated,
        last_request_epoch=last_request,
    )


def _merge_single_quota(disk_state: QuotaState, mem_state: QuotaState) -> QuotaState:
    """Merge disk quota state with in-memory quota state preserving freshest consumption."""
    if disk_state.reset_epoch is None:
        return mem_state
    if mem_state.reset_epoch is None:
        return disk_state
    if disk_state.reset_epoch == mem_state.reset_epoch:
        return _merge_same_epoch_quota(disk_state, mem_state)
    return disk_state if disk_state.reset_epoch > mem_state.reset_epoch else mem_state


def extract_json_payload(raw_stdout: str) -> Any:
    """Extract first valid JSON object or array from output, ignoring preambles."""
    if not isinstance(raw_stdout, str) or not raw_stdout:
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
    except json.JSONDecodeError as err:
        logger.debug("Failed to extract JSON payload from candidate substring: %s", err)
        return None


def calculate_request_delay(
    time_until_reset: float,
    remaining: int,
    limit: int | None = None,
) -> float:
    """Calculate request delay = time until reset / remaining requests.

    Raises ValueError if time_until_reset, remaining, or limit is negative.
    When quota is exhausted (remaining == 0), delay is the full time until reset,
    forcing the rate to zero until requests become available under the reset.
    """
    if time_until_reset < 0.0:
        raise ValueError(f"time_until_reset must be non-negative, got {time_until_reset}")
    if remaining < 0:
        raise ValueError(f"remaining requests must be non-negative, got {remaining}")
    if limit is not None and limit < 0:
        raise ValueError(f"rate limit must be non-negative, got {limit}")

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


def gh_request_resource(args: list[str]) -> str:
    """The rate-limit resource a `gh` command spends (`core`, `graphql`, `search`, ...), as
    `run_gh` paces it."""
    return _detect_resource(_normalize_gh_args(args))


def _parse_reset_epoch(reset_at: str | None) -> float | None:
    """Parse ISO resetAt string into epoch timestamp."""
    if not reset_at:
        return None
    try:
        clean = reset_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.timestamp()
    except (ValueError, TypeError) as err:
        raise ValueError(f"Failed to parse resetAt timestamp '{reset_at}': {err}") from err


def _extract_graphql_ratelimit_json(output: str, limiter: GitHubRateLimiter) -> None:
    """Charge the points a GraphQL response's `rateLimit` reports it cost, and track the points
    left; a response without one is charged only `acquire`'s estimate."""
    payload = extract_json_payload(output)
    if not isinstance(payload, dict):
        return
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return
    rl = data.get("rateLimit")
    if isinstance(rl, dict):
        cost = rl.get("cost")
        if isinstance(cost, int):
            limiter.charge_points("graphql", cost)
        rem = rl.get("remaining")
        lim = rl.get("limit")
        used = rl.get("used")
        reset_at = rl.get("resetAt")
        if rem is not None:
            epoch = _parse_reset_epoch(str(reset_at)) if reset_at else None
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


def _parse_float_safe(value: str, default: float | None = None) -> float | None:
    """Parse string float safely without exceptions."""
    try:
        return float(value.strip())
    except ValueError, TypeError:
        return default


def _parse_retry_after_safe(value: str, default: float | None = None) -> float | None:
    """Parse string Retry-After value safely as float seconds or HTTP-date."""
    seconds = _parse_float_safe(value)
    if seconds is not None:
        return seconds
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(value.strip())
        delay = dt.timestamp() - time.time()
        return max(0.0, delay)
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
        "retry-after": ("retry_after", _parse_retry_after_safe),
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


def extract_retry_after(message: str) -> float | None:
    """Extract Retry-After duration in seconds from headers or error message."""
    if not message:
        return None
    metrics = _process_header_metrics(message)
    if metrics.get("retry_after") is not None:
        return float(metrics["retry_after"])
    match = re.search(r"retry[- ]after[:\s]+(\d+(?:\.\d+)?)", message, re.IGNORECASE)
    if match:
        val = _parse_float_safe(match.group(1))
        if val is not None and val >= 0.0:
            return val
    return None


def _extract_header_ratelimit(output: str, resource: str, limiter: GitHubRateLimiter) -> None:
    """Parse HTTP headers from output for x-ratelimit metrics."""
    metrics = _process_header_metrics(output)
    if metrics.get("remaining") is not None:
        limiter.update_quota(
            resource,
            remaining=metrics["remaining"],
            reset_epoch=metrics.get("reset_epoch"),
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


def _handle_retry_after_wait(
    retry_after: float,
    max_rate_limit_wait: float | None,
    subcommand: str,
) -> float:
    """Validate and return server Retry-After delay unchanged without clamping."""
    if max_rate_limit_wait is not None and retry_after > max_rate_limit_wait:
        raise GitHubRateLimitError(
            f"Required Retry-After wait of {retry_after:.1f}s exceeds max_rate_limit_wait of {max_rate_limit_wait:.1f}s",
            subcommand=subcommand,
            details={"wait": retry_after, "max_rate_limit_wait": max_rate_limit_wait},
        )
    return retry_after


def _is_primary_exhausted(state: QuotaState | None) -> bool:
    """Check if quota state indicates primary rate limit exhaustion (remaining == 0)."""
    return (
        state is not None
        and state.remaining == 0
        and state.reset_epoch is not None
        and state.reset_epoch > 0.0
    )


def _calculate_primary_delay(
    state: QuotaState | None,
    max_rate_limit_wait: float | None,
    subcommand: str,
) -> float | None:
    """Calculate wait until reset epoch for primary rate limits (remaining == 0)."""
    if not _is_primary_exhausted(state) or state is None or state.reset_epoch is None:
        return None
    now = time.time()
    if state.reset_epoch <= now:
        return None
    wait = float(state.reset_epoch - now)
    if max_rate_limit_wait is not None and wait > max_rate_limit_wait:
        reset_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(state.reset_epoch))
        raise GitHubRateLimitError(
            f"Required primary rate limit wait of {wait:.1f}s (reset at {reset_iso}) exceeds max_rate_limit_wait of {max_rate_limit_wait:.1f}s",
            subcommand=subcommand,
            details={
                "wait": wait,
                "reset_epoch": state.reset_epoch,
                "max_rate_limit_wait": max_rate_limit_wait,
            },
        )
    return wait


def _calculate_secondary_delay(
    attempt: int,
    floor: float,
    max_cap: float,
    max_rate_limit_wait: float | None,
    subcommand: str,
) -> float:
    """Calculate secondary rate limit delay using floor and tenacity wait_random_exponential."""
    retry_state = RetryCallState(retry_object=Retrying(), fn=None, args=(), kwargs={})
    retry_state.attempt_number = max(1, attempt)
    wait_strategy = wait_random_exponential(multiplier=1.0, max=max_cap)
    tenacity_wait = float(wait_strategy(retry_state))
    delay = min(floor + tenacity_wait, max_cap)
    if max_rate_limit_wait is not None and delay > max_rate_limit_wait:
        raise GitHubRateLimitError(
            f"Required secondary rate limit backoff of {delay:.1f}s exceeds max_rate_limit_wait of {max_rate_limit_wait:.1f}s",
            subcommand=subcommand,
            details={"wait": delay, "max_rate_limit_wait": max_rate_limit_wait},
        )
    return delay


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
        mutation_min_interval: float = DEFAULT_GH_MUTATION_MIN_INTERVAL_SECONDS,
        quota_max_age: float = DEFAULT_GH_QUOTA_MAX_AGE_SECONDS,
        secondary_rate_wait: float = DEFAULT_GH_SECONDARY_RATE_WAIT,
        secondary_max_cap: float = DEFAULT_GH_SECONDARY_MAX_CAP,
        max_rate_limit_wait: float | None = DEFAULT_GH_MAX_RATE_LIMIT_WAIT,
    ) -> None:
        if mutation_min_interval < 0.0:
            raise ValueError(
                f"mutation_min_interval must be non-negative, got {mutation_min_interval}"
            )
        if quota_max_age < 0.0:
            raise ValueError(f"quota_max_age must be non-negative, got {quota_max_age}")
        if secondary_rate_wait < 0.0:
            raise ValueError(f"secondary_rate_wait must be non-negative, got {secondary_rate_wait}")
        if secondary_max_cap < 0.0:
            raise ValueError(f"secondary_max_cap must be non-negative, got {secondary_max_cap}")
        if max_rate_limit_wait is not None and max_rate_limit_wait < 0.0:
            raise ValueError(f"max_rate_limit_wait must be non-negative, got {max_rate_limit_wait}")
        self.persist_path = persist_path
        self.min_interval = min_interval
        self.fallback_delay = fallback_delay
        self.mutation_min_interval = mutation_min_interval
        self.quota_max_age = quota_max_age
        self.secondary_rate_wait = secondary_rate_wait
        self.secondary_max_cap = secondary_max_cap
        self.max_rate_limit_wait = max_rate_limit_wait
        self._lock = threading.RLock()
        self._cache: dict[str, _CacheEntry] = {}
        self._next_allowed_time: dict[str, float] = {}
        self._last_mutation_epoch: float = 0.0
        self._async_limiters: dict[str, AsyncLimiter] = {}
        self._is_refreshing: bool = False
        self._total_requests: int = 0
        # GraphQL points the responses reported, by resource (#1125).
        self._points_charged: dict[str, int] = {}
        self._last_request_epoch: float = 0.0
        self._last_disk_prune_epoch: float = 0.0
        self._total_throttles: int = 0
        self._total_wait_seconds: float = 0.0
        self._quotas: dict[str, QuotaState] = {}
        if persist_path:
            self._sync_from_disk_locked()
            self.prune_expired_cache()

    def get_async_limiter(self, subcommand: str = "core") -> AsyncLimiter:
        """Retrieve or create an aiolimiter.AsyncLimiter instance for the resource."""
        with self._lock:
            if subcommand not in self._async_limiters:
                self._async_limiters[subcommand] = AsyncLimiter(max_rate=60, time_period=60)
            return self._async_limiters[subcommand]

    def _sync_from_disk_locked(self) -> None:
        """Synchronize in-memory quotas and global request counts with disk."""
        if not self.persist_path:
            return
        disk_quotas = _load_disk_quota(self.persist_path)
        disk_reqs, disk_last_req, disk_throttles, disk_wait_sec = _load_disk_global_meta(
            self.persist_path
        )
        self._total_requests = max(self._total_requests, disk_reqs)
        self._last_request_epoch = max(self._last_request_epoch, disk_last_req)
        self._total_throttles = max(self._total_throttles, disk_throttles)
        self._total_wait_seconds = max(self._total_wait_seconds, disk_wait_sec)
        for subcmd, d_state in disk_quotas.items():
            if subcmd in self._quotas:
                self._quotas[subcmd] = _merge_single_quota(d_state, self._quotas[subcmd])
            else:
                self._quotas[subcmd] = d_state

    def _persist_to_disk_locked(self) -> None:
        """Persist state to disk under lock."""
        if self.persist_path:
            _save_disk_quota(
                self._quotas,
                self.persist_path,
                total_requests=self._total_requests,
                last_request_epoch=self._last_request_epoch,
                total_throttles=self._total_throttles,
                total_wait_seconds=self._total_wait_seconds,
            )

    def record_throttle(self, wait_seconds: float) -> None:
        """Record rate-limit throttle event and sleep duration."""
        with self._lock:
            self._total_throttles += 1
            self._total_wait_seconds += max(0.0, wait_seconds)
            self._persist_to_disk_locked()

    def get_total_throttles(self) -> int:
        """Return total tracked rate limit throttle events across processes."""
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    self._sync_from_disk_locked()
            return self._total_throttles

    def get_total_wait_seconds(self) -> float:
        """Return total accumulated backoff wait seconds across processes."""
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    self._sync_from_disk_locked()
            return self._total_wait_seconds

    def get_global_request_count(self) -> int:
        """Return total tracked global requests across all processes."""
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    self._sync_from_disk_locked()
            return self._total_requests

    def get_last_request_epoch(self) -> float:
        """Return timestamp of the most recent global request."""
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    self._sync_from_disk_locked()
            return self._last_request_epoch

    def get_all_quotas(self) -> dict[str, QuotaState]:
        """Return all tracked quotas synced from disk."""
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    self._sync_from_disk_locked()
            return {
                k: QuotaState(
                    limit=v.limit,
                    remaining=v.remaining,
                    used=v.used,
                    reset_epoch=v.reset_epoch,
                    last_updated=v.last_updated,
                    last_request_epoch=v.last_request_epoch,
                )
                for k, v in self._quotas.items()
            }

    def _resolve_quota_state(self, subcommand: str) -> QuotaState:
        """Retrieve or refresh quota state for subcommand under lock.

        Raises GitHubRateLimitError if state is broken or unknown and cannot be refreshed.
        """
        if self.persist_path:
            self._sync_from_disk_locked()

        now = time.time()
        state = self._quotas.get(subcommand)
        if state and state.is_valid(now, max_age=self.quota_max_age):
            return state

        if not self._is_refreshing:
            self._is_refreshing = True
            try:
                self._refresh_from_github()
            finally:
                self._is_refreshing = False
            state = self._quotas.get(subcommand)
            if state and state.is_valid(now, max_age=self.quota_max_age):
                return state

        raise GitHubRateLimitError(
            f"Rate limit state for subcommand '{subcommand}' is in an unknown or broken state "
            f"and could not be refreshed from GitHub",
            subcommand=subcommand,
            details={
                "subcommand": subcommand[:256],
                "remaining": str(getattr(state, "remaining", None)),
                "reset_epoch": str(getattr(state, "reset_epoch", None)),
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
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    state = self._resolve_quota_state(subcommand)
            else:
                state = self._resolve_quota_state(subcommand)

            now = time.time()
            if state.reset_epoch is None:
                raise GitHubRateLimitError(
                    f"reset_epoch is unknown for subcommand '{subcommand}'",
                    subcommand=subcommand,
                )
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
            )
            return max(self.min_interval, delay)

    def _calculate_target_delay(self, target: str, is_mutation: bool) -> float:
        """Calculate request pacing delay strictly from tracked quota state."""
        delay = self.calculate_delay(target)
        if is_mutation:
            delay = max(delay, self.mutation_min_interval)
        return delay

    def acquire(
        self,
        subcommand: str = "core",
        resource: str | None = None,
        is_mutation: bool = False,
        cost: int = 1,
    ) -> float:
        """Institute mandatory pause of the request delay calculated for that subcommand.

        Synchronizes global tracking across processes and serializes requests.
        """
        target = resource or subcommand
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    sleep_duration = self._acquire_locked(
                        target, is_mutation=is_mutation, cost=cost
                    )
            else:
                sleep_duration = self._acquire_locked(target, is_mutation=is_mutation, cost=cost)

        if sleep_duration > 0.0:
            logger.info(
                "[RateLimit] Mandatory pause for '%s': delaying %.2fs",
                target,
                sleep_duration,
            )
            time.sleep(sleep_duration)

        return sleep_duration

    def _acquire_locked(self, target: str, is_mutation: bool = False, cost: int = 1) -> float:
        """Internal lock-guarded execution of rate limit acquisition."""
        if self.persist_path:
            self._sync_from_disk_locked()
        now = time.time()

        delay = self._calculate_target_delay(target, is_mutation)
        state = self._quotas.get(target)

        prev_scheduled = self._next_allowed_time.get(target, 0.0)
        if prev_scheduled < now or (
            state and state.reset_epoch is not None and state.reset_epoch <= now
        ):
            prev_scheduled = now

        # The resource's own schedule follows its quota alone; only the write itself moves to
        # the write slot, so reads after it are never held by another resource's write.
        paced_time = max(now, prev_scheduled) + delay
        scheduled_time = self._write_slot_locked(paced_time) if is_mutation else paced_time
        sleep_duration = max(0.0, scheduled_time - now)

        self._next_allowed_time[target] = paced_time
        self._last_request_epoch = now + sleep_duration
        if is_mutation:
            self._last_mutation_epoch = scheduled_time
        if state and state.is_valid(now, max_age=self.quota_max_age):
            state.record_utilization(cost=cost)
        self._total_requests += 1
        self._persist_to_disk_locked()

        return sleep_duration

    def _write_slot_locked(self, scheduled_time: float) -> float:
        """A write's slot: at least `mutation_min_interval` after the last write was scheduled,
        whichever resource either uses, so concurrent callers in one process share the spacing."""
        return max(scheduled_time, self._last_mutation_epoch + self.mutation_min_interval)

    @staticmethod
    def _validate_quota_update_args(
        remaining: int,
        reset_epoch: float | None,
        limit: int | None,
        used: int | None,
    ) -> None:
        """Validate non-negative bounds for update_quota parameters."""
        if remaining < 0:
            raise ValueError(f"remaining requests must be non-negative, got {remaining}")
        for name, val in (("rate limit", limit), ("used requests", used)):
            if val is not None and val < 0:
                raise ValueError(f"{name} must be non-negative, got {val}")
        if reset_epoch is not None and reset_epoch < 0.0:
            raise ValueError(f"reset_epoch must be non-negative, got {reset_epoch}")

    def _apply_quota_update_locked(
        self,
        subcommand: str,
        remaining: int,
        reset_epoch: float | None,
        limit: int | None,
        used: int | None,
        now: float,
    ) -> None:
        """Apply quota update syncing and persisting to disk when configured."""
        if self.persist_path:
            with _disk_quota_lock(self.persist_path):
                self._sync_from_disk_locked()
                self._apply_quota_update(subcommand, remaining, reset_epoch, limit, used, now)
                self._persist_to_disk_locked()
        else:
            self._apply_quota_update(subcommand, remaining, reset_epoch, limit, used, now)

    def update_quota(
        self,
        subcommand: str,
        *,
        remaining: int,
        reset_epoch: float | None = None,
        limit: int | None = None,
        used: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Update tracked remaining tokens and reset epoch from live response."""
        self._validate_quota_update_args(remaining, reset_epoch, limit, used)
        now = time.time()
        with self._lock:
            self._apply_quota_update_locked(subcommand, remaining, reset_epoch, limit, used, now)

    def _apply_quota_update(
        self,
        subcommand: str,
        remaining: int,
        reset_epoch: float | None,
        limit: int | None,
        used: int | None,
        now: float,
    ) -> None:
        """Apply in-memory updates to quota state without resetting utilization on unknown values."""
        state = self._quotas.get(subcommand)
        if state is None:
            self._quotas[subcommand] = QuotaState(
                limit=limit,
                remaining=remaining,
                used=used,
                reset_epoch=reset_epoch,
                last_updated=now,
            )
            return

        state.remaining = remaining
        if reset_epoch is not None:
            state.reset_epoch = reset_epoch
        if limit is not None:
            state.limit = limit
        if used is not None:
            state.used = used
        state.last_updated = now
        state.validate()

    def record_utilization(self, subcommand: str, cost: int = 1) -> None:
        """Increment used count and decrement remaining quota based on request utilization."""
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    self._sync_from_disk_locked()
                    self._record_utilization_locked(subcommand, cost)
                    self._persist_to_disk_locked()
            else:
                self._record_utilization_locked(subcommand, cost)

    def _record_utilization_locked(self, subcommand: str, cost: int) -> None:
        state = self._quotas.get(subcommand)
        if state and state.is_valid():
            state.record_utilization(cost=cost)
            self._total_requests += cost

    def charge_points(self, subcommand: str, points: int) -> None:
        """Charge `points`, the cost a response reported, to `subcommand` (#1125)."""
        if points < 0:
            raise ValueError(f"charged points must be non-negative, got {points}")
        with self._lock:
            self._points_charged[subcommand] = self._points_charged.get(subcommand, 0) + points

    def points_charged(self, subcommand: str) -> int:
        """The points the responses on `subcommand` reported they cost."""
        with self._lock:
            return self._points_charged.get(subcommand, 0)

    def decrement_quota_estimate(self, subcommand: str, cost: int = 1) -> None:
        """Pessimistically decrement quota estimate when a command lacks rate limit headers."""
        self.record_utilization(subcommand, cost=cost)

    def get_quota(self, subcommand: str) -> QuotaState:
        """Retrieve a copy of current quota state for a subcommand synced with disk."""
        with self._lock:
            if self.persist_path:
                with _disk_quota_lock(self.persist_path):
                    self._sync_from_disk_locked()
            state = self._quotas.get(subcommand)
            if state is None:
                return QuotaState()
            return QuotaState(
                limit=state.limit,
                remaining=state.remaining,
                used=state.used,
                reset_epoch=state.reset_epoch,
                last_updated=state.last_updated,
                last_request_epoch=state.last_request_epoch,
            )

    def is_rate_limit_error(self, message: str) -> bool:
        """Detect whether an error output indicates primary or secondary GitHub rate limits."""
        if not message:
            return False
        clean = message.lower()
        return any(pattern in clean for pattern in CONST_GITHUB_RATE_LIMIT_PATTERNS)

    def is_secondary_rate_limit(self, message: str) -> bool:
        """Detect whether an error output indicates a secondary rate limit."""
        if not message:
            return False
        clean = message.lower()
        return any(pattern in clean for pattern in CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS)

    def calculate_backoff_delay(
        self, message: str, attempt: int = 1, subcommand: str = "core"
    ) -> float:
        """Calculate backoff delay for primary, secondary, or Retry-After rate limits."""
        if not self.is_rate_limit_error(message):
            return 0.0

        retry_after = extract_retry_after(message)
        if retry_after is not None and retry_after > 0.0:
            return _handle_retry_after_wait(retry_after, self.max_rate_limit_wait, subcommand)

        with self._lock:
            state = self._quotas.get(subcommand)

        primary_delay = _calculate_primary_delay(state, self.max_rate_limit_wait, subcommand)
        if primary_delay is not None:
            return primary_delay

        return _calculate_secondary_delay(
            attempt,
            floor=self.secondary_rate_wait,
            max_cap=self.secondary_max_cap,
            max_rate_limit_wait=self.max_rate_limit_wait,
            subcommand=subcommand,
        )

    def get_cached(self, key: str) -> str | None:
        """Retrieve unexpired cached stdout string for an idempotent query."""
        with self._lock:
            entry = self._cache.get(key)
            now = time.time()
            if entry is not None and now <= entry.expires_at:
                return entry.data
            if entry is not None:
                del self._cache[key]
            if self.persist_path:
                cache_dir = self.persist_path.parent / "responses"
                disk_entry = _load_disk_cache(cache_dir, key)
                if disk_entry is not None:
                    self._cache[key] = disk_entry
                    return disk_entry.data
            return None

    def set_cached(self, key: str, data: str, ttl: float = DEFAULT_GH_CACHE_TTL_SECONDS) -> None:
        """Store stdout payload into ephemeral and persistent disk cache."""
        with self._lock:
            entry = _CacheEntry(data=data, expires_at=time.time() + ttl)
            self._cache[key] = entry
            if self.persist_path:
                cache_dir = self.persist_path.parent / "responses"
                _save_disk_cache(cache_dir, key, entry)
                if time.time() - self._last_disk_prune_epoch > DEFAULT_GH_CACHE_TTL_SECONDS:
                    self.prune_expired_cache()

    def clear_cache(self) -> None:
        """Clear all in-memory and persistent cached responses."""
        with self._lock:
            self._cache.clear()
            if self.persist_path:
                cache_dir = self.persist_path.parent / "responses"
                shutil.rmtree(cache_dir, ignore_errors=True)

    def prune_expired_cache(self) -> int:
        """Prune expired in-memory entries and disk response cache files."""
        with self._lock:
            now = time.time()
            self._last_disk_prune_epoch = now
            expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
            for k in expired_keys:
                del self._cache[k]
            disk_pruned = 0
            if self.persist_path:
                cache_dir = self.persist_path.parent / "responses"
                disk_pruned = _prune_disk_cache(cache_dir, now=now)
            return len(expired_keys) + disk_pruned


def _is_expired_or_corrupt(entry_file: Path, now: float) -> bool:
    """Check if cache file is expired or corrupted."""
    try:
        data = json.loads(entry_file.read_text(encoding="utf-8"))
        return now > float(data.get("expires_at", 0.0))
    except OSError, ValueError, TypeError:
        return True


def _prune_disk_cache(cache_dir: Path, now: float | None = None) -> int:
    """Prune expired cache files from response cache directory, returning count of removed files."""
    if not cache_dir.is_dir():
        return 0
    removed = 0
    current_time = time.time() if now is None else now
    try:
        for entry_file in cache_dir.glob("*.json"):
            if _is_expired_or_corrupt(entry_file, current_time):
                entry_file.unlink(missing_ok=True)
                removed += 1
    except OSError:
        pass
    return removed


def _load_disk_cache(cache_dir: Path, key: str) -> _CacheEntry | None:
    """Load unexpired cache entry from disk."""
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    entry_file = cache_dir / f"{key_hash}.json"
    if not entry_file.exists():
        return None
    try:
        data = json.loads(entry_file.read_text(encoding="utf-8"))
        expires_at = float(data.get("expires_at", 0.0))
        if time.time() > expires_at:
            entry_file.unlink(missing_ok=True)
            return None
        return _CacheEntry(data=str(data.get("data", "")), expires_at=expires_at)
    except (OSError, ValueError, TypeError) as _err:
        return None


def _save_disk_cache(cache_dir: Path, key: str, entry: _CacheEntry) -> None:
    """Persist cache entry to disk."""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        entry_file = cache_dir / f"{key_hash}.json"
        payload = json.dumps({"expires_at": entry.expires_at, "data": entry.data})
        entry_file.write_text(payload, encoding="utf-8")
    except OSError:
        pass


_GLOBAL_RATE_LIMITER: GitHubRateLimiter | None = None
_GLOBAL_LOCK = threading.RLock()


def resolve_identity_cache_dir(token: str) -> Path:
    """The directory of the identity `token` is, under the cache dir, honoring DEVOPS_CLI_DATA_DIR.

    It is named by the first hex characters of the token's SHA-256, so no path holds the token
    or the login. Two tokens of one account get two directories; each answer's headers correct
    the figures.
    """
    env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    base_dir = Path(env_dir) if env_dir else DEFAULT_DATA_DIR
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return base_dir / CONST_CACHE_DIR_NAME / digest[:CONST_GITHUB_IDENTITY_DIGEST_CHARS]


def resolve_quota_cache_path() -> Path:
    """The session identity's quota ledger; its response cache sits beside it."""
    return resolve_identity_cache_dir(github_token()) / CONST_GH_QUOTA_CACHE_FILENAME


def reset_github_rate_limiter() -> None:
    """Reset the global rate limiter instance (useful for test isolation)."""
    global _GLOBAL_RATE_LIMITER
    with _GLOBAL_LOCK:
        _GLOBAL_RATE_LIMITER = None


def get_github_rate_limiter() -> GitHubRateLimiter:
    """The rate limiter of the session's identity, keeping that identity's quota and cache."""
    global _GLOBAL_RATE_LIMITER
    persist_path = resolve_quota_cache_path()
    with _GLOBAL_LOCK:
        if _GLOBAL_RATE_LIMITER is None or _GLOBAL_RATE_LIMITER.persist_path != persist_path:
            _GLOBAL_RATE_LIMITER = GitHubRateLimiter(persist_path=persist_path)
        return _GLOBAL_RATE_LIMITER


def _is_sensitive_command(args: list[str]) -> bool:
    """Check if command contains sensitive tokens or credentials."""
    combined_args = " ".join(args).lower()
    sensitive_markers = ("token", "authorization", "bearer", "password", "secret", "cookie")
    return any(marker in combined_args for marker in sensitive_markers)


def _is_cacheable_cli_read(args: list[str]) -> bool:
    """Whether a high-level gh command is a cacheable read: its group is one whose listings are
    cached, and its verb, in the verb position, reads. A read verb elsewhere in argv, as in
    `pr create --title list`, does not make it one."""
    words = gh_command_words(args)
    if words is None:
        return False
    group, verb = words
    return group in _CACHEABLE_CLI_GROUPS and verb in CONST_GH_READ_VERBS


def _is_cacheable_api_call(args: list[str]) -> bool:
    """Whether a `gh api` call is safe to cache: gh sends it as a GET with no fields or body."""
    api_args = parse_gh_api_args(args[1:])
    return (
        api_args is not None
        and api_args.method == CONST_GH_API_DEFAULT_METHOD
        and not api_args.has_params
    )


def _should_cache(args: list[str], use_cache: bool, input: str | None = None) -> bool:
    """Determine whether a command is eligible for response caching."""
    if not use_cache or input or not args:
        return False
    if _is_sensitive_command(args):
        return False
    if _is_cacheable_cli_read(args):
        return True
    if args[0] == "api":
        return _is_cacheable_api_call(args)
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


def _is_rate_limit_exempt(args: list[str]) -> bool:
    """Determine whether the command is a read-only rate limit inspection or local non-API command."""
    clean = [a.lower() for a in args if a not in (CONST_GH_CLI, "gh")]
    return bool(clean) and (is_local_gh_command(clean) or _is_rate_limit_check(clean))


def _parse_resource_quota(
    r_name: str, r_info: dict[str, Any]
) -> tuple[int, float | None, int | None, int | None]:
    try:
        reset_val = r_info.get("reset")
        reset_epoch = float(reset_val) if reset_val is not None else None
        rem_val = int(r_info["remaining"])
        limit_val = int(r_info["limit"]) if r_info.get("limit") is not None else None
        used_val = int(r_info["used"]) if r_info.get("used") is not None else None
        return rem_val, reset_epoch, limit_val, used_val
    except (ValueError, TypeError) as exc:
        raise GitHubRateLimitError(
            f"Malformed rate limit metric for resource '{r_name}': {exc}",
            operation="refresh_quota",
            details={"resource": str(r_name)[:256], "error": str(exc)[:256]},
        ) from exc


def _update_single_resource_quota(r_name: str, r_info: Any, limiter: GitHubRateLimiter) -> None:
    if not isinstance(r_info, dict) or r_info.get("remaining") is None:
        return
    rem_val, reset_epoch, limit_val, used_val = _parse_resource_quota(r_name, r_info)
    limiter.update_quota(
        r_name,
        remaining=rem_val,
        limit=limit_val,
        used=used_val,
        reset_epoch=reset_epoch,
    )


def _extract_rate_limit_endpoint_response(output: str, limiter: GitHubRateLimiter) -> None:
    """Update quotas directly from /rate_limit endpoint response."""
    payload = extract_json_payload(output)
    if not isinstance(payload, dict):
        raise GitHubRateLimitError(
            "Invalid rate_limit payload format from GitHub API",
            operation="refresh_quota",
        )
    resources = payload.get("resources")
    if not isinstance(resources, dict):
        raise GitHubRateLimitError(
            "Missing resources dictionary in rate_limit payload from GitHub API",
            operation="refresh_quota",
        )
    for r_name, r_info in resources.items():
        _update_single_resource_quota(r_name, r_info, limiter)


def _extract_page_per_page(url_or_endpoint: str) -> int:
    """Extract per_page from query string or default to DEFAULT_GH_REST_PER_PAGE."""
    parts = urlsplit(url_or_endpoint)
    query = parse_qs(parts.query)
    per_page_vals = query.get("per_page")
    if per_page_vals and per_page_vals[0].isdigit():
        return int(per_page_vals[0])
    return DEFAULT_GH_REST_PER_PAGE


def _build_paginated_url(endpoint: str, page: int, per_page: int = DEFAULT_GH_REST_PER_PAGE) -> str:
    """Append or update page and per_page query parameters in endpoint URL."""
    parts = urlsplit(endpoint)
    query = parse_qs(parts.query, keep_blank_values=True)
    query["page"] = [str(page)]
    if "per_page" not in query:
        query["per_page"] = [str(per_page)]
    new_query = urlencode(query, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


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
    per_page: int,
    limiter: GitHubRateLimiter,
    target_resource: str,
    cwd: Path | None,
    quiet: bool,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Prepend calculated delay and execute a single page request."""
    page_endpoint = _build_paginated_url(base_endpoint, page, per_page)
    page_args = list(base_args)
    page_args[endpoint_idx] = page_endpoint

    limiter.acquire(subcommand=target_resource)
    try:
        proc = cast(
            subprocess.CompletedProcess[str],
            _burst_protected_subprocess(
                [CONST_GH_CLI, *page_args],
                cwd=cwd,
                check=False,
                quiet=quiet,
                timeout=timeout,
            ),
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=[CONST_GH_CLI, *page_args],
            returncode=124,
            stdout="",
            stderr=f"GitHub API request timed out after {timeout} seconds",
        )
    _post_process_run(proc, target_resource, limiter, cost=1)
    return proc


def _is_expected_page_shape(data: Any) -> bool:
    """Return True if data is a list or a check-runs dict."""
    if isinstance(data, list):
        return True
    return (
        isinstance(data, dict) and "check_runs" in data and isinstance(data.get("check_runs"), list)
    )


def _append_paginated_data(combined_items: list[Any], data: Any, per_page: int) -> bool:
    """Append page items and return True if more pages may exist."""
    if isinstance(data, dict):
        combined_items.append(data)
        check_runs = data.get("check_runs", [])
        total_count = data.get("total_count", 0)
        return len(check_runs) >= per_page and len(combined_items) * per_page < total_count

    if isinstance(data, list):
        combined_items.extend(data)
        return len(data) >= per_page

    return False


def _validate_page_payload(
    proc: subprocess.CompletedProcess[str],
    base_endpoint: str,
    page: int,
) -> tuple[Any, subprocess.CompletedProcess[str] | None]:
    """Validate page stdout and return (data, None), or (None, error_proc) on failure."""
    stdout_trimmed = (proc.stdout or "").strip()
    if not stdout_trimmed:
        err_proc = subprocess.CompletedProcess(
            args=proc.args,
            returncode=1,
            stdout="",
            stderr=f"gh api paginated read of {base_endpoint} failed on page {page}: empty response",
        )
        return None, err_proc

    try:
        data = json.loads(stdout_trimmed)
    except (json.JSONDecodeError, ValueError) as exc:
        err_proc = subprocess.CompletedProcess(
            args=proc.args,
            returncode=1,
            stdout="",
            stderr=f"gh api paginated read of {base_endpoint} failed on page {page}: malformed JSON ({exc})",
        )
        return None, err_proc

    if not _is_expected_page_shape(data):
        err_proc = subprocess.CompletedProcess(
            args=proc.args,
            returncode=1,
            stdout="",
            stderr=f"gh api paginated read of {base_endpoint} failed on page {page}: unexpected response shape",
        )
        return None, err_proc

    return data, None


def _fetch_all_pages(
    args_no_paginate: list[str],
    endpoint_idx: int,
    base_endpoint: str,
    per_page: int,
    limiter: GitHubRateLimiter,
    target_resource: str,
    cwd: Path | None,
    quiet: bool,
    timeout: float,
    max_pages: int,
) -> tuple[subprocess.CompletedProcess[str] | None, list[Any], bool]:
    """Execute pages up to max_pages and return (last_proc, combined_items, is_exhausted)."""
    combined_items: list[Any] = []
    page = 1
    last_proc: subprocess.CompletedProcess[str] | None = None

    while page <= max_pages:
        proc = _execute_single_page(
            args_no_paginate,
            endpoint_idx,
            base_endpoint,
            page,
            per_page,
            limiter,
            target_resource,
            cwd,
            quiet,
            timeout,
        )
        last_proc = proc
        if proc.returncode != 0:
            return proc, combined_items, False

        stdout_trimmed = (proc.stdout or "").strip()
        if stdout_trimmed == "[]":
            return last_proc, combined_items, True

        data, err_proc = _validate_page_payload(proc, base_endpoint, page)
        if err_proc is not None:
            return err_proc, combined_items, False

        if not _append_paginated_data(combined_items, data, per_page):
            return last_proc, combined_items, True
        page += 1

    err_proc = subprocess.CompletedProcess(
        args=last_proc.args if last_proc else [CONST_GH_CLI, *args_no_paginate],
        returncode=1,
        stdout="",
        stderr=f"gh api: paginated read of '{base_endpoint}' exceeded page cap of {max_pages} pages",
    )
    return err_proc, combined_items, False


def _run_gh_paginated(
    clean_args: list[str],
    limiter: GitHubRateLimiter,
    target_resource: str,
    cwd: Path | None = None,
    quiet: bool = False,
    timeout: float = 30.0,
    max_pages: int = DEFAULT_GH_MAX_PAGINATED_PAGES,
) -> subprocess.CompletedProcess[str]:
    """Execute a paginated gh api request page-by-page with mandatory delay prepended."""
    args_no_paginate = [a for a in clean_args if a not in ("--paginate", "--slurp")]
    endpoint_idx = _find_api_endpoint_idx(args_no_paginate)
    if endpoint_idx == -1:
        return cast(
            subprocess.CompletedProcess[str],
            _burst_protected_subprocess(
                [CONST_GH_CLI, *clean_args], cwd=cwd, check=False, quiet=quiet, timeout=timeout
            ),
        )

    base_endpoint = args_no_paginate[endpoint_idx]
    per_page = _extract_page_per_page(base_endpoint)
    proc, items, ok = _fetch_all_pages(
        args_no_paginate,
        endpoint_idx,
        base_endpoint,
        per_page,
        limiter,
        target_resource,
        cwd,
        quiet,
        timeout,
        max_pages,
    )
    if not ok and proc is not None:
        return proc

    return subprocess.CompletedProcess(
        args=[CONST_GH_CLI, *clean_args],
        returncode=0,
        stdout=json.dumps(items),
        stderr=proc.stderr if proc else "",
    )


def _post_process_run(
    proc: subprocess.CompletedProcess[str],
    resource: str,
    limiter: GitHubRateLimiter,
    is_rate_limit_check: bool = False,
    is_exempt: bool = False,
    cost: int = 1,
) -> None:
    """Extract rate limit metrics from response headers or payload, or record quota utilization."""
    if is_rate_limit_check and proc.stdout:
        _extract_rate_limit_endpoint_response(proc.stdout, limiter)
        return
    if is_exempt:
        return

    _parse_rate_limit_from_output(proc.stdout, resource, limiter)
    if proc.stderr:
        _parse_rate_limit_from_output(proc.stderr, resource, limiter)


def _validate_paginated_api_args(
    clean_args: list[str], full_cmd: list[str], check: bool
) -> subprocess.CompletedProcess[str] | None:
    """Refuse incompatible flags or GraphQL queries when --paginate is passed."""
    if not clean_args or clean_args[0] != "api" or "--paginate" not in clean_args:
        return None
    api_args = clean_args[1:]
    incompatible_flag = incompatible_gh_api_paginate_flag(api_args)
    if incompatible_flag is not None:
        proc = subprocess.CompletedProcess(
            args=full_cmd,
            returncode=1,
            stdout="",
            stderr=f"gh api: cannot combine --paginate with {incompatible_flag}",
        )
        if check:
            raise subprocess.CalledProcessError(
                proc.returncode, full_cmd, output=proc.stdout, stderr=proc.stderr
            )
        return proc
    parsed_api = parse_gh_api_args(api_args)
    if parsed_api is not None and parsed_api.endpoint == CONST_GH_API_GRAPHQL_ENDPOINT:
        proc = subprocess.CompletedProcess(
            args=full_cmd,
            returncode=1,
            stdout="",
            stderr="gh api: GraphQL queries do not support --paginate",
        )
        if check:
            raise subprocess.CalledProcessError(
                proc.returncode, full_cmd, output=proc.stdout, stderr=proc.stderr
            )
        return proc
    return None


def _handle_cached_or_paginated(
    limiter: GitHubRateLimiter,
    clean_args: list[str],
    full_cmd: list[str],
    input: str | None,
    use_cache: bool,
    cache_ttl: float,
    cwd: Path | None,
    quiet: bool,
    timeout: float,
    check: bool,
    target_resource: str,
    is_check: bool,
    is_mutation: bool,
) -> subprocess.CompletedProcess[str] | None:
    """Check cache or execute paginated API request if applicable.

    Page-by-page fetching is for reads; a write with `--paginate` goes to gh once, as given.
    """
    cached = _check_cached_result(limiter, clean_args, input, use_cache)
    if cached is not None:
        return cached

    if not is_check and not is_mutation and "--paginate" in clean_args:
        invalid_paginated = _validate_paginated_api_args(clean_args, full_cmd, check)
        if invalid_paginated is not None:
            return invalid_paginated

        proc = _run_gh_paginated(
            clean_args,
            limiter=limiter,
            target_resource=target_resource,
            cwd=cwd,
            quiet=quiet,
            timeout=timeout,
        )
        if _should_cache(clean_args, use_cache, input) and proc.returncode == 0 and proc.stdout:
            limiter.set_cached(_build_cache_key(clean_args, input), proc.stdout, ttl=cache_ttl)
        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, full_cmd, output=proc.stdout, stderr=proc.stderr
            )
        return proc
    return None


def _execute_gh_single_attempt(
    full_cmd: list[str],
    input: str | None,
    cwd: Path | None,
    quiet: bool,
    timeout: float,
    capture_output: bool,
    target_resource: str,
    limiter: GitHubRateLimiter,
    is_check: bool,
    is_exempt: bool,
    is_mutation: bool,
    cost: int,
) -> subprocess.CompletedProcess[str]:
    """Execute a single attempt of GitHub CLI command under rate limiting."""
    if not is_exempt:
        limiter.acquire(subcommand=target_resource, is_mutation=is_mutation, cost=cost)
    try:
        proc = cast(
            subprocess.CompletedProcess[str],
            _burst_protected_subprocess(
                full_cmd,
                input=input,
                cwd=cwd,
                check=False,
                quiet=quiet,
                timeout=timeout,
                capture_output=capture_output,
            ),
        )
    except subprocess.TimeoutExpired:
        proc = subprocess.CompletedProcess(
            args=full_cmd,
            returncode=124,
            stdout="",
            stderr=f"GitHub API command timed out after {timeout} seconds",
        )
    _post_process_run(
        proc,
        target_resource,
        limiter,
        is_rate_limit_check=is_check,
        is_exempt=is_exempt,
        cost=cost,
    )
    return proc


def _handle_attempt_backoff(
    limiter: GitHubRateLimiter,
    proc: subprocess.CompletedProcess[str],
    attempt: int,
    max_retries: int,
    target_resource: str,
) -> bool:
    """Evaluate and sleep backoff if rate limited, returning True if backoff performed."""
    combined_err = (proc.stderr or "") + " " + (proc.stdout or "")
    if not limiter.is_rate_limit_error(combined_err) or attempt >= max_retries:
        return False

    backoff = limiter.calculate_backoff_delay(
        combined_err, attempt=attempt + 1, subcommand=target_resource
    )
    if backoff <= 0.0:
        return False
    logger.warning(
        "[RateLimit] Rate limit encountered on attempt %d for '%s'. Pausing %.2fs",
        attempt + 1,
        target_resource,
        backoff,
    )
    limiter.record_throttle(backoff)
    time.sleep(backoff)
    return True


def _calculate_effective_cost(clean_args: list[str], target_resource: str, cost: int) -> int:
    """Calculate effective cost of command for rate limit tracking."""
    if cost != 1:
        return cost
    is_graphql = target_resource == "graphql"
    is_project = bool(clean_args and clean_args[0] == "project")
    return 2 if (is_graphql or is_project) else cost


def _run_gh_retry_loop(
    full_cmd: list[str],
    clean_args: list[str],
    input: str | None,
    valid_cwd: Path | None,
    quiet: bool,
    timeout: float,
    capture_output: bool,
    target_resource: str,
    limiter: GitHubRateLimiter,
    is_check: bool,
    is_exempt: bool,
    is_mutation: bool,
    effective_cost: int,
    max_retries: int,
    use_cache: bool,
    cache_ttl: float,
) -> subprocess.CompletedProcess[str]:
    """Execute command with retries and backoff."""
    cache_key = _build_cache_key(clean_args, input)
    last_res = subprocess.CompletedProcess(args=full_cmd, returncode=1, stdout="", stderr="")
    for attempt in range(max_retries + 1):
        proc = _execute_gh_single_attempt(
            full_cmd,
            input,
            valid_cwd,
            quiet,
            timeout,
            capture_output,
            target_resource,
            limiter,
            is_check,
            is_exempt,
            is_mutation,
            effective_cost,
        )
        last_res = proc
        if proc.returncode == 0:
            if _should_cache(clean_args, use_cache, input) and proc.stdout:
                limiter.set_cached(cache_key, proc.stdout, ttl=cache_ttl)
            return proc
        if not _handle_attempt_backoff(limiter, proc, attempt, max_retries, target_resource):
            break
    return last_res


def _raise_for_status(
    proc: subprocess.CompletedProcess[str], full_cmd: list[str], check: bool
) -> None:
    """Raise CalledProcessError if check is True and returncode is non-zero."""
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode,
            full_cmd,
            output=proc.stdout,
            stderr=proc.stderr,
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
    cost: int = 1,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a GitHub CLI command via centralized rate limiting, pacing, backoff, and caching.

    Enforces mandatory pause calculated from:
        request delay = time in seconds until next quota reset for this subcommand / remaining requests
    """
    valid_cwd = _validate_gh_cwd(cwd) if cwd is not None else None
    clean_args = _normalize_gh_args(args)
    full_cmd = [CONST_GH_CLI, *clean_args]
    if is_local_gh_command(clean_args):
        # They need no identity, so they run outside the session's ledger.
        proc = run_subprocess(
            full_cmd,
            input=input,
            cwd=valid_cwd,
            quiet=quiet,
            timeout=timeout,
            capture_output=capture_output,
        )
        _raise_for_status(proc, full_cmd, check)
        return proc
    limiter = get_github_rate_limiter()
    target_resource = resource or _detect_resource(clean_args)
    is_check = _is_rate_limit_check(clean_args)
    is_exempt = _is_rate_limit_exempt(clean_args)
    is_mutation = not is_exempt and is_write_gh_command(clean_args, input=input, cwd=valid_cwd)

    early_res = _handle_cached_or_paginated(
        limiter,
        clean_args,
        full_cmd,
        input,
        use_cache,
        cache_ttl,
        valid_cwd,
        quiet,
        timeout,
        check,
        target_resource,
        is_check,
        is_mutation,
    )
    if early_res is not None:
        return early_res

    effective_cost = _calculate_effective_cost(clean_args, target_resource, cost)

    proc = _run_gh_retry_loop(
        full_cmd,
        clean_args,
        input,
        valid_cwd,
        quiet,
        timeout,
        capture_output,
        target_resource,
        limiter,
        is_check,
        is_exempt,
        is_mutation,
        effective_cost,
        max_retries,
        use_cache,
        cache_ttl,
    )
    _raise_for_status(proc, full_cmd, check)
    return proc


async def run_gh_async(
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
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a GitHub CLI command asynchronously with aiolimiter token-bucket pacing."""
    clean_args = _normalize_gh_args(args)
    target_resource = resource or _detect_resource(clean_args)
    limiter = get_github_rate_limiter()
    async_limiter = limiter.get_async_limiter(target_resource)

    async with async_limiter:
        return await asyncio.to_thread(
            run_gh,
            args,
            input=input,
            cwd=cwd,
            check=check,
            quiet=quiet,
            use_cache=use_cache,
            cache_ttl=cache_ttl,
            timeout=timeout,
            max_retries=max_retries,
            resource=target_resource,
            cost=cost,
            capture_output=capture_output,
        )
