"""Network validation, limited JSON parsing, and concurrency coordination."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx2

from devops_cli.ai.client.models import AIClientError, RequestPriority
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_SERVED_BY_HEADER,
    CONST_AI_GATEWAY_SERVED_MODEL_HEADER,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_MAX_RESPONSE_BYTES as DEFAULT_AI_MAX_RESPONSE_BYTES,
)
from devops_cli.config.defaults import (
    DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
    DEFAULT_GATEWAY_SLOT_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_SLOT_POLL_INTERVAL_SECONDS,
    DEFAULT_OLLAMA_SLOT_TIMEOUT_SECONDS,
)
from devops_cli.http.client import user_agent
from devops_cli.telemetry import trace_span
from devops_cli.telemetry.instruments import AI_GATEWAY_SLOT_WAIT, AI_OLLAMA_SLOT_WAIT, emit
from devops_cli.telemetry.tracer import otel_service_name

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason

logger = logging.getLogger(__name__)

active_ollama_requests: dict[str, int] = {}
ollama_active_lock = threading.Lock()
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

# The header in which LiteLLM reads the caller of a request as its end user, one of its standard
# customer-id headers. With `enable_end_user_cost_tracking_prometheus_only` it writes the value
# as the `end_user` label of its request and token series (#1668).
_GATEWAY_END_USER_HEADER = "x-litellm-end-user-id"


def gateway_caller_headers() -> dict[str, str]:
    """What each call to the LLM gateway says about its caller (#1668).

    Every caller sends the gateway's one key, so the gateway tells callers apart by these: the
    process's OTel service name as the end user, from a closed set that the workloads set, and
    devops-cli and its release as the user agent.
    """
    return {"User-Agent": user_agent(), _GATEWAY_END_USER_HEADER: otel_service_name()}


async def name_gateway_caller(request: httpx2.Request) -> None:
    """Request hook that puts the gateway caller headers on a request that a library built.

    pydantic-ai sets its own User-Agent on each request, so only a hook that runs after it can
    name devops-cli.
    """
    request.headers.update(gateway_caller_headers())


# Every chat request the process sends to the gateway holds one of these, so the requests in
# flight never outnumber the slots of the backends behind it, whatever thread pools sent them.
gateway_slots = threading.BoundedSemaphore(DEFAULT_GATEWAY_REVIEW_CONCURRENCY)

# How long a streamed call waited for its gateway slot, set by the stream once it holds one. A
# plain call starts its clock once it holds its slot; a stream's clock starts before its
# generator first runs, so the wait travels like the serving backend and is taken off its time.
stream_slot_wait: ContextVar[float] = ContextVar("stream_slot_wait", default=0.0)

# The backend a gateway named in a streamed response's headers. A stream is a generator consumed
# in the caller's context, so its spend is recorded after the last chunk, not where headers arrive.
stream_served_by: ContextVar[str | None] = ContextVar("stream_served_by", default=None)


def extract_served_by(headers: Mapping[str, str] | None) -> str | None:
    """Extract backend URL from gateway response headers, stripping any userinfo."""
    if not headers:
        return None
    val = headers.get(CONST_AI_GATEWAY_SERVED_BY_HEADER)
    if not val:
        return None
    try:
        u = httpx2.URL(val)
    except httpx2.InvalidURL:
        return None
    if "@" in val and not u.userinfo:
        return None
    return str(u.copy_with(userinfo=b""))


# The deployment model a gateway named in a streamed response's headers, read with the backend.
stream_served_model: ContextVar[str | None] = ContextVar("stream_served_model", default=None)

# The model name reported in stream chunks/payloads.
stream_model: ContextVar[str | None] = ContextVar("stream_model", default=None)


@dataclass(frozen=True)
class DispatchContext:
    """Active dispatch call metadata for attempt recording."""

    provider: str
    model: str
    request_type: str = "chat_dispatch"
    task_name: str | None = None
    server: str | None = None
    backend_info: str | None = None


active_dispatch_context: ContextVar[DispatchContext | None] = ContextVar(
    "active_dispatch_context", default=None
)


@contextmanager
def bind_dispatch_context(
    provider: str,
    model: str,
    request_type: str = "chat_dispatch",
    task_name: str | None = None,
    server: str | None = None,
    backend_info: str | None = None,
) -> Generator[None]:
    """Bind dispatch metadata for the duration of a call so transports can record attempts."""
    token = active_dispatch_context.set(
        DispatchContext(
            provider=provider,
            model=model,
            request_type=request_type,
            task_name=task_name,
            server=server,
            backend_info=backend_info,
        )
    )
    try:
        yield
    finally:
        active_dispatch_context.reset(token)


def extract_served_model(headers: Mapping[str, str] | None) -> str | None:
    """The deployment model that a gateway reply names as the model that served the call, such as
    `openai/gpt-4o`; None when the reply names none.

    The LiteLLM router writes the route name, such as `devops-chat`, in the reply body, so a
    hosted call is priced at this model (#2031).
    """
    if not headers:
        return None
    return (headers.get(CONST_AI_GATEWAY_SERVED_MODEL_HEADER) or "").strip() or None


# Why a streamed reply ended, set by the stream reader when the provider's final frame arrives.
# A generator's return value would be lost in the caller's `for` loop and the sanitizer wrapping
# it, so the reason travels like the serving backend.
stream_finish_reason: ContextVar[FinishReason | None] = ContextVar(
    "stream_finish_reason", default=None
)


@dataclass(frozen=True)
class StreamUsage:
    """Token usage metrics reported directly by a streaming LLM provider."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None


# Token usage metrics extracted from the final frames of a streamed reply.
stream_usage: ContextVar[StreamUsage | None] = ContextVar("stream_usage", default=None)

# The origin of the server leased for a streamed request, e.g. for multi-node Ollama. The stream
# span opens before the lease, so the spend that is recorded after the last chunk reads it here.
stream_server: ContextVar[httpx2.Origin | None] = ContextVar("stream_server", default=None)

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


@dataclass(frozen=True)
class ReplySchema:
    """The JSON Schema a structured call's reply must validate against, and the schema's name.

    A provider gets the schema as its native constraint only where the pydantic-ai profile of its
    model supports JSON-schema output, in the form pydantic-ai's `NativeOutput` sends (#1419).
    """

    name: str
    json_schema: dict[str, Any]

    def openai_response_format(self, model: str) -> dict[str, Any] | None:
        """The `response_format` for an OpenAI model, or None when its profile has no JSON-schema
        output. The profile's transformer adapts the schema, and `strict` is true only when the
        schema fits OpenAI's strict mode."""
        from pydantic_ai.profiles.openai import openai_model_profile

        profile = openai_model_profile(model)
        transformer_class = profile.get("json_schema_transformer")
        if not profile.get("supports_json_schema_output") or transformer_class is None:
            return None
        transformer = transformer_class(self.json_schema, strict=None)
        json_schema: dict[str, Any] = {"name": self.name, "schema": transformer.walk()}
        if profile.get("openai_supports_strict_tool_definition", True):
            json_schema["strict"] = transformer.is_strict_compatible
        return {"type": "json_schema", "json_schema": json_schema}

    def anthropic_output_format(self, model: str) -> dict[str, Any] | None:
        """The `output_config.format` for a Claude model, or None when its profile has no
        JSON-schema output. The schema goes through the Anthropic transform, which keeps the
        subset the API compiles and moves the other constraints into descriptions."""
        from pydantic_ai.profiles.anthropic import anthropic_model_profile
        from pydantic_ai.providers.anthropic import AnthropicJsonSchemaTransformer

        profile = anthropic_model_profile(model)
        if profile is None or not profile.get("supports_json_schema_output"):
            return None
        schema = AnthropicJsonSchemaTransformer(self.json_schema, strict=True).walk()
        return {"type": "json_schema", "schema": schema}


# The schema the replies of the calls made inside `constrain_reply` must match. It travels with
# the context, like the reply cap, so a structured call can ask the provider to constrain its
# decoding without every layer between it and the request payload taking a parameter.
reply_schema: ContextVar[ReplySchema | None] = ContextVar("reply_schema", default=None)


@contextmanager
def constrain_reply(schema: ReplySchema) -> Generator[None]:
    """Ask the provider to constrain the reply of every LLM call made inside the block to
    ``schema``, where the provider takes such a parameter."""
    token = reply_schema.set(schema)
    try:
        yield
    finally:
        reply_schema.reset(token)


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
    from devops_cli.core.repo import resolve_store_path

    state_file = resolve_store_path(f"devops_cli_ollama_rr_{uid}")
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
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


def _observe_ollama_slot_wait(started: float, priority: RequestPriority, outcome: str) -> None:
    """Observe the seconds since `started` as one wait for an Ollama slot."""
    emit(
        AI_OLLAMA_SLOT_WAIT,
        time.monotonic() - started,
        {"priority": priority.value, "outcome": outcome},
    )


@contextmanager
def acquire_ollama_slot(
    candidates: list[str],
    max_parallel: int,
    timeout: float | None = None,
    priority: RequestPriority | str | None = None,
) -> Generator[str]:
    """Dynamically lease an available Ollama slot across candidate nodes with priority scheduling.

    The lease counts the calls of this process only. `active_ollama_requests` and
    `ollama_slot_condition` are module state, so two processes can each hold `max_parallel`
    leases on one URL. This is by design. A lease across processes would add a hidden queue in
    front of the queue of Ollama itself (`OLLAMA_NUM_PARALLEL` 1), as the gateway caps did
    before #467. Ollama queues the excess calls itself.

    Each call observes its wait once, as `devops_cli_ai_ollama_slot_wait_seconds` by priority
    and outcome (ok once it holds a slot, or timeout), after it leaves the condition.
    """
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

    started = time.monotonic()
    deadline = started + eff_timeout
    leased_url: str | None = None

    try:
        with ollama_slot_condition:
            waiting_priority_requests[resolved_p] = waiting_priority_requests.get(resolved_p, 0) + 1
            try:
                leased_url = _wait_for_slot(
                    candidates, max_parallel, resolved_p, deadline, eff_timeout
                )
            finally:
                waiting_priority_requests[resolved_p] = max(
                    0, waiting_priority_requests.get(resolved_p, 0) - 1
                )
    except AIClientError:
        _observe_ollama_slot_wait(started, resolved_p, "timeout")
        raise
    _observe_ollama_slot_wait(started, resolved_p, "ok")

    try:
        yield leased_url
    finally:
        _release_ollama_slot(leased_url)


def uses_gateway_slots(config: Any) -> bool:
    """Whether a client's chat calls take the gateway's backend slots: the `gateway` provider's.

    `ai.gateway_enabled` alone sends no chat call to the gateway, so it takes no slot.
    """
    return getattr(config, "provider", None) == CONST_AI_GATEWAY_PROVIDER


def _wait_for_gateway_slot() -> float:
    """Take one of the gateway's backend slots and return the seconds spent waiting for it.

    The wait is an `ai.llm.gateway_slot` span under the call's span and an observation of
    `devops_cli_ai_gateway_slot_wait_seconds`, so a call queued in this process is told apart
    from a slow reply. It is bounded by `DEFAULT_GATEWAY_SLOT_TIMEOUT_SECONDS`; past it the
    request is refused with an `AIClientError` naming the slot count.
    """
    timeout = DEFAULT_GATEWAY_SLOT_TIMEOUT_SECONDS
    with trace_span(
        "ai.llm.gateway_slot", {"llm.gateway.slots": DEFAULT_GATEWAY_REVIEW_CONCURRENCY}
    ) as span_handle:
        started = time.monotonic()
        held = gateway_slots.acquire(timeout=timeout)
        waited = time.monotonic() - started
        span_handle.set_attribute("llm.gateway.slot_wait_seconds", waited)
        emit(AI_GATEWAY_SLOT_WAIT, waited, {"outcome": "ok" if held else "timeout"})
        if not held:
            raise AIClientError(
                f"Timed out after {timeout:g}s waiting for one of the gateway's "
                f"{DEFAULT_GATEWAY_REVIEW_CONCURRENCY} backend slots."
            )
    return waited


@contextmanager
def acquire_gateway_slot() -> Generator[float]:
    """Hold one of the gateway's backend slots for the block, yielding how long it waited."""
    waited = _wait_for_gateway_slot()
    try:
        yield waited
    finally:
        gateway_slots.release()


# The process's most model calls in flight at once, held by the roadmap Service from its
# configuration (#2564). None until the Service sets it: a CLI process sends its calls with no
# such limit. A lane that cannot take a slot waits in the process, where no stall timer runs.
_model_call_sem: threading.Semaphore | None = None


def set_model_call_limit(limit: int) -> threading.Semaphore:
    """Set the process's most model calls in flight at once and return its shared semaphore.

    A limit of one keeps one model call in flight, as the Service's single-slot model tier
    serves. A higher limit admits more, and a limit of zero or less is read as one.
    """
    global _model_call_sem
    _model_call_sem = threading.Semaphore(max(1, int(limit)))
    return _model_call_sem


def get_model_call_limit() -> threading.Semaphore | None:
    """The process's model call limit, or None when the process sets none."""
    return _model_call_sem


def reset_model_call_limit() -> None:
    """Remove the process's model call limit (for tests)."""
    global _model_call_sem
    _model_call_sem = None


@contextmanager
def model_call_slot() -> Generator[None]:
    """Hold the process's model call slot for the block; none when the process sets no limit.

    The slot is the standard library's `threading.Semaphore`, shared by the Service's worker
    threads, so a lane that cannot take one waits in the process instead of queueing at the
    gateway, where a stall timer would refuse it (#2564).
    """
    sem = _model_call_sem
    if sem is None:
        yield
        return
    sem.acquire()
    try:
        yield
    finally:
        sem.release()


@contextmanager
def track_ollama_url(
    url: str,
    max_parallel: int,
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
    global global_ollama_url_index
    with ollama_slot_condition:
        active_ollama_requests.clear()
        for p in RequestPriority:
            waiting_priority_requests[p] = 0
        ollama_slot_condition.notify_all()
    with global_ollama_url_lock:
        global_ollama_url_index = 0


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
    """Validate a configured base URL against scheme and host rules.

    The pre-flight DNS check is removed; the factory client checks at the connect
    (ai/client/base.py:64-66). Scheme and host checks stay for early syntax errors.
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

    return base_url.rstrip("/")
