"""Shared HTTP clients, so repeated calls reuse connections instead of rebuilding them.

The prevailing pattern across this codebase is::

    with new_http_client(level=EgressLevel.PUBLIC, timeout=...) as client:
        client.post(url, json=payload)

which builds a connection pool, performs one request, and tears the pool down. Every call
therefore pays for a fresh TCP handshake and a fresh TLS negotiation. Measured against real
endpoints:

===================  ==========  ==========  =======
Endpoint             Per client  Shared      Speedup
===================  ==========  ==========  =======
Cluster API (LAN)     19 ms/req   12 ms/req   1.5x
api.github.com (WAN) 247 ms/req   61 ms/req   4.1x
===================  ==========  ==========  =======

Clients are keyed on *transport* configuration only -- egress level, TLS material, redirects,
protocol -- because that is what a connection can be shared across. The egress level is part of
every key, so a connection a private-level client opened is never handed to a public-level one.
Anything that varies per call, such as headers or a per-request timeout, is passed to the request
instead, so an authorization header does not fragment the pool into one client per caller.
"""

from __future__ import annotations

import atexit
import inspect
import logging
import ssl
import threading
from contextlib import nullcontext
from typing import Any, Unpack

import httpx2

from devops_cli.http.client import (
    ClientOptions,
    connection_limits,
    new_async_http_client,
    new_http_client,
    request_timeout,
)
from devops_cli.http.egress import EgressLevel

logger = logging.getLogger(__name__)

_CLIENTS: dict[str, httpx2.Client] = {}
_ASYNC_CLIENTS: dict[str, httpx2.AsyncClient] = {}
_LOCK = threading.RLock()


def get_shared_client(
    key: str,
    level: EgressLevel,
    *,
    verify: ssl.SSLContext | bool = True,
    retries: int | None = None,
    **options: Unpack[ClientOptions],
) -> httpx2.Client:
    """Return a shared synchronous client for a transport profile at an egress level.

    `key` names the transport configuration, not the caller. Two callers reaching the same
    endpoint over the same TLS settings should share connections; giving each its own key
    would preserve the churn this exists to remove. The level joins the key.

    A client closed elsewhere is rebuilt rather than handed back unusable.
    """
    options.setdefault("follow_redirects", True)
    with _LOCK:
        pool_key = f"{level}:{key}"
        existing = _CLIENTS.get(pool_key)
        if existing is not None and not existing.is_closed:
            return existing
        client = new_http_client(
            level=level,
            timeout=request_timeout(),
            verify=verify,
            http2=True,
            limits=connection_limits(),
            retries=retries,
            **options,
        )
        _CLIENTS[pool_key] = client
        return client


def get_shared_async_client(
    key: str,
    level: EgressLevel,
    *,
    verify: ssl.SSLContext | bool = True,
    **options: Unpack[ClientOptions],
) -> httpx2.AsyncClient:
    """Return a shared asynchronous client for a transport profile at an egress level."""
    options.setdefault("follow_redirects", True)
    with _LOCK:
        pool_key = f"{level}:{key}"
        existing = _ASYNC_CLIENTS.get(pool_key)
        if existing is not None and not existing.is_closed:
            return existing
        client = new_async_http_client(
            level=level,
            timeout=request_timeout(),
            verify=verify,
            http2=True,
            limits=connection_limits(),
            **options,
        )
        _ASYNC_CLIENTS[pool_key] = client
        return client


def close_shared_clients() -> None:
    """Close every shared client, releasing their sockets.

    Registered to run at interpreter exit so a long-lived pool does not outlive the process
    that built it, and exposed so tests can start from a clean registry.
    """
    with _LOCK:
        for client in _CLIENTS.values():
            try:
                client.close()
            except Exception as exc:
                logger.debug("Failed closing shared HTTP client: %s", exc)
        _CLIENTS.clear()
        # Async clients need a running loop to close cleanly. At interpreter exit there is
        # none, so they are dropped: the sockets are released when the process ends, and
        # raising here would obscure whatever the process was actually doing.
        _ASYNC_CLIENTS.clear()


