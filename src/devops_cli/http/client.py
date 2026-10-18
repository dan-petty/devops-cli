"""The HTTP client factory: every client it builds dials only what its egress level allows.

httpx2 ignores `verify`, `http2` and `limits` on a client given `transport=`, so the factory owns
them and builds the transport itself. httpx2's transports take no network backend
(`HTTPTransport.__init__` in httpx2 2.13.1), so the factory replaces the connection pool each one
builds with an httpcore2 pool, httpcore2's public API, holding the vetting backend of
`devops_cli.http.egress`. `tests/test_http_egress.py` pins that seam, so an httpx2 upgrade that
moves it fails the suite instead of dropping the check.

A factory client ignores HTTP_PROXY, HTTPS_PROXY and ALL_PROXY. httpx2 reads them only for a
client without `transport=`, and a proxy would become the vetted peer in place of the destination.
"""

from __future__ import annotations

import ssl
from collections.abc import Callable, Mapping
from typing import Any, TypedDict, Unpack

import httpcore2
import httpx2

from devops_cli.config.defaults import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_HTTP_KEEPALIVE_EXPIRY_SECONDS,
    DEFAULT_HTTP_MAX_CONNECTIONS,
    DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_POOL_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.http.egress import AsyncVettingBackend, EgressLevel, VettingBackend


class HTTPTimeoutTypeError(ValidationError, TypeError):
    """Raised when an invalid timeout parameter type is provided."""


class ClientOptions(TypedDict, total=False):
    """httpx2 client options a factory client accepts: none of them changes where it connects."""

    headers: Mapping[str, str]
    follow_redirects: bool
    max_redirects: int
    event_hooks: Mapping[str, list[Callable[..., Any]]]
    base_url: str


def request_timeout(
    *,
    read: float | None = None,
    connect: float | None = None,
) -> httpx2.Timeout:
    """Build an httpx2.Timeout object configured with project default HTTP timeout bounds (short connect, long read)."""
    return httpx2.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT_SECONDS if connect is None else connect,
        read=DEFAULT_HTTP_TIMEOUT_SECONDS if read is None else read,
        write=DEFAULT_HTTP_TIMEOUT_SECONDS,
        pool=DEFAULT_POOL_TIMEOUT_SECONDS,
    )


def connection_limits() -> httpx2.Limits:
    """Bound how many sockets a client may hold.

    Reusing connections without a ceiling trades connection churn for descriptor
    exhaustion, which is the failure connection pooling is supposed to prevent rather than cause.
    """
    return httpx2.Limits(
        max_connections=DEFAULT_HTTP_MAX_CONNECTIONS,
        max_keepalive_connections=DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS,
        keepalive_expiry=DEFAULT_HTTP_KEEPALIVE_EXPIRY_SECONDS,
    )


def _resolve_client_timeout(
    timeout: httpx2.Timeout | float | None,
    read_timeout: float | None,
) -> httpx2.Timeout:
    """Validate timeout parameter types and resolve standard short-connect timeout."""
    if timeout is not None and not isinstance(timeout, (int, float, httpx2.Timeout)):
        raise HTTPTimeoutTypeError(
            f"timeout must be int, float, httpx2.Timeout, or None, got {type(timeout).__name__}"
        )
    if read_timeout is not None and not isinstance(read_timeout, (int, float)):
        raise HTTPTimeoutTypeError(
            f"read_timeout must be int, float, or None, got {type(read_timeout).__name__}"
        )
    if isinstance(timeout, httpx2.Timeout):
        return timeout
    if isinstance(timeout, (int, float)):
        return request_timeout(read=float(timeout))
    return request_timeout(read=read_timeout)


def egress_transport(
    level: EgressLevel,
    *,
    verify: ssl.SSLContext | bool = True,
    http2: bool = False,
    limits: httpx2.Limits | None = None,
) -> httpx2.HTTPTransport:
    """An httpx2 transport whose connections dial only the addresses `level` allows."""
    ssl_context = httpx2.create_ssl_context(verify=verify)
    bounds = limits or connection_limits()
    transport = httpx2.HTTPTransport(verify=ssl_context, http2=http2, limits=bounds)
    transport._pool = httpcore2.ConnectionPool(
        ssl_context=ssl_context,
        max_connections=bounds.max_connections,
        max_keepalive_connections=bounds.max_keepalive_connections,
        keepalive_expiry=bounds.keepalive_expiry,
        http1=True,
        http2=http2,
        network_backend=VettingBackend(level),
    )
    return transport


def async_egress_transport(
    level: EgressLevel,
    *,
    verify: ssl.SSLContext | bool = True,
    http2: bool = True,
    limits: httpx2.Limits | None = None,
) -> httpx2.AsyncHTTPTransport:
    """The async `egress_transport`."""
    ssl_context = httpx2.create_ssl_context(verify=verify)
    bounds = limits or connection_limits()
    transport = httpx2.AsyncHTTPTransport(verify=ssl_context, http2=http2, limits=bounds)
    transport._pool = httpcore2.AsyncConnectionPool(
        ssl_context=ssl_context,
        max_connections=bounds.max_connections,
        max_keepalive_connections=bounds.max_keepalive_connections,
        keepalive_expiry=bounds.keepalive_expiry,
        http1=True,
        http2=http2,
        network_backend=AsyncVettingBackend(level),
    )
    return transport


def new_http_client(
    *,
    level: EgressLevel,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    verify: ssl.SSLContext | bool = True,
    http2: bool = False,
    limits: httpx2.Limits | None = None,
    retries: int | None = None,
    **options: Unpack[ClientOptions],
) -> httpx2.Client:
    """Create an httpx2.Client that dials only what `level` allows, with short-connect timeouts.

    `retries` wraps the transport in the tenacity retry transport for that many attempts. That
    transport turns every 4xx and 5xx response into httpx2.HTTPStatusError and retries 429, 5xx
    and connect failures, so only a caller built for those semantics, as the AI clients are,
    passes it. A refusal (SSRFBlockedError) is not an httpx2 error and is never retried.
    """
    transport: httpx2.BaseTransport = egress_transport(
        level, verify=verify, http2=http2, limits=limits
    )
    if retries is not None:
        from devops_cli.ai.retries import create_retry_transport

        transport = create_retry_transport(max_attempts=retries, wrapped=transport)
    return httpx2.Client(
        timeout=_resolve_client_timeout(timeout, read_timeout), transport=transport, **options
    )


def new_async_http_client(
    *,
    level: EgressLevel,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    verify: ssl.SSLContext | bool = True,
    http2: bool = True,
    limits: httpx2.Limits | None = None,
    **options: Unpack[ClientOptions],
) -> httpx2.AsyncClient:
    """Create an httpx2.AsyncClient that dials only what `level` allows, with HTTP/2."""
    transport = async_egress_transport(level, verify=verify, http2=http2, limits=limits)
    return httpx2.AsyncClient(
        timeout=_resolve_client_timeout(timeout, read_timeout), transport=transport, **options
    )


__all__ = [
    "ClientOptions",
    "HTTPTimeoutTypeError",
    "async_egress_transport",
    "connection_limits",
    "egress_transport",
    "new_async_http_client",
    "new_http_client",
    "request_timeout",
]
