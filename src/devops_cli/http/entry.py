"""The one entry point that builds httpx2 clients, and the hook that replaces their transport.

`http_client` and `async_http_client` build every client: unpooled, or pooled when the caller
names a `key`. A client dials only what its egress level allows (`devops_cli.http.egress`), and
takes its transport from one place, `devops_cli.http.client`: the transport that
`install_transport` put in place, else the egress transport of its level. Nothing here builds a
client or reads a setting at import; the egress level is read when a client is built.

`install_transport` and `remove_transport` are the hook for a test. Each closes the pooled clients
first, so no client built earlier keeps the old transport. The pool keeps its public reset,
`close_shared_clients`, and its `atexit` close (`devops_cli.http.pool`).

`request_headers` and `veto_request` are what a caller that sends a request itself adds to it: the
User-Agent and the W3C `traceparent` header, and a veto of any scheme but http and https, and of a
redirect hop that the request's own egress policy refuses.
"""

from __future__ import annotations

import ssl
from typing import Unpack

import httpx2

from devops_cli.config.constants import CONST_HTTP_EGRESS_POLICY_EXTENSION
from devops_cli.exceptions import InvalidURLError
from devops_cli.http.client import (
    ClientOptions,
    TransportFactory,
    new_async_http_client,
    new_http_client,
    set_transport_hook,
    user_agent,
)
from devops_cli.http.egress import EgressLevel
from devops_cli.http.pool import close_shared_clients, get_shared_async_client, get_shared_client
from devops_cli.telemetry.context import inject_traceparent_headers

_POOL_FIXES = "A pooled client fixes its timeout, protocol, limits and transport"


def http_client(
    level: EgressLevel,
    *,
    key: str | None = None,
    retries: int | None = None,
    verify: ssl.SSLContext | bool = True,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    http2: bool | None = None,
    limits: httpx2.Limits | None = None,
    transport: httpx2.BaseTransport | None = None,
    **options: Unpack[ClientOptions],
) -> httpx2.Client:
    """Build a synchronous client that dials only what `level` allows.

    With a `key` the client is pooled: callers that name the same key and level share one client,
    and so its connections, and the caller does not close it. `key` names the transport
    configuration, such as the endpoint and its TLS material, never the caller. A pooled client
    sets its own timeout, protocol, limits and transport, so passing one with a `key` is a
    TypeError. Without a `key` the caller owns the client and closes it.

    `http2` is off unless set. `retries` wraps the transport in the retry transport for that many
    attempts; see `devops_cli.http.client.new_http_client` for what that changes.
    """
    if key is not None:
        if (read_timeout, timeout, http2, limits, transport) != (None,) * 5:
            raise TypeError(f"{_POOL_FIXES}; build an unpooled client to set one")
        return get_shared_client(key, level, verify=verify, retries=retries, **options)
    return new_http_client(
        level=level,
        read_timeout=read_timeout,
        timeout=timeout,
        verify=verify,
        http2=bool(http2),
        limits=limits,
        retries=retries,
        transport=transport,
        **options,
    )


def async_http_client(
    level: EgressLevel,
    *,
    key: str | None = None,
    verify: ssl.SSLContext | bool = True,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    http2: bool | None = None,
    limits: httpx2.Limits | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
    **options: Unpack[ClientOptions],
) -> httpx2.AsyncClient:
    """Build an asynchronous client that dials only what `level` allows.

    `key` pools it, as for `http_client`; a pooled client sets its own timeout, protocol, limits
    and transport. A caller of an unpooled client closes it. `http2` is on unless set.
    """
    if key is not None:
        if (read_timeout, timeout, http2, limits, transport) != (None,) * 5:
            raise TypeError(f"{_POOL_FIXES}; build an unpooled client to set one")
        return get_shared_async_client(key, level, verify=verify, **options)
    return new_async_http_client(
        level=level,
        read_timeout=read_timeout,
        timeout=timeout,
        verify=verify,
        http2=http2 is None or http2,
        limits=limits,
        transport=transport,
        **options,
    )


def install_transport(factory: TransportFactory) -> None:
    """Make every client built from now on take the transport that `factory` gives for its level.

    The pooled clients close first, so none keeps a transport built before. The factory serves
    sync clients with an `httpx2.BaseTransport` and async clients with an
    `httpx2.AsyncBaseTransport`; `httpx2.MockTransport` is both.
    """
    close_shared_clients()
    set_transport_hook(factory)


def remove_transport() -> None:
    """Take the installed transport away, after closing the pooled clients that used it."""
    close_shared_clients()
    set_transport_hook(None)


def request_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """`headers` with devops-cli's User-Agent, unless it has one, and the `traceparent` context."""
    complete = dict(headers or {})
    complete.setdefault("User-Agent", user_agent())
    return inject_traceparent_headers(complete)


def veto_request(request: httpx2.Request) -> None:
    """Veto the request and each redirect hop before it is sent.

    A request carrying its own egress policy is held to that policy, and every hop must be http or
    https. Which addresses a hop may reach is the connect's decision, made for the address dialled,
    so the hook does no lookup. Pass it in the `request` event hooks of a client.
    """
    if policy := request.extensions.get(CONST_HTTP_EGRESS_POLICY_EXTENSION):
        policy(str(request.url))
    if request.url.scheme not in ("http", "https"):
        raise InvalidURLError(
            str(request.url)[:256], reason="Only http and https URLs may be requested"
        )


async def aveto_request(request: httpx2.Request) -> None:
    """`veto_request` for the `request` event hooks of an async client."""
    veto_request(request)


__all__ = [
    "async_http_client",
    "aveto_request",
    "http_client",
    "install_transport",
    "remove_transport",
    "request_headers",
    "veto_request",
]
