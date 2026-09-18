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
import random
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

from devops_cli.config.constants import (
    CONST_CACHE_DIR_NAME,
    CONST_GH_CLI,
    CONST_GH_MUTATION_HTTP_METHODS,
    CONST_GH_MUTATION_VERBS,
    CONST_GH_NON_API_COMMANDS,
    CONST_GH_QUOTA_CACHE_FILENAME,
    CONST_GITHUB_RATE_LIMIT_PATTERNS,
)
from devops_cli.config.defaults import (
    DEFAULT_DATA_DIR,
    DEFAULT_GH_CACHE_TTL_SECONDS,
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_MUTATION_MIN_INTERVAL_SECONDS,
    DEFAULT_GH_QUOTA_MAX_AGE_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubRateLimitError

logger = logging.getLogger(__name__)

_BURST_LIMIT_DECORATOR: Any = limits(calls=60, period=60)


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
        fd = open(lock_file, "a+", encoding="utf-8")
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


def _load_disk_global_meta(path: Path) -> tuple[int, float]:
    """Load global request count and last request timestamp from disk."""
    if not path.is_file():
        return 0, 0.0
    try:
        content = path.read_text(encoding="utf-8")
        raw = json.loads(content)
        if isinstance(raw, dict):
            g = raw.get("_global", {})
            if isinstance(g, dict):
                total = int(g.get("total_requests", 0))
                last_epoch = float(g.get("last_request_epoch", 0.0))
                return max(0, total), max(0.0, last_epoch)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as err:
        logger.warning("Failed to load global rate limit metadata from %s: %s", path, err)
    return 0, 0.0


def _save_disk_quota(
    quotas: dict[str, QuotaState],
    path: Path,
    total_requests: int = 0,
    last_request_epoch: float = 0.0,
) -> None:
    """Persist rate limit quota state and global request metrics to disk atomically."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "_global": {
                "total_requests": max(0, total_requests),
                "last_request_epoch": max(0.0, last_request_epoch),
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


def _is_api_mutation(api_args: list[str]) -> bool:
    """Determine whether API call arguments constitute a write mutation."""
    for arg in api_args:
        upper = arg.upper()
        if upper in CONST_GH_MUTATION_HTTP_METHODS:
            return True
        if any(
            upper.startswith(f"-X{m}") or upper.startswith(f"--METHOD={m}")
            for m in CONST_GH_MUTATION_HTTP_METHODS
        ):
            return True
    return False


def _is_mutation_command(args: list[str]) -> bool:
    """Determine whether a GitHub CLI command is a write mutation."""
    if not args:
        return False
    clean = [a.lower() for a in args if a not in (CONST_GH_CLI, "gh")]
    if not clean:
        return False
    if any(arg in CONST_GH_MUTATION_VERBS for arg in clean[1:]):
        return True
    if clean[0] == "api":
        return _is_api_mutation(clean[1:])
    return False


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
    ) -> None:
        if mutation_min_interval < 0.0:
            raise ValueError(
                f"mutation_min_interval must be non-negative, got {mutation_min_interval}"
            )
        if quota_max_age < 0.0:
            raise ValueError(f"quota_max_age must be non-negative, got {quota_max_age}")
        self.persist_path = persist_path
        self.min_interval = min_interval
        self.fallback_delay = fallback_delay
        self.mutation_min_interval = mutation_min_interval
        self.quota_max_age = quota_max_age
        self._lock = threading.RLock()
        self._cache: dict[str, _CacheEntry] = {}
        self._next_allowed_time: dict[str, float] = {}
        self._last_mutation_epoch: float = 0.0
        self._async_limiters: dict[str, AsyncLimiter] = {}
        self._is_refreshing: bool = False
        self._total_requests: int = 0
        self._last_request_epoch: float = 0.0
        self._quotas: dict[str, QuotaState] = {}
        if persist_path:
            self._sync_from_disk_locked()

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
        disk_reqs, disk_last_req = _load_disk_global_meta(self.persist_path)
        self._total_requests = max(self._total_requests, disk_reqs)
        self._last_request_epoch = max(self._last_request_epoch, disk_last_req)
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
            )

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

        scheduled_time = max(now, prev_scheduled) + delay
        raw_sleep = max(0.0, scheduled_time - now)

        sleep_duration = raw_sleep
        self._next_allowed_time[target] = now + sleep_duration
        self._last_request_epoch = now + sleep_duration
        if is_mutation:
            self._last_mutation_epoch = now + sleep_duration
        if state and state.is_valid(now, max_age=self.quota_max_age):
            state.record_utilization(cost=cost)
        self._total_requests += 1
        self._persist_to_disk_locked()

        return sleep_duration

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

    def calculate_backoff_delay(
        self, message: str, attempt: int = 1, subcommand: str = "core"
    ) -> float:
        """Calculate backoff delay for secondary rate limits or wait until reset."""
        if not self.is_rate_limit_error(message):
            return 0.0
        with self._lock:
            state = self._quotas.get(subcommand)
            if state and state.reset_epoch is not None and state.reset_epoch > 0.0:
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

    def clear_cache(self) -> None:
        """Clear all in-memory and persistent cached responses."""
        with self._lock:
            self._cache.clear()
            if self.persist_path:
                cache_dir = self.persist_path.parent / "responses"
                shutil.rmtree(cache_dir, ignore_errors=True)


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


def _is_sensitive_command(args: list[str]) -> bool:
    """Check if command contains sensitive tokens or credentials."""
    combined_args = " ".join(args).lower()
    sensitive_markers = ("token", "authorization", "bearer", "password", "secret", "cookie")
    return any(marker in combined_args for marker in sensitive_markers)


def _is_cacheable_cli_read(first: str, rest_args: list[str]) -> bool:
    """Predicate determining if top-level gh subcommand is a read query."""
    if first not in ("pr", "issue", "project", "label", "milestone", "repo", "workflow", "run"):
        return False
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
    return any(arg in read_verbs for arg in rest_args)


def _is_cacheable_api_call(args: list[str]) -> bool:
    """Predicate determining if gh api call is safe for read caching."""
    if _is_api_mutation(args):
        return False
    has_field = any(arg in ("-f", "--field", "-F", "--raw-field") for arg in args)
    return not has_field


def _should_cache(args: list[str], use_cache: bool, input: str | None = None) -> bool:
    """Determine whether a command is eligible for response caching."""
    if not use_cache or input or not args:
        return False
    if _is_sensitive_command(args):
        return False
    if _is_cacheable_cli_read(args[0], args[1:]):
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
    if not clean:
        return False
    if clean[0] in CONST_GH_NON_API_COMMANDS:
        return True
    return _is_rate_limit_check(clean)


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
        if isinstance(r_info, dict) and "remaining" in r_info and r_info["remaining"] is not None:
            reset_val = r_info.get("reset")
            reset_epoch = float(reset_val) if reset_val is not None else None
            limiter.update_quota(
                r_name,
                remaining=int(r_info["remaining"]),
                limit=int(r_info["limit"])
                if "limit" in r_info and r_info["limit"] is not None
                else None,
                used=int(r_info["used"])
                if "used" in r_info and r_info["used"] is not None
                else None,
                reset_epoch=reset_epoch,
            )


def _extract_page_per_page(url_or_endpoint: str) -> int:
    """Extract per_page from query string or default to 100."""
    parts = urlsplit(url_or_endpoint)
    query = parse_qs(parts.query)
    per_page_vals = query.get("per_page")
    if per_page_vals and per_page_vals[0].isdigit():
        return int(per_page_vals[0])
    return 100


def _build_paginated_url(endpoint: str, page: int) -> str:
    """Append or update page query parameter in endpoint URL."""
    parts = urlsplit(endpoint)
    query = parse_qs(parts.query, keep_blank_values=True)
    query["page"] = [str(page)]
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
    args_no_paginate = [a for a in clean_args if a != "--paginate"]
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
    combined_items: list[Any] = []
    page = 1
    last_proc: subprocess.CompletedProcess[str] | None = None

    while page <= max_pages:
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
) -> subprocess.CompletedProcess[str] | None:
    """Check cache or execute paginated API request if applicable."""
    cached = _check_cached_result(limiter, clean_args, input, use_cache)
    if cached is not None:
        return cached

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
    limiter = get_github_rate_limiter()
    full_cmd = [CONST_GH_CLI, *clean_args]
    target_resource = resource or _detect_resource(clean_args)
    is_check = _is_rate_limit_check(clean_args)
    is_exempt = _is_rate_limit_exempt(clean_args)

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
    )
    if early_res is not None:
        return early_res

    is_mutation = _is_mutation_command(clean_args)
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
