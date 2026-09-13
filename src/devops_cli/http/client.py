"""Shared HTTP client creation and timeout configuration."""

from __future__ import annotations

from typing import Any

import httpx2

from devops_cli.config.defaults import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_POOL_TIMEOUT_SECONDS,
)


def request_timeout(*, read: float | None = None) -> httpx2.Timeout:
    """Build an httpx2.Timeout object configured with project default HTTP timeout bounds (short connect, long read)."""
    return httpx2.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read=DEFAULT_HTTP_TIMEOUT_SECONDS if read is None else read,
        write=DEFAULT_HTTP_TIMEOUT_SECONDS,
        pool=DEFAULT_POOL_TIMEOUT_SECONDS,
    )


def _resolve_client_timeout(
    timeout: httpx2.Timeout | float | None,
    read_timeout: float | None,
) -> httpx2.Timeout:
    """Validate timeout parameter types and resolve standard short-connect timeout."""
    if timeout is not None and not isinstance(timeout, (int, float, httpx2.Timeout)):
        raise TypeError(
            f"timeout must be int, float, httpx2.Timeout, or None, got {type(timeout).__name__}"
        )
    if read_timeout is not None and not isinstance(read_timeout, (int, float)):
        raise TypeError(
            f"read_timeout must be int, float, or None, got {type(read_timeout).__name__}"
        )
    if isinstance(timeout, httpx2.Timeout):
        return timeout
    if isinstance(timeout, (int, float)):
        return request_timeout(read=float(timeout))
    return request_timeout(read=read_timeout)


def new_http_client(
    *,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    **kwargs: Any,
) -> httpx2.Client:
    """Create a new httpx2.Client configured with default short connect and resilient read timeouts."""
    client_timeout = _resolve_client_timeout(timeout, read_timeout)
    return httpx2.Client(timeout=client_timeout, **kwargs)


def new_async_http_client(
    *,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    http2: bool = True,
    **kwargs: Any,
) -> httpx2.AsyncClient:
    """Create a new async httpx2.AsyncClient configured with HTTP/2 and resilient timeouts."""
    client_timeout = _resolve_client_timeout(timeout, read_timeout)
    return httpx2.AsyncClient(timeout=client_timeout, http2=http2, **kwargs)
