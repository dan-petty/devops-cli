"""What `devops_cli.http.entry` builds a client from: the egress transports, the timeouts and the
transport hook of a test. Every client the entry point builds dials only what its egress level
allows.

httpx2 ignores `verify`, `http2` and `limits` on a client given `transport=`, so the entry point
owns them and builds the transport itself. httpx2's transports take no network backend
(`HTTPTransport.__init__` in httpx2 2.13.1), so each egress transport replaces the connection pool
that httpx2 builds with an httpcore2 pool, httpcore2's public API, holding the vetting backend of
`devops_cli.http.egress`. `tests/http/test_http_egress.py` pins that seam, so an httpx2 upgrade that
moves it fails the suite instead of dropping the check.

A client of the entry point ignores HTTP_PROXY, HTTPS_PROXY and ALL_PROXY. httpx2 reads them only
for a client without `transport=`, and a proxy would become the vetted peer in place of the
destination.

Every client takes its transport from one place: the transport that a test installed with
`devops_cli.http.entry.install_transport`, else the egress transport of its level.
"""

from __future__ import annotations

import ssl
from collections.abc import Callable, Mapping
from typing import Any, TypedDict

import httpcore2
import httpx2

from devops_cli.config.constants import CONST_APP_NAME
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
    """httpx2 client options that the entry point accepts: none of them changes where it connects."""

    headers: Mapping[str, str]
    follow_redirects: bool
    max_redirects: int
    event_hooks: Mapping[str, list[Callable[..., Any]]]
    base_url: str


TransportFactory = Callable[[EgressLevel], httpx2.BaseTransport | httpx2.AsyncBaseTransport]
"""What a test installs to replace the egress transport: it gets a client's level and gives the
transport that client uses, which may vet the destination at that level."""

_TRANSPORT_HOOK: TransportFactory | None = None


def set_transport_hook(factory: TransportFactory | None) -> None:
    """Install, or with None remove, the transport that every client of the entry point uses.

    Callers go through `devops_cli.http.entry.install_transport`, which closes the pooled clients
    first: a client built earlier keeps the transport it was built with.
    """
    global _TRANSPORT_HOOK
    _TRANSPORT_HOOK = factory


def has_transport_hook() -> bool:
    """Report whether a test has installed a transport."""
    return _TRANSPORT_HOOK is not None


def reset_transport_hook() -> None:
    """Remove the installed transport, so every client of the entry point takes its egress transport."""
    global _TRANSPORT_HOOK
    _TRANSPORT_HOOK = None


def hooked_transport[T: (httpx2.BaseTransport, httpx2.AsyncBaseTransport)](
    level: EgressLevel, kind: type[T]
) -> T | None:
    """The installed transport for a client at `level`, or None when none is installed.

    An installed transport that does not serve the kind of client asked for is a bug in the test.
    """
    if _TRANSPORT_HOOK is None:
        return None
    transport = _TRANSPORT_HOOK(level)
    if not isinstance(transport, kind):
        raise TypeError(
            f"The installed transport is a {type(transport).__name__}, not a {kind.__name__}"
        )
    return transport


def user_agent() -> str:
    """devops-cli's User-Agent: its name and the installed release."""
    from devops_cli import __version__

    return f"{CONST_APP_NAME}/{__version__}"


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


def resolve_client_timeout(
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


__all__ = [
    "ClientOptions",
    "HTTPTimeoutTypeError",
    "TransportFactory",
    "async_egress_transport",
    "connection_limits",
    "egress_transport",
    "has_transport_hook",
    "hooked_transport",
    "request_timeout",
    "reset_transport_hook",
    "resolve_client_timeout",
    "set_transport_hook",
    "user_agent",
]
