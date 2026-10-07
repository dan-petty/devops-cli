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
from typing import TYPE_CHECKING, Any
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

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason

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

# The backend a gateway named in a streamed response's headers. A stream is a generator consumed
# in the caller's context, so its spend is recorded after the last chunk, not where headers arrive.
stream_served_by: ContextVar[str | None] = ContextVar("stream_served_by", default=None)
# Why a streamed reply ended, set by the stream reader when the provider's final frame arrives.
# A generator's return value would be lost in the caller's `for` loop and the sanitizer wrapping
# it, so the reason travels like the serving backend.
stream_finish_reason: ContextVar[FinishReason | None] = ContextVar(
    "stream_finish_reason", default=None
)

# A reply-token cap for the calls made inside `limit_completion_tokens`. It travels with the
# context, like the request priority, so one call site can bound a reply without every layer
# between it and the provider taking a parameter.
completion_cap: ContextVar[int | None] = ContextVar("completion_cap", default=None)


@contextmanager
def limit_completion_tokens(limit: int) -> Generator[None]:
    """Cap the reply of every LLM call made inside the block at ``limit`` tokens."""
    token = completion_cap.set(limit)
    try:
        yield
    finally:
        completion_cap.reset(token)


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


def size_limit_text(limit_bytes: int) -> str:
    """A byte limit in the largest unit it reaches: `50MB`, `1.5KB`, `200 bytes`."""
    for unit, scale in (("MB", 1024 * 1024), ("KB", 1024)):
        if limit_bytes >= scale:
            return f"{limit_bytes / scale:.1f}".removesuffix(".0") + unit
    return f"{limit_bytes} bytes"


def _response_size_error(limit_bytes: int) -> AIClientError:
    return AIClientError(f"Response body exceeded maximum size ({size_limit_text(limit_bytes)}).")


def _read_limited_body(response: httpx2.Response, limit_bytes: int) -> bytearray:
    """A streamed response's decoded body, refused as soon as it passes ``limit_bytes``.

    A numeric Content-Length over the limit is refused before any of the body is read. The
    decoded bytes are counted, so a compressed body cannot inflate past the limit either.
    """
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit_bytes:
        raise _response_size_error(limit_bytes)
    body = bytearray()
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > limit_bytes:
            raise _response_size_error(limit_bytes)
    return body


def _raise_for_status(response: httpx2.Response, body: bytearray) -> None:
    """Raise `HTTPStatusError` for a reply that is not 2xx, its response holding the body read.

    The streamed response is closed by then, so the error carries a copy whose `text` and
    `json()` read the bounded body, as callers that inspect a provider's error message do.
    """
    if response.is_success:
        return
    read_reply = httpx2.Response(
        response.status_code,
        headers={"content-type": response.headers.get("content-type", "")},
        content=bytes(body),
        request=response.request,
    )
    read_reply.raise_for_status()


def _json_object(body: bytearray) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AIClientError(f"Invalid JSON response payload from AI provider: {exc}") from exc
    if not isinstance(payload, dict):
        kind = type(payload).__name__
        raise AIClientError(f"AI provider replied with a JSON {kind}, not an object.")
    return payload


def request_limited_json(
    http_client: httpx2.Client,
    method: str,
    url: str,
    *,
    limit_bytes: int | None = None,
    **request_kwargs: Any,
) -> tuple[dict[str, Any], httpx2.Headers]:
    """Send a request and return its JSON object reply and headers, reading at most the limit.

    The reply is streamed, so no more than ``limit_bytes`` (default
    `DEFAULT_AI_MAX_RESPONSE_BYTES`) of it is ever held: a client that buffers the whole body
    before checking its size gives a model endpoint, or anyone on the path to a plain-http one,
    the CLI's memory. A reply that is not 2xx raises `httpx2.HTTPStatusError`, unparsed.
    """
    limit = DEFAULT_AI_MAX_RESPONSE_BYTES if limit_bytes is None else limit_bytes
    try:
        with http_client.stream(method, url, **request_kwargs) as response:
            body = _read_limited_body(response, limit)
        _raise_for_status(response, body)
        return _json_object(body), response.headers
    finally:
        from devops_cli.http.pool import close_expired_connections

        close_expired_connections(http_client)


def validate_base_url(
    base_url: str,
    purpose: str = "API",
    *,
    allow_private_network: bool = False,
) -> str:
    """Validate a configured base URL against SSRF and network egress rules.

    Every base URL the client sends to comes from the user's configuration, so it follows
    `validate_configured_service_url`: loopback is allowed, and any other non-public host
    needs ``allow_private_network``.
    """
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

    if not parsed.hostname:
        raise AIClientError(f"Missing hostname in {purpose} base URL: {base_url!r}")

    from devops_cli.core.validation import validate_configured_service_url

    try:
        validate_configured_service_url(
            base_url, purpose=purpose, allow_private=allow_private_network
        )
    except ValueError as exc:
        raise AIClientError(str(exc)) from exc

    return base_url.rstrip("/")
