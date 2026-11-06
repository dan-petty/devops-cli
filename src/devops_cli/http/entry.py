"""The one entry point that builds httpx2 clients, and the hook that replaces their transport.

`http_client` and `async_http_client` build every client: unpooled, or pooled when the caller
names a `key`. A client dials only what its egress level allows (`devops_cli.http.egress`), and
takes its transport from one place: the transport that `install_transport` put in place, else
the egress transport of its level (`devops_cli.http.client`). Nothing here builds a
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
    async_egress_transport,
    connection_limits,
    egress_transport,
    has_transport_hook,
    hooked_transport,
    request_timeout,
    reset_transport_hook,
    resolve_client_timeout,
    set_transport_hook,
    user_agent,
)
from devops_cli.http.egress import EgressLevel
from devops_cli.http.pool import (
    close_shared_clients,
    pooled_async_client,
    pooled_client,
)
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

    `http2` is off unless set. `retries` wraps the transport in the tenacity retry transport for
    that many attempts. That transport turns every 4xx and 5xx response into
    `httpx2.HTTPStatusError` and retries 429, 5xx and connect failures, so only a caller built for
    those semantics, as the AI clients are, passes it. A refusal (`SSRFBlockedError`) is not an
    httpx2 error and is never retried.

    A pooled client follows redirects unless the caller says otherwise, and uses the default
    timeout and the default connection limits.
    """
    if key is not None:
        if (read_timeout, timeout, http2, limits, transport) != (None,) * 5:
            raise TypeError(f"{_POOL_FIXES}; build an unpooled client to set one")
        options.setdefault("follow_redirects", True)
        return pooled_client(
            f"{level}:{key}",
            lambda: _build_client(
                level,
                timeout=request_timeout(),
                verify=verify,
                http2=True,
                limits=connection_limits(),
                retries=retries,
                **options,
            ),
        )
    return _build_client(
        level,
        read_timeout=read_timeout,
        timeout=timeout,
        verify=verify,
        http2=bool(http2),
        limits=limits,
        retries=retries,
        transport=transport,
        **options,
    )


def _build_client(
    level: EgressLevel,
    *,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    verify: ssl.SSLContext | bool,
    http2: bool,
    limits: httpx2.Limits | None = None,
    retries: int | None = None,
    transport: httpx2.BaseTransport | None = None,
    **options: Unpack[ClientOptions],
) -> httpx2.Client:
    """The synchronous client: short-connect timeouts and the transport of the hook or of `level`."""
    if transport is None:
        transport = hooked_transport(level, httpx2.BaseTransport)
    effective_transport: httpx2.BaseTransport = (
        transport
        if transport is not None
        else egress_transport(level, verify=verify, http2=http2, limits=limits)
    )
    if retries is not None:
        from devops_cli.ai.retries import create_retry_transport
        from devops_cli.ai.spend.transport import AttemptRecordingTransport

        effective_transport = AttemptRecordingTransport(effective_transport)
        effective_transport = create_retry_transport(
            max_attempts=retries, wrapped=effective_transport
        )
    return httpx2.Client(
        timeout=resolve_client_timeout(timeout, read_timeout),
        transport=effective_transport,
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
        options.setdefault("follow_redirects", True)
        return pooled_async_client(
            f"{level}:{key}",
            lambda: _build_async_client(
                level,
                timeout=request_timeout(),
                verify=verify,
                http2=True,
                limits=connection_limits(),
                **options,
            ),
        )
    return _build_async_client(
        level,
        read_timeout=read_timeout,
        timeout=timeout,
        verify=verify,
        http2=http2 is None or http2,
        limits=limits,
        transport=transport,
        **options,
    )


def _build_async_client(
    level: EgressLevel,
    *,
    read_timeout: float | None = None,
    timeout: httpx2.Timeout | float | None = None,
    verify: ssl.SSLContext | bool,
    http2: bool,
    limits: httpx2.Limits | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
    **options: Unpack[ClientOptions],
) -> httpx2.AsyncClient:
    """The asynchronous client: short-connect timeouts and the transport of the hook or of `level`."""
    if transport is None:
        transport = hooked_transport(level, httpx2.AsyncBaseTransport)
    effective_transport: httpx2.AsyncBaseTransport = (
        transport
        if transport is not None
        else async_egress_transport(level, verify=verify, http2=http2, limits=limits)
    )
    return httpx2.AsyncClient(
        timeout=resolve_client_timeout(timeout, read_timeout),
        transport=effective_transport,
        **options,
    )


def install_transport(factory: TransportFactory) -> None:
    """Make every client built from now on take the transport that `factory` gives for its level.

    The pooled clients close first, so none keeps a transport built before. The factory serves
    sync clients with an `httpx2.BaseTransport` and async clients with an
    `httpx2.AsyncBaseTransport`; `httpx2.MockTransport` is both. A second install raises
    `RuntimeError`, because one test with two fakes of HTTP would let the later one win without
    a sign; `remove_transport` first.
    """
    if has_transport_hook():
        raise RuntimeError("A transport is already installed; remove_transport() before another")
    close_shared_clients()
    set_transport_hook(factory)


def remove_transport() -> None:
    """Take the installed transport away, after closing the pooled clients that used it."""
    close_shared_clients()
    reset_transport_hook()


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
