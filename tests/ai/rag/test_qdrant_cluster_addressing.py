"""Reaching Qdrant through the Kubernetes API server, over the cluster fake and a loopback server."""

from __future__ import annotations

import ssl

import httpcore2
import pytest

from devops_cli.ai.rag.qdrant import QdrantClient, create_native_qdrant_client
from devops_cli.k8s.service_proxy import ServiceRef, resolve_proxy_connection
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.qdrant import serving_qdrant

pytestmark = pytest.mark.usefixtures("keyring_store")

CLUSTER_URL = "k8s://llm/qdrant:6333"
DIRECT_URL = "http://qdrant.example.com:6333"
PROXY_PREFIX = "api/v1/namespaces/llm/services/qdrant:6333/proxy"
SERVICE = ServiceRef(namespace="llm", service="qdrant", port="6333")


@pytest.fixture(autouse=True)
def _credentials(cluster: FakeCluster) -> None:
    cluster.configuration.host = "https://cluster.example.com:6443"
    cluster.configuration.api_key = {"authorization": "tok"}
    cluster.configuration.api_key_prefix = {"authorization": "Bearer"}


def test_a_proxy_endpoint_splits_into_a_base_url_and_a_prefix() -> None:
    """Clients that take a host and a path prefix can reach a Service this way.

    That shape is what lets a k8s:// address work for a library this project does not
    control, rather than only for its own requests.
    """
    connection = resolve_proxy_connection(SERVICE)

    assert (connection.base_url, connection.prefix) == (
        "https://cluster.example.com:6443",
        PROXY_PREFIX,
    )


def test_the_connection_carries_the_cluster_credentials() -> None:
    """The client authenticates as the kubeconfig does, with nothing new to configure."""
    connection = resolve_proxy_connection(SERVICE)

    assert connection.headers["authorization"] == "Bearer tok"
    assert isinstance(connection.ssl_context, ssl.SSLContext)


def test_the_prefix_carries_no_leading_or_trailing_slash() -> None:
    """The client joins the prefix to the base itself; a stray slash doubles up."""
    prefix = resolve_proxy_connection(SERVICE).prefix

    assert not prefix.startswith("/")
    assert not prefix.endswith("/")


def test_a_cluster_address_builds_a_client_for_the_proxy_endpoint(cluster: FakeCluster) -> None:
    """The defect this fixes: a cluster address was passed through as a plain URL."""
    with serving_qdrant(prefix=f"/{PROXY_PREFIX}", collections=["devops_code"]) as served:
        cluster.configuration.host = served.url

        create_native_qdrant_client(CLUSTER_URL).get_collections()

    assert [(method, path) for method, path, _ in served.requests] == [
        ("GET", f"/{PROXY_PREFIX}/collections")
    ]


def test_a_direct_address_is_unchanged() -> None:
    """Direct addressing keeps working for a Qdrant that is not in a cluster."""
    with serving_qdrant(collections=["devops_code"]) as served:
        create_native_qdrant_client(served.url).get_collections()

    assert [(method, path) for method, path, _ in served.requests] == [("GET", "/collections")]


def test_a_cluster_address_needs_no_host_validation(dns: DnsFake) -> None:
    """A k8s:// address names a Service, so there is no host to validate.

    What is dialled is the API server from the kubeconfig, and no name is looked up.
    """
    store = QdrantClient(base_url=CLUSTER_URL, api_key=None)

    assert (store.base_url, dns.lookups) == (CLUSTER_URL, [])


def test_a_direct_address_is_still_validated(dns: DnsFake) -> None:
    """Skipping validation for cluster addresses must not skip it for everything."""
    with pytest.raises(httpcore2.ConnectError, match="Name or service not known"):
        QdrantClient(base_url=DIRECT_URL, api_key=None)

    dns.add("qdrant.example.com", PUBLIC_ADDRESS)
    assert QdrantClient(base_url=DIRECT_URL, api_key=None).base_url == DIRECT_URL


@pytest.mark.parametrize("url", [CLUSTER_URL, "http://127.0.0.1:6333"])
def test_a_store_accepts_either_address_form(url: str) -> None:
    """A configuration can move between the two without code changes."""
    assert QdrantClient(base_url=url, api_key=None).base_url == url


def test_the_liveness_check_reaches_a_store_through_the_proxy(cluster: FakeCluster) -> None:
    """It once built a client straight from the address, bypassing cluster addressing.

    A store that could list its collections still reported itself unreachable.
    """
    with serving_qdrant(prefix=f"/{PROXY_PREFIX}", collections=["devops_code"]) as served:
        cluster.configuration.host = served.url
        store = QdrantClient(base_url=CLUSTER_URL, api_key=None)

        alive = store.is_alive(force_check=True)

    assert (alive, [(method, path) for method, path, _ in served.requests]) == (
        True,
        [("GET", f"/{PROXY_PREFIX}/collections")],
    )
    assert served.headers_of_requests()[0]["authorization"] == "Bearer tok"


def test_an_unreachable_store_reports_not_alive(cluster: FakeCluster, refusing_port: int) -> None:
    """Liveness must still be able to say no."""
    cluster.configuration.host = f"http://127.0.0.1:{refusing_port}"

    assert QdrantClient(base_url=CLUSTER_URL, api_key=None).is_alive(force_check=True) is False
