"""Test suite for reaching Qdrant through the Kubernetes API server."""

from __future__ import annotations

import ssl
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.k8s.service_proxy import ServiceRef, resolve_proxy_connection

CLUSTER_URL = "k8s://llm/qdrant:6333"
DIRECT_URL = "http://qdrant.internal:6333"


def _configuration(**overrides: Any) -> Any:
    """Build a Kubernetes client configuration stub."""
    configuration = MagicMock()
    configuration.host = overrides.get("host", "https://cluster.example.com:6443")
    configuration.ssl_ca_cert = None
    configuration.verify_ssl = True
    configuration.cert_file = None
    configuration.key_file = None
    configuration.api_key = overrides.get("api_key", {"authorization": "tok"})
    configuration.api_key_prefix = {"authorization": "Bearer"}
    return configuration


# =============================================================================
# Connection Resolution
# =============================================================================


def test_a_proxy_endpoint_splits_into_a_base_url_and_a_prefix() -> None:
    """Clients that take a host and a path prefix can reach a Service this way.

    That shape is what lets a k8s:// address work for a library this project does not
    control, rather than only for its own requests.
    """
    with patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()):
        connection = resolve_proxy_connection(
            ServiceRef(namespace="llm", service="qdrant", port="6333")
        )
    assert (connection.base_url, connection.prefix) == (
        "https://cluster.example.com:6443",
        "api/v1/namespaces/llm/services/qdrant:6333/proxy",
    )


def test_the_connection_carries_the_cluster_credentials() -> None:
    """The client authenticates as the kubeconfig does, with nothing new to configure."""
    with patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()):
        connection = resolve_proxy_connection(
            ServiceRef(namespace="llm", service="qdrant", port="6333")
        )
    assert connection.headers["authorization"] == "Bearer tok"
    assert isinstance(connection.ssl_context, ssl.SSLContext)


def test_the_prefix_carries_no_leading_or_trailing_slash() -> None:
    """The client joins the prefix to the base itself; a stray slash doubles up."""
    with patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()):
        prefix = resolve_proxy_connection(
            ServiceRef(namespace="llm", service="qdrant", port="6333")
        ).prefix
    assert not prefix.startswith("/") and not prefix.endswith("/")


# =============================================================================
# Client Construction
# =============================================================================


def _store(url: str) -> QdrantClient:
    """Build a store without contacting anything."""
    with patch("devops_cli.ai.rag.qdrant.validate_service_url"):
        return QdrantClient(base_url=url, api_key=None)


def test_a_cluster_address_builds_a_proxied_client() -> None:
    """The defect this fixes: a cluster address was passed through as a plain URL."""
    store = _store(CLUSTER_URL)
    with (
        patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()),
        patch("devops_cli.ai.rag.qdrant.NativeQdrantClient") as native,
    ):
        store._build_client()

    kwargs = native.call_args.kwargs
    assert (kwargs["url"], kwargs["prefix"]) == (
        "https://cluster.example.com:6443",
        "api/v1/namespaces/llm/services/qdrant:6333/proxy",
    )


def test_a_direct_address_is_unchanged() -> None:
    """Direct addressing keeps working for a Qdrant that is not in a cluster."""
    store = _store(DIRECT_URL)
    with patch("devops_cli.ai.rag.qdrant.NativeQdrantClient") as native:
        store._build_client()

    kwargs = native.call_args.kwargs
    assert (kwargs["url"], "prefix" in kwargs) == (DIRECT_URL, False)


def test_a_cluster_address_skips_host_based_egress_validation() -> None:
    """A k8s:// address names a Service, so there is no host to validate.

    What is actually dialled is the API server from the kubeconfig.
    """
    with patch("devops_cli.ai.rag.qdrant.validate_service_url") as validate:
        QdrantClient(base_url=CLUSTER_URL, api_key=None)
    validate.assert_not_called()


def test_a_direct_address_is_still_validated() -> None:
    """Skipping validation for cluster addresses must not skip it for everything."""
    with patch("devops_cli.ai.rag.qdrant.validate_service_url") as validate:
        QdrantClient(base_url=DIRECT_URL, api_key=None)
    validate.assert_called_once()


# =============================================================================
# Liveness
# =============================================================================


def test_the_liveness_check_uses_the_same_client_builder() -> None:
    """It constructed a client directly from base_url, bypassing cluster addressing.

    A store that could list its collections still reported itself unreachable.
    """
    store = _store(CLUSTER_URL)
    with patch.object(store, "_build_client") as builder:
        builder.return_value.get_collections.return_value = MagicMock(collections=[])
        assert store.is_alive(force_check=True) is True
    builder.assert_called_once()


def test_an_unreachable_store_reports_not_alive() -> None:
    """Liveness must still be able to say no."""
    store = _store(CLUSTER_URL)
    with patch.object(store, "_build_client", side_effect=RuntimeError("refused")):
        assert store.is_alive(force_check=True) is False


@pytest.mark.parametrize("url", [CLUSTER_URL, DIRECT_URL])
def test_a_store_accepts_either_address_form(url: str) -> None:
    """A configuration can move between the two without code changes."""
    with patch("devops_cli.ai.rag.qdrant.validate_service_url"):
        assert QdrantClient(base_url=url, api_key=None).base_url == url.rstrip("/")