async def aclose_shared_clients() -> None:
    """Close every shared async client asynchronously, releasing sockets cleanly."""
    with _LOCK:
        clients = list(_ASYNC_CLIENTS.values())
        _ASYNC_CLIENTS.clear()
    for client in clients:
        try:
            if not client.is_closed:
                await client.aclose()
        except Exception as exc:
            logger.debug("Failed closing shared async HTTP client: %s", exc)


def _extract_connection_pool(target: Any) -> Any:
    """Find the underlying httpcore connection pool from a client, transport, or pool."""
    current = target
    for _ in range(5):
        if current is None:
            break
        if hasattr(current, "_pool"):
            return current._pool
        if hasattr(current, "wrapped"):
            current = getattr(current, "wrapped", None)
        elif hasattr(current, "_transport"):
            current = getattr(current, "_transport", None)
        elif hasattr(current, "_connections"):
            return current
        else:
            break
    return None


def _purge_connection_if_expired(conn: Any, connections: list[Any], closing: list[Any]) -> None:
    """Remove a connection from the pool and queue it for closing if expired or closed."""
    try:
        closed = conn.is_closed() if callable(getattr(conn, "is_closed", None)) else False
        expired = conn.has_expired() if callable(getattr(conn, "has_expired", None)) else False
        if closed:
            if conn in connections:
                connections.remove(conn)
        elif expired:
            if conn in connections:
                connections.remove(conn)
            closing.append(conn)
    except Exception as exc:
        logger.debug("Failed evaluating connection expiration: %s", exc)


def _close_connection_list(pool: Any, closing: list[Any]) -> None:
    """Close each connection in closing list using pool or direct method."""
    if not closing:
        return
    if callable(getattr(pool, "_close_connections", None)):
        try:
            pool._close_connections(closing)
            return
        except Exception as exc:
            logger.debug("Pool failed closing connections: %s", exc)
    for conn in closing:
        try:
            conn.close()
        except Exception as exc:
            logger.debug("Failed closing expired connection: %s", exc)


def close_expired_connections(target: Any) -> None:
    """Close and purge expired, closed, or server-disconnected connections from the target's pool."""
    pool = _extract_connection_pool(target)
    if pool is None:
        return
    connections = getattr(pool, "_connections", None)
    if not isinstance(connections, list):
        return

    closing: list[Any] = []
    lock = getattr(pool, "_optional_thread_lock", None)
    cm = lock if lock is not None else nullcontext()
    with cm:
        for conn in list(connections):
            _purge_connection_if_expired(conn, connections, closing)

    _close_connection_list(pool, closing)


async def _aclose_connection_list(pool: Any, closing: list[Any]) -> None:
    """Asynchronously close each connection in closing list using pool or direct method."""
    if not closing:
        return
    close_method = getattr(pool, "_close_connections", None)
    if callable(close_method):
        try:
            res = close_method(closing)
            if inspect.iscoroutine(res):
                await res
            return
        except Exception as exc:
            logger.debug("Pool failed closing connections asynchronously: %s", exc)
    for conn in closing:
        try:
            aclose = getattr(conn, "aclose", None)
            if callable(aclose):
                await aclose()
            elif callable(getattr(conn, "close", None)):
                conn.close()
        except Exception as exc:
            logger.debug("Failed closing expired connection asynchronously: %s", exc)


async def aclose_expired_connections(target: Any) -> None:
    """Close and purge expired, closed, or server-disconnected connections from an async target's pool."""
    pool = _extract_connection_pool(target)
    if pool is None:
        return
    connections = getattr(pool, "_connections", None)
    if not isinstance(connections, list):
        return

    closing: list[Any] = []
    lock = getattr(pool, "_optional_thread_lock", None)
    if lock is not None and hasattr(lock, "__aenter__"):
        async with lock:
            for conn in list(connections):
                _purge_connection_if_expired(conn, connections, closing)
    elif lock is not None and hasattr(lock, "__enter__"):
        with lock:
            for conn in list(connections):
                _purge_connection_if_expired(conn, connections, closing)
    else:
        for conn in list(connections):
            _purge_connection_if_expired(conn, connections, closing)

    await _aclose_connection_list(pool, closing)


atexit.register(close_shared_clients)


__all__ = [
    "aclose_expired_connections",
    "aclose_shared_clients",
    "close_expired_connections",
    "close_shared_clients",
    "get_shared_async_client",
    "get_shared_client",
]
