"""Test suite for shared HTTP clients and connection reuse."""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.config.defaults import (
    DEFAULT_HTTP_KEEPALIVE_EXPIRY_SECONDS,
    DEFAULT_HTTP_MAX_CONNECTIONS,
    DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS,
)
from devops_cli.http.broker import HttpClientBroker
from devops_cli.http.egress import EgressLevel
from devops_cli.http.pool import (
    close_shared_clients,
    get_shared_async_client,
    get_shared_client,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


@pytest.fixture(autouse=True)
def clean_registry() -> Any:
    """Clients are process-wide; a test must not inherit another's."""
    close_shared_clients()
    yield
    close_shared_clients()


# =============================================================================
# Sharing
# =============================================================================


def test_the_same_key_returns_the_same_client() -> None:
    """Reuse is the whole point: a new client means a new TCP and TLS handshake."""
    assert get_shared_client("profile-a", EgressLevel.PUBLIC) is get_shared_client(
        "profile-a", EgressLevel.PUBLIC
    )


def test_different_keys_get_different_clients() -> None:
    """Endpoints with different transport settings cannot share a connection."""
    assert get_shared_client("profile-a", EgressLevel.PUBLIC) is not get_shared_client(
        "profile-b", EgressLevel.PUBLIC
    )


def test_a_closed_client_is_rebuilt_rather_than_handed_back() -> None:
    """A client closed elsewhere is unusable; returning it would fail every later call."""
    first = get_shared_client("profile-a", EgressLevel.PUBLIC)
    first.close()
    second = get_shared_client("profile-a", EgressLevel.PUBLIC)
    assert (second is not first, second.is_closed) == (True, False)


def test_async_clients_are_shared_separately_from_sync_ones() -> None:
    """The two kinds are not interchangeable, so one key must not collide across them."""
    sync_client = get_shared_client("profile-a", EgressLevel.PUBLIC)
    async_client = get_shared_async_client("profile-a", EgressLevel.PUBLIC)
    assert isinstance(sync_client, httpx2.Client)
    assert isinstance(async_client, httpx2.AsyncClient)
    assert (sync_client is not async_client, sync_client.is_closed) == (True, False)


def test_concurrent_callers_receive_one_client() -> None:
    """Two threads racing to create the same profile must not each build a pool."""
    clients: list[httpx2.Client] = []
    barrier = threading.Barrier(8)

    def grab() -> None:
        barrier.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        clients.append(get_shared_client("racy", EgressLevel.PUBLIC))

    threads = [threading.Thread(target=grab) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert len({id(client) for client in clients}) == 1


# =============================================================================
# Configuration
# =============================================================================


def _shared_pool(**overrides: Any) -> Any:
    """The httpcore2 connection pool under one shared client, as the factory built it."""
    return get_shared_client("profile-a", EgressLevel.PRIVATE, **overrides)._transport._pool


def test_a_shared_client_negotiates_http2_at_its_level() -> None:
    """Multiplexing is what lets concurrent requests share one connection."""
    pool = _shared_pool()
    assert (pool._http2, pool._network_backend.level) == (True, EgressLevel.PRIVATE)


def test_a_shared_client_bounds_its_connections() -> None:
    """Reuse without a ceiling trades connection churn for descriptor exhaustion."""
    pool = _shared_pool()
    assert (pool._max_connections, pool._max_keepalive_connections) == (
        DEFAULT_HTTP_MAX_CONNECTIONS,
        DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS,
    )


def test_idle_connections_expire() -> None:
    """An endpoint that restarts must not leave the pool holding dead sockets."""
    assert _shared_pool()._keepalive_expiry == DEFAULT_HTTP_KEEPALIVE_EXPIRY_SECONDS


def test_a_caller_can_override_transport_settings() -> None:
    """A cluster API needs its own TLS material; the defaults must not fix that."""
    import ssl

    context = ssl.create_default_context()
    assert _shared_pool(verify=context)._ssl_context is context


def test_defaults_apply_when_not_overridden() -> None:
    """An override of one setting must not discard the rest."""
    import ssl

    client = get_shared_client("profile-a", EgressLevel.PRIVATE, verify=False)
    pool = client._transport._pool
    assert (pool._ssl_context.verify_mode, pool._http2, client.follow_redirects) == (
        ssl.CERT_NONE,
        True,
        True,
    )


# =============================================================================
# Lifecycle
# =============================================================================


def test_closing_releases_every_client() -> None:
    """A pool that outlives its process leaks sockets."""
    first = get_shared_client("profile-a", EgressLevel.PUBLIC)
    second = get_shared_client("profile-b", EgressLevel.PUBLIC)
    close_shared_clients()
    assert (first.is_closed, second.is_closed) == (True, True)


def test_closing_clears_the_registry() -> None:
    """A closed client must not be handed to the next caller."""
    first = get_shared_client("profile-a", EgressLevel.PUBLIC)
    close_shared_clients()
    assert get_shared_client("profile-a", EgressLevel.PUBLIC) is not first


def test_a_failing_close_does_not_abandon_the_rest() -> None:
    """One stuck client must not leak every other one."""
    broken = MagicMock()
    broken.close.side_effect = RuntimeError("already detached")
    from devops_cli.http import pool

    pool._CLIENTS["broken"] = broken
    healthy = get_shared_client("healthy", EgressLevel.PUBLIC)
    close_shared_clients()
    assert healthy.is_closed is True


def test_closing_an_empty_registry_is_harmless() -> None:
    """This runs at interpreter exit, where a process may have opened no clients at all."""
    from devops_cli.http import pool

    close_shared_clients()
    close_shared_clients()
    assert (close_shared_clients(), pool._CLIENTS) == (None, {})


def test_closing_is_registered_with_atexit() -> None:
    """Sockets are released when the process ends rather than left to the operating system."""
    import atexit

    from devops_cli.http import pool

    before = atexit._ncallbacks()
    atexit.unregister(pool.close_shared_clients)
    after = atexit._ncallbacks()
    atexit.register(pool.close_shared_clients)
    assert before - after == 1


def test_llm_providers_share_a_client_per_provider() -> None:
    """Inference calls were building a pool each; that is the churn this removes."""
    from devops_cli.ai.client.base import BaseLLMProviderMixin
    from devops_cli.config.settings import AIConfig

    class Provider(BaseLLMProviderMixin):
        _config = AIConfig()

    provider = Provider()
    assert provider._shared_client() is provider._shared_client()


def test_http_client_broker_close_resets_client_references() -> None:
    """Verify HttpClientBroker forgets and closes its per-level clients on close/aclose."""
    broker = HttpClientBroker()
    mock_sync = MagicMock(is_closed=False)
    mock_async = MagicMock(is_closed=False)
    mock_async.aclose = MagicMock(return_value=asyncio.sleep(0))

    broker._sync_clients[EgressLevel.PUBLIC] = mock_sync
    broker._async_clients[EgressLevel.PRIVATE] = mock_async

    broker.close()
    assert (broker._sync_clients, mock_sync.close.call_count) == ({}, 1)

    asyncio.run(broker.aclose())
    assert (broker._async_clients, mock_async.aclose.call_count) == ({}, 1)


def test_aclose_shared_clients_releases_async_pool() -> None:
    """Verify aclose_shared_clients awaits closing all active async clients."""
    from devops_cli.http import pool

    mock_client = MagicMock(is_closed=False)
    mock_client.aclose = MagicMock(return_value=asyncio.sleep(0))

    with pool._LOCK:
        pool._ASYNC_CLIENTS["test-key"] = mock_client

    asyncio.run(pool.aclose_shared_clients())

    assert (len(pool._ASYNC_CLIENTS), mock_client.aclose.call_count) == (0, 1)
