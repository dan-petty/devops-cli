"""Native Pydantic AI retries subsystem for devops-cli.

Provides native Tenacity-based HTTPX2 transports, Retry-After header parsing,
structured retry configurations, and agent retry budget normalization.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

import httpx2
from pydantic_ai import AgentRetries
from pydantic_ai.retries import (
    AsyncHTTPX2TenacityTransport,
    AsyncTenacityTransport,
    HTTPX2TenacityTransport,
    RetryConfig,
    TenacityTransport,
    wait_retry_after,
)
from tenacity import retry_if_exception, stop_after_attempt, wait_exponential

DEFAULT_RETRYABLE_STATUS_CODES: tuple[int, ...] = (408, 429, 500, 502, 503, 504)


def is_retryable_status_code(
    status_code: int,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
) -> bool:
    """Predicate determining if an HTTP status code represents a transient, retryable condition."""
    return status_code in retry_statuses


def create_retry_config(
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 60.0,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
    reraise: bool = True,
    **kwargs: Any,
) -> RetryConfig:
    """Construct a native RetryConfig with tenacity stop, wait_retry_after, and retry strategies."""

    def should_retry(exc: BaseException) -> bool:
        if isinstance(exc, (httpx2.TransportError, httpx2.TimeoutException)):
            return True
        if isinstance(exc, httpx2.HTTPStatusError):
            return is_retryable_status_code(exc.response.status_code, retry_statuses)
        return False

    wait_strategy = wait_retry_after(
        fallback_strategy=wait_exponential(multiplier=min_wait, max=max_wait),
        max_wait=max_wait,
    )

    config: RetryConfig = {
        "stop": stop_after_attempt(max_attempts),
        "wait": wait_strategy,
        "retry": retry_if_exception(should_retry),
        "reraise": reraise,
    }
    cast(dict[str, Any], config).update(kwargs)
    return config


def create_retry_transport(
    config: RetryConfig | None = None,
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 60.0,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
    validate_response: Callable[[httpx2.Response], Any] | None = None,
    wrapped: httpx2.BaseTransport | None = None,
    **kwargs: Any,
) -> HTTPX2TenacityTransport:
    """Construct a synchronous HTTPX2TenacityTransport with automatic Retry-After inspection."""
    active_config = config or create_retry_config(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        retry_statuses=retry_statuses,
        **kwargs,
    )

    def default_validate(resp: httpx2.Response) -> None:
        if is_retryable_status_code(resp.status_code, retry_statuses):
            resp.raise_for_status()

    validator = validate_response or default_validate
    return HTTPX2TenacityTransport(
        active_config,
        validate_response=validator,
        wrapped=wrapped,
    )


def create_async_retry_transport(
    config: RetryConfig | None = None,
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 60.0,
    retry_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES,
    validate_response: Callable[[httpx2.Response], Any] | None = None,
    wrapped: httpx2.AsyncBaseTransport | None = None,
    **kwargs: Any,
) -> AsyncHTTPX2TenacityTransport:
    """Construct an asynchronous AsyncHTTPX2TenacityTransport with automatic Retry-After inspection."""
    active_config = config or create_retry_config(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        retry_statuses=retry_statuses,
        **kwargs,
    )

    def default_validate(resp: httpx2.Response) -> None:
        if is_retryable_status_code(resp.status_code, retry_statuses):
            resp.raise_for_status()

    validator = validate_response or default_validate
    return AsyncHTTPX2TenacityTransport(
        active_config,
        validate_response=validator,
        wrapped=wrapped,
    )


def normalize_agent_retries(
    retries: int | AgentRetries | Mapping[str, int] | Any | None,
) -> AgentRetries:
    """Normalize integer, dict, or AgentRetries configurations into canonical AgentRetries TypedDict."""
    if retries is None:
        return {"tools": 1, "output": 1}
    if isinstance(retries, int):
        return {"tools": retries, "output": retries}
    if hasattr(retries, "tools") and hasattr(retries, "output"):
        return {
            "tools": int(getattr(retries, "tools", 1)),
            "output": int(getattr(retries, "output", 1)),
        }
    if isinstance(retries, Mapping):
        return {
            "tools": int(retries.get("tools", 1)),
            "output": int(retries.get("output", 1)),
        }
    return {"tools": 1, "output": 1}


__all__ = [
    "AgentRetries",
    "AsyncHTTPX2TenacityTransport",
    "AsyncTenacityTransport",
    "DEFAULT_RETRYABLE_STATUS_CODES",
    "HTTPX2TenacityTransport",
    "RetryConfig",
    "TenacityTransport",
    "create_async_retry_transport",
    "create_retry_config",
    "create_retry_transport",
    "is_retryable_status_code",
    "normalize_agent_retries",
    "wait_retry_after",
]
