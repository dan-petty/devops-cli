"""Tenacity-based HTTPX2 retry transports that honour Retry-After."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final, cast

import httpx2
from pydantic_ai.retries import (
    AsyncHTTPX2TenacityTransport,
    HTTPX2TenacityTransport,
    RetryConfig,
    wait_retry_after,
)
from tenacity import (
    RetryCallState,
    retry_if_exception,
    wait_exponential,
    wait_exponential_jitter,
)
from tenacity.stop import stop_base

from devops_cli.config.constants import CONST_RETRYABLE_HTTP_STATUS_CODES
from devops_cli.core import clock

DEFAULT_RETRYABLE_STATUS_CODES: tuple[int, ...] = CONST_RETRYABLE_HTTP_STATUS_CODES

# The failures of a request that never reached the server: a failed connect, and no free
# connection in the pool.
_NOT_SENT_ERRORS: Final = (httpx2.ConnectError, httpx2.ConnectTimeout, httpx2.PoolTimeout)


def connect_failed(exc: BaseException) -> bool:
    """Whether `exc` ended a request before it reached the server: the retry rule of a client
    whose server retries every other failure itself, as the LLM gateway does (#5965)."""
    return isinstance(exc, _NOT_SENT_ERRORS)


def is_retryable_status_code(
    status_code: int,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
) -> bool:
    """Predicate determining if an HTTP status code represents a transient, retryable condition.

    All 5xx server/gateway errors and transient 4xx errors (e.g. 408, 429) are considered retryable.
    """
    return status_code in retry_statuses or (500 <= status_code < 600)


def is_pre_chunk_reset(exc: BaseException) -> bool:
    """Whether an exception while reading a reply stream is a connection reset before data."""
    import httpcore2

    # If it is a connect failure or status error, the transport handles it; do not treat as stream reset
    curr: BaseException | None = exc
    seen: set[int] = set()
    while curr is not None and id(curr) not in seen:
        seen.add(id(curr))
        if connect_failed(curr) or isinstance(curr, httpx2.HTTPStatusError):
            return False
        curr = getattr(curr, "__cause__", None)

    curr = exc
    seen.clear()
    while curr is not None and id(curr) not in seen:
        seen.add(id(curr))
        if isinstance(
            curr,
            (
                httpx2.ReadError,
                httpcore2.ReadError,
                ConnectionResetError,
                BrokenPipeError,
                httpx2.RemoteProtocolError,
                httpcore2.RemoteProtocolError,
            ),
        ):
            return True
        if "Provider stream ended before its final frame." in str(curr):
            return True
        curr = getattr(curr, "__cause__", None)

    return False


class _TransportRetryStop(stop_base):
    """Stop strategy for AI client HTTP transport:
    - Allows up to `connect_max_attempts` (10) for connect errors, regardless of `max_attempts`.
    - Allows up to `max_attempts` for other retryable failures.
    - Stops before the outer read timeout elapses (no attempt starts when its connect timeout
      would pass the read timeout).
    """

    def __init__(self, max_attempts: int = 5, connect_max_attempts: int | None = None) -> None:
        self.max_attempts = max_attempts
        self.connect_max_attempts = (
            connect_max_attempts if connect_max_attempts is not None else max_attempts
        )

    def __call__(self, retry_state: RetryCallState) -> bool:
        exc = (
            retry_state.outcome.exception()
            if retry_state.outcome and retry_state.outcome.failed
            else None
        )
        is_connect = connect_failed(exc) if exc is not None else False
        limit = self.connect_max_attempts if is_connect else self.max_attempts
        if retry_state.attempt_number >= limit:
            return True

        if is_connect:
            req = retry_state.args[0] if retry_state.args else None
            if req is not None:
                started = req.extensions.setdefault("_retry_started", clock.monotonic())
                timeout_ext = req.extensions.get("timeout") or {}
                read_timeout = timeout_ext.get("read")
                connect_timeout = timeout_ext.get("connect", 5.0)
                if connect_timeout is None:
                    connect_timeout = 5.0
                else:
                    connect_timeout = min(connect_timeout, 5.0)
                if read_timeout is not None:
                    elapsed = clock.monotonic() - started
                    upcoming = getattr(retry_state, "upcoming_sleep", 0.0) or 0.0
                    if elapsed + upcoming + connect_timeout > read_timeout:
                        return True

        return False


def create_retry_config(
    max_attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
    reraise: bool = True,
    retry_on: Callable[[BaseException], bool] | None = None,
    connect_max_attempts: int | None = None,
    jitter: float = 0.0,
    **kwargs: Any,
) -> RetryConfig:
    """Construct a native RetryConfig with tenacity stop, wait_retry_after, and retry strategies.

    `retry_on` replaces the rule that says which failure is sent again, such as `connect_failed`.
    """

    def should_retry(exc: BaseException) -> bool:
        if isinstance(exc, (httpx2.TransportError, httpx2.TimeoutException)):
            return True
        if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
            return True
        if isinstance(exc, httpx2.HTTPStatusError):
            return is_retryable_status_code(exc.response.status_code, retry_statuses)
        return False

    fallback_strategy: Any
    if jitter > 0:
        fallback_strategy = wait_exponential_jitter(initial=min_wait, max=max_wait, jitter=jitter)
    else:
        fallback_strategy = wait_exponential(multiplier=min_wait, max=max_wait)

    wait_strategy = wait_retry_after(
        fallback_strategy=fallback_strategy,
        max_wait=max_wait,
    )

    config: RetryConfig = {
        "stop": _TransportRetryStop(
            max_attempts=max_attempts, connect_max_attempts=connect_max_attempts
        ),
        "wait": wait_strategy,
        "retry": retry_if_exception(retry_on or should_retry),
        "reraise": reraise,
    }
    cast(dict[str, Any], config).update(kwargs)
    return config


class ExpiringConnectionTransport(httpx2.BaseTransport):
    """Transport wrapper that closes expired and cut connections on each request attempt."""

    def __init__(self, wrapped: httpx2.BaseTransport) -> None:
        self.wrapped = wrapped

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        from devops_cli.http.pool import close_expired_connections

        request.extensions.setdefault("_retry_started", clock.monotonic())
        try:
            return self.wrapped.handle_request(request)
        finally:
            close_expired_connections(self.wrapped)

    def close(self) -> None:
        self.wrapped.close()


class AsyncExpiringConnectionTransport(httpx2.AsyncBaseTransport):
    """Async transport wrapper that closes expired and cut connections on each request attempt."""

    def __init__(self, wrapped: httpx2.AsyncBaseTransport) -> None:
        self.wrapped = wrapped

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        from devops_cli.http.pool import close_expired_connections

        request.extensions.setdefault("_retry_started", clock.monotonic())
        try:
            return await self.wrapped.handle_async_request(request)
        finally:
            close_expired_connections(self.wrapped)

    async def aclose(self) -> None:
        await self.wrapped.aclose()


def create_retry_transport(
    *,
    wrapped: httpx2.BaseTransport,
    config: RetryConfig | None = None,
    max_attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
    validate_response: Callable[[httpx2.Response], Any] | None = None,
    retry_on: Callable[[BaseException], bool] | None = None,
    **kwargs: Any,
) -> HTTPX2TenacityTransport:
    """Construct a synchronous HTTPX2TenacityTransport with automatic Retry-After inspection.

    `wrapped` is the transport that sends each attempt. It has no default, because a default
    transport would dial without the egress check: a caller passes the one that
    `devops_cli.http.client` builds. `retry_on` is the rule of `create_retry_config`.
    """
    base_config = config or create_retry_config(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        retry_statuses=retry_statuses,
        retry_on=retry_on,
        **kwargs,
    )
    active_config: RetryConfig = {"sleep": clock.sleep, **base_config}

    def default_validate(resp: httpx2.Response) -> None:
        if resp.status_code >= 400:
            resp.raise_for_status()

    validator = validate_response or default_validate
    return HTTPX2TenacityTransport(
        active_config,
        validate_response=validator,
        wrapped=ExpiringConnectionTransport(wrapped),
    )


def create_async_retry_transport(
    *,
    wrapped: httpx2.AsyncBaseTransport,
    config: RetryConfig | None = None,
    max_attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
    validate_response: Callable[[httpx2.Response], Any] | None = None,
    **kwargs: Any,
) -> AsyncHTTPX2TenacityTransport:
    """Construct an asynchronous HTTPX2TenacityTransport with automatic Retry-After inspection.

    `wrapped` is the transport that sends each attempt.
    """
    base_config = config or create_retry_config(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        retry_statuses=retry_statuses,
        **kwargs,
    )

    async def _async_sleep(seconds: float) -> None:
        clock.sleep(seconds)

    active_config: RetryConfig = {"sleep": _async_sleep, **base_config}

    validator = validate_response
    return AsyncHTTPX2TenacityTransport(
        active_config,
        validate_response=validator,
        wrapped=AsyncExpiringConnectionTransport(wrapped),
    )


__all__ = [
    "connect_failed",
    "create_async_retry_transport",
    "create_retry_config",
    "create_retry_transport",
    "is_pre_chunk_reset",
    "is_retryable_status_code",
]
