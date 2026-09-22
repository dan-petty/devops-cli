"""Test suite for shared HTTP clients and connection reuse."""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest

from devops_cli.config.defaults import (
    DEFAULT_HTTP_KEEPALIVE_EXPIRY_SECONDS,
    DEFAULT_HTTP_MAX_CONNECTIONS,
    DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS,
)
from devops_cli.http.pool import (
    close_shared_clients,
    connection_limits,
    get_shared_async_client,
    get_shared_client,
)


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
    """Reuse is the whole point: a new client means a new TCP and TLS handshake.

    Measured against a remote endpoint: 247 ms per request building a client per call,
    against 61 ms once the connection is reused.
    """
    assert get_shared_client("profile-a") is get_shared_client("profile-a")


def test_different_keys_get_different_clients() -> None:
    """Endpoints with different transport settings cannot share a connection."""
    assert get_shared_client("profile-a") is not get_shared_client("profile-b")


def test_a_closed_client_is_rebuilt_rather_than_handed_back() -> None:
    """A client closed elsewhere is unusable; returning it would fail every later call."""
    first = get_shared_client("profile-a")
    first.close()
    second = get_shared_client("profile-a")
    assert (second is not first, second.is_closed) == (True, False)


def test_async_clients_are_shared_separately_from_sync_ones() -> None:
    """The two kinds are not interchangeable, so one key must not collide across them."""
    sync_client = get_shared_client("profile-a")
    async_client = get_shared_async_client("profile-a")
    assert isinstance(sync_client, httpx2.Client)
    assert isinstance(async_client, httpx2.AsyncClient)


def test_concurrent_callers_receive_one_client() -> None:
    """Two threads racing to create the same profile must not each build a pool."""
    clients: list[httpx2.Client] = []
    barrier = threading.Barrier(8)

    def grab() -> None:
        barrier.wait(timeout=10)
        clients.append(get_shared_client("racy"))

    threads = [threading.Thread(target=grab) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len({id(client) for client in clients}) == 1


# =============================================================================
# Configuration
# =============================================================================


def test_a_shared_client_negotiates_http2() -> None:
    """Multiplexing is what lets concurrent requests share one connection."""
    with patch("httpx2.Client") as constructor:
        get_shared_client("profile-a")
    assert constructor.call_args.kwargs["http2"] is True


def test_a_shared_client_bounds_its_connections() -> None:
    """Reuse without a ceiling trades connection churn for descriptor exhaustion.

    That is the failure this pooling exists to prevent, not to cause.
    """
    with patch("httpx2.Client") as constructor:
        get_shared_client("profile-a")
    limits = constructor.call_args.kwargs["limits"]
    assert (limits.max_connections, limits.max_keepalive_connections) == (
        DEFAULT_HTTP_MAX_CONNECTIONS,
        DEFAULT_HTTP_MAX_KEEPALIVE_CONNECTIONS,
    )


def test_idle_connections_expire() -> None:
    """An endpoint that restarts must not leave the pool holding dead sockets."""
    assert connection_limits().keepalive_expiry == DEFAULT_HTTP_KEEPALIVE_EXPIRY_SECONDS


def test_a_caller_can_override_transport_settings() -> None:
    """A cluster API needs its own TLS material; the defaults must not fix that."""
    sentinel = object()
    with patch("httpx2.Client") as constructor:
        get_shared_client("profile-a", verify=sentinel)
    assert constructor.call_args.kwargs["verify"] is sentinel


def test_defaults_apply_when_not_overridden() -> None:
    """An override of one setting must not discard the rest."""
    with patch("httpx2.Client") as constructor:
        get_shared_client("profile-a", verify=False)
    kwargs = constructor.call_args.kwargs
    assert (kwargs["http2"], kwargs["follow_redirects"]) == (True, True)


# =============================================================================
# Lifecycle
# =============================================================================


def test_closing_releases_every_client() -> None:
    """A pool that outlives its process leaks sockets."""
    first = get_shared_client("profile-a")
    second = get_shared_client("profile-b")
    close_shared_clients()
    assert (first.is_closed, second.is_closed) == (True, True)


def test_closing_clears_the_registry() -> None:
    """A closed client must not be handed to the next caller."""
    first = get_shared_client("profile-a")
    close_shared_clients()
    assert get_shared_client("profile-a") is not first


def test_a_failing_close_does_not_abandon_the_rest() -> None:
    """One stuck client must not leak every other one."""
    broken = MagicMock()
    broken.close.side_effect = RuntimeError("already detached")
    from devops_cli.http import pool

    pool._CLIENTS["broken"] = broken
    healthy = get_shared_client("healthy")
    close_shared_clients()
    assert healthy.is_closed is True


def test_closing_an_empty_registry_is_harmless() -> None:
    """This runs at interpreter exit, where a process may have opened no clients at all.

    Raising there would surface as a confusing traceback after the command's real work had
    already finished.
    """
    close_shared_clients()
    close_shared_clients()


def test_closing_is_registered_with_atexit() -> None:
    """Sockets are released when the process ends rather than left to the operating system.

    `atexit.unregister` is a no-op for a function that was never registered, so the callback
    count dropping by one proves the module registered it.
    """
    import atexit

    from devops_cli.http import pool

    before = atexit._ncallbacks()
    atexit.unregister(pool.close_shared_clients)
    after = atexit._ncallbacks()
    atexit.register(pool.close_shared_clients)
    assert before - after == 1


# =============================================================================
# Call Sites
# =============================================================================


def test_the_cluster_proxy_reuses_one_client_per_api_server() -> None:
    """Every dashboard refresh queries the cluster; a client per call renegotiates TLS."""
    from devops_cli.k8s import service_http

    target = MagicMock()
    target.url = "https://cluster.example.com:6443/api/v1/namespaces/x/services/y:80/proxy/z"
    target.headers = {"authorization": "Bearer t"}
    target.ssl_context = object()

    client = MagicMock()
    client.get.return_value = MagicMock(text='{"status": "success"}')

    with (
        patch.object(service_http, "resolve_proxy_target", return_value=target),
        patch.object(service_http, "get_shared_client", return_value=client) as shared,
    ):
        service_http.get_json("k8s://x/y:80", "z")
        service_http.get_json("k8s://x/y:80", "z")

    keys = {call.args[0] for call in shared.call_args_list}
    assert len(keys) == 1


def test_the_proxy_client_key_ignores_the_request_path() -> None:
    """Every path on one host shares a connection.

    Keying on the path would build a client per endpoint and reinstate the churn.
    """
    from devops_cli.k8s.service_http import _transport_key

    assert _transport_key("https://host:6443/a/b?q=1") == _transport_key("https://host:6443/c")


def test_the_proxy_client_key_separates_hosts() -> None:
    """Two clusters must not share a connection."""
    from devops_cli.k8s.service_http import _transport_key

    assert _transport_key("https://a:6443/x") != _transport_key("https://b:6443/x")


def test_llm_providers_share_a_client_per_provider() -> None:
    """Inference calls were building a pool each; that is the churn this removes."""
    from devops_cli.ai.client.base import BaseLLMProviderMixin

    class Provider(BaseLLMProviderMixin):
        pass

    provider = Provider()
    assert provider._shared_client() is provider._shared_client()


# =============================================================================
# Per-Request Rebuilding
# =============================================================================


def test_the_client_configuration_is_cached_between_requests() -> None:
    """Reloading the kubeconfig per call cost 24 ms of a 32 ms proxied request.

    More than the HTTP itself, and the dashboard issues one per panel per refresh.
    """
    from devops_cli.k8s import service_proxy

    service_proxy.reset_configuration_cache()
    with (
        patch("devops_cli.k8s.service_proxy.resolve_context", return_value="ctx"),
        patch("devops_cli.k8s.service_proxy._kubeconfig_mtime", return_value=1.0),
        patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(client=MagicMock(), config=MagicMock())},
        ) as _,
    ):
        from kubernetes import config as loader  # type: ignore[import-untyped]

        service_proxy._kube_configuration()
        service_proxy._kube_configuration()
        calls = loader.load_kube_config.call_count + loader.load_incluster_config.call_count
    service_proxy.reset_configuration_cache()
    assert calls <= 1


