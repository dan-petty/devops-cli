"""Network validation, limited JSON parsing, and concurrency coordination."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx2

from devops_cli.ai.client.models import AIClientError, RequestPriority
from devops_cli.config.constants import CONST_AI_ALLOW_PRIVATE_NETWORK_ENV
from devops_cli.config.defaults import (
    DEFAULT_AI_MAX_RESPONSE_BYTES,
    DEFAULT_OLLAMA_MAX_PARALLEL,
    DEFAULT_OLLAMA_SLOT_POLL_INTERVAL_SECONDS,
    DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

ALLOW_PRIVATE_NETWORK_ENV = CONST_AI_ALLOW_PRIVATE_NETWORK_ENV
active_ollama_requests: dict[str, int] = {}
ollama_active_lock = threading.Lock()
ollama_semaphores: dict[str, threading.Semaphore] = {}
ollama_sem_lock = threading.Lock()
ollama_slot_condition = threading.Condition(threading.Lock())
waiting_priority_requests: dict[RequestPriority, int] = {
    RequestPriority.HIGH: 0,
    RequestPriority.NORMAL: 0,
    RequestPriority.AS_AVAILABLE: 0,
}
current_request_priority: ContextVar[RequestPriority] = ContextVar(
    "current_request_priority", default=RequestPriority.NORMAL
)
global_ollama_url_index: int = 0
global_ollama_url_lock = threading.Lock()


@contextmanager
def request_priority_scope(priority: RequestPriority | str) -> Generator[None]:
    """Set the request priority for the current task or thread context."""
    p = RequestPriority(priority) if isinstance(priority, str) else priority
    token = current_request_priority.set(p)
    try:
        yield
    finally:
        current_request_priority.reset(token)


def load_and_increment_rr_index(n: int) -> int:
    """Atomically fetch and increment the round-robin server index across runs."""
    global global_ollama_url_index
    if n <= 1:
        return 0
    uid = os.getuid() if hasattr(os, "getuid") else 0
    state_file = Path(tempfile.gettempdir()) / f"devops_cli_ollama_rr_{uid}"
    with global_ollama_url_lock:
        idx = global_ollama_url_index
        try:
            if state_file.exists():
                idx = int(state_file.read_text(encoding="utf-8").strip())
        except Exception:
            pass
        next_idx = (idx + 1) % n
        global_ollama_url_index = next_idx
        try:
            state_file.write_text(str(next_idx), encoding="utf-8")
        except Exception:
            pass
        return idx % n


def get_ollama_semaphore(url: str, max_parallel: int) -> threading.Semaphore:
    with ollama_sem_lock:
        if (
            url not in ollama_semaphores
            or getattr(ollama_semaphores[url], "_max_parallel", None) != max_parallel
        ):
            sem = threading.Semaphore(max(1, max_parallel))
            setattr(sem, "_max_parallel", max_parallel)
            ollama_semaphores[url] = sem
        return ollama_semaphores[url]


def _is_priority_eligible(priority: RequestPriority) -> bool:
    """Check if priority tier is eligible without higher-priority starvation."""
    if priority == RequestPriority.HIGH:
        return True
    if priority == RequestPriority.NORMAL:
        return waiting_priority_requests.get(RequestPriority.HIGH, 0) == 0
    return (
        waiting_priority_requests.get(RequestPriority.HIGH, 0) == 0
        and waiting_priority_requests.get(RequestPriority.NORMAL, 0) == 0
    )


def _find_available_slot(
    candidates: list[str],
    max_parallel: int,
    priority: RequestPriority = RequestPriority.NORMAL,
) -> str | None:
    """Find candidate URL with active request count below limit and lowest load, respecting priority."""
    if not _is_priority_eligible(priority):
        return None

    cap = max_parallel
    if priority == RequestPriority.AS_AVAILABLE and max_parallel > 1:
        cap = max(1, max_parallel - 1)

    best_url: str | None = None
    best_active = cap
    for url in candidates:
        active = active_ollama_requests.get(url, 0)
        if active < best_active:
            best_url = url
            best_active = active
    return best_url


def _wait_for_slot(
    candidates: list[str],
    max_parallel: int,
    priority: RequestPriority,
    deadline: float,
    eff_timeout: float,
) -> str:
    """Wait on condition until an eligible slot is acquired or deadline expires."""
    while True:
        best_url = _find_available_slot(candidates, max_parallel, priority)
        if best_url is not None:
            active_ollama_requests[best_url] = active_ollama_requests.get(best_url, 0) + 1
            return best_url

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if priority == RequestPriority.AS_AVAILABLE:
                raise AIClientError(
                    f"No capacity available for as-available priority request across: {candidates}"
                )
            raise AIClientError(
                f"Timed out after {eff_timeout}s waiting for available slot across Ollama nodes: {candidates}"
            )
        ollama_slot_condition.wait(
            timeout=min(remaining, DEFAULT_OLLAMA_SLOT_POLL_INTERVAL_SECONDS)
        )


def _release_ollama_slot(leased_url: str | None) -> None:
    """Release active slot lease and notify waiting requesters."""
    with ollama_slot_condition:
        if leased_url is not None:
            active_ollama_requests[leased_url] = max(
                0, active_ollama_requests.get(leased_url, 0) - 1
            )
        ollama_slot_condition.notify_all()


@contextmanager
def acquire_ollama_slot(
    candidates: list[str],
    max_parallel: int = DEFAULT_OLLAMA_MAX_PARALLEL,
    timeout: float | None = None,
    priority: RequestPriority | str | None = None,
) -> Generator[str]:
    """Dynamically lease an available Ollama slot across candidate nodes with priority scheduling."""
    if not candidates:
        raise AIClientError("No candidate Ollama servers provided for slot leasing.")

    resolved_p = (
        RequestPriority(priority)
        if isinstance(priority, str)
        else (priority or current_request_priority.get())
    )

    eff_timeout = (
        0.0
        if (timeout is None and resolved_p == RequestPriority.AS_AVAILABLE)
        else (timeout if timeout is not None else DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS)
    )

    deadline = time.monotonic() + eff_timeout
    leased_url: str | None = None

    with ollama_slot_condition:
        waiting_priority_requests[resolved_p] = waiting_priority_requests.get(resolved_p, 0) + 1
        try:
            leased_url = _wait_for_slot(candidates, max_parallel, resolved_p, deadline, eff_timeout)
        finally:
            waiting_priority_requests[resolved_p] = max(
                0, waiting_priority_requests.get(resolved_p, 0) - 1
            )

    try:
        yield leased_url
    finally:
        _release_ollama_slot(leased_url)


@contextmanager
def track_ollama_url(
    url: str,
    max_parallel: int = DEFAULT_OLLAMA_MAX_PARALLEL,
    priority: RequestPriority | str | None = None,
) -> Generator[None]:
    """Acquire concurrency slot and track active in-flight requests per Ollama server node."""
    with acquire_ollama_slot([url], max_parallel=max_parallel, priority=priority):
        yield


def get_ollama_active_leases(url: str) -> int:
    """Get count of active leased slots for an Ollama server node."""
    with ollama_slot_condition:
        return active_ollama_requests.get(url, 0)


def get_ollama_waiting_counts() -> dict[str, int]:
    """Get active waiting request counts grouped by priority name."""
    with ollama_slot_condition:
        return {p.value: waiting_priority_requests.get(p, 0) for p in RequestPriority}


def reset_ollama_slots() -> None:
    """Reset all active slot leases and waiting queues to zero (for testing)."""
    with ollama_slot_condition:
        active_ollama_requests.clear()
        for p in RequestPriority:
            waiting_priority_requests[p] = 0
        ollama_slot_condition.notify_all()


def read_limited_json(
    response: httpx2.Response, limit_bytes: int = DEFAULT_AI_MAX_RESPONSE_BYTES
) -> dict[str, Any]:
    """Parse JSON response while enforcing a maximum response body size limit."""
    headers = getattr(response, "headers", {})
    content_length = headers.get("content-length") if hasattr(headers, "get") else None
    if content_length and content_length.isdigit() and int(content_length) > limit_bytes:
        raise AIClientError(
            f"Response body exceeded maximum size ({limit_bytes // (1024 * 1024)}MB)."
        )
    if hasattr(response, "content") and response.content is not None:
        body = response.content
        if len(body) > limit_bytes:
            raise AIClientError(
                f"Response body exceeded maximum size ({limit_bytes // (1024 * 1024)}MB)."
            )
        try:
            res: dict[str, Any] = json.loads(body)
            return res
        except json.JSONDecodeError as exc:
            raise AIClientError(f"Invalid JSON response payload from AI provider: {exc}") from exc

    try:
        raw_res: dict[str, Any] = response.json()
        return raw_res
    except Exception as exc:
        raise AIClientError(f"Failed to parse JSON response body from AI provider: {exc}") from exc


def validate_base_url(
    base_url: str,
    purpose: str = "API",
    *,
    allow_private_network: bool = False,
    allow_loopback_for_local_tooling: bool = False,
) -> str:
    """Validate base URL against SSRF and network egress rules."""
    if not base_url or not base_url.strip():
        raise AIClientError(f"Missing {purpose} base URL.")

    try:
        parsed = urlparse(base_url.strip())
    except Exception as exc:
        raise AIClientError(f"Invalid {purpose} base URL format: {base_url!r}") from exc

    if parsed.scheme not in ("http", "https"):
        raise AIClientError(
            f"Invalid {purpose} URL scheme '{parsed.scheme}'. Only http and https are permitted."
        )

    host = parsed.hostname
    if not host:
        raise AIClientError(f"Missing hostname in {purpose} base URL: {base_url!r}")

    is_allowed_local = allow_loopback_for_local_tooling and host in (
        "localhost",
        "127.0.0.1",
        "::1",
    )
    if not allow_private_network and not is_allowed_local:
        try:
            from devops_cli.core.validation import validate_service_url

            validate_service_url(base_url, purpose=purpose, allow=False)
        except ValueError as exc:
            raise AIClientError(str(exc)) from exc

    return base_url.rstrip("/")
