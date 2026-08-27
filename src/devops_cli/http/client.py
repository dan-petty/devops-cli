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


def new_http_client(
    *,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    **kwargs: Any,
) -> httpx2.Client:
    """Create a new httpx2.Client configured with default short connect and resilient read timeouts."""
    client_timeout = (
        timeout
        if isinstance(timeout, httpx2.Timeout)
        else (
            httpx2.Timeout(timeout, connect=DEFAULT_CONNECT_TIMEOUT_SECONDS)
            if isinstance(timeout, (int, float))
            else request_timeout(read=read_timeout)
        )
    )
    return httpx2.Client(timeout=client_timeout, **kwargs)