def test_an_edited_kubeconfig_invalidates_the_cached_configuration() -> None:
    """Credentials must not be held after the file that supplied them changes."""
    from devops_cli.k8s import service_proxy

    service_proxy.reset_configuration_cache()
    mtimes = iter([1.0, 2.0])
    with (
        patch("devops_cli.k8s.service_proxy.resolve_context", return_value="ctx"),
        patch("devops_cli.k8s.service_proxy._kubeconfig_mtime", side_effect=lambda: next(mtimes)),
        patch.dict(
            "sys.modules", {"kubernetes": MagicMock(client=MagicMock(), config=MagicMock())}
        ),
    ):
        from kubernetes import config as loader  # type: ignore[import-untyped]

        service_proxy._kube_configuration()
        service_proxy._kube_configuration()
        reloaded = loader.load_kube_config.call_count + loader.load_incluster_config.call_count
    service_proxy.reset_configuration_cache()
    assert reloaded == 2


def test_the_configured_context_is_cached_between_calls() -> None:
    """Loading settings cost 10.8 ms and this is consulted on every cluster request."""
    from devops_cli.k8s import context as context_module

    context_module.reset_context_cache()
    with (
        patch.object(context_module, "_config_signature", return_value=1.0),
        patch("devops_cli.config.settings.load_settings") as loader,
    ):
        loader.return_value.k8s.context = "homelab-k3s"
        first = context_module.configured_context()
        second = context_module.configured_context()
    context_module.reset_context_cache()
    assert (first, second, loader.call_count) == ("homelab-k3s", "homelab-k3s", 1)


def test_an_edited_configuration_changes_the_context() -> None:
    """A long-running process must follow a context switch, not pin the startup value.

    That property is why this was uncached originally; caching on the file's modification
    time keeps it while removing the per-call reload.
    """
    from devops_cli.k8s import context as context_module

    context_module.reset_context_cache()
    signatures = iter([1.0, 2.0])
    with (
        patch.object(context_module, "_config_signature", side_effect=lambda: next(signatures)),
        patch("devops_cli.config.settings.load_settings") as loader,
    ):
        first = MagicMock()
        first.k8s.context = "homelab-k3s"
        second = MagicMock()
        second.k8s.context = "staging"
        loader.side_effect = [first, second]
        before = context_module.configured_context()
        after = context_module.configured_context()
    context_module.reset_context_cache()
    assert (before, after) == ("homelab-k3s", "staging")
