"""Qdrant requests name their server by host and port in spans, and count their retries (#975)."""

from __future__ import annotations

from typing import Any

import pytest
from qdrant_client import QdrantClient as NativeQdrantClient

from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.telemetry.instruments import QDRANT_RETRIES_TOTAL
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.qdrant import serving_qdrant

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture(autouse=True)
def _mock_example_com_dns(dns: DnsFake) -> None:
    dns.add("example.com", PUBLIC_ADDRESS)


def _upsert_span_attributes(url: str, otlp: FakeCollector) -> dict[str, Any]:
    """Upsert one point through a real client for `url` and return the attributes of the span.

    The client runs over the native client's in-memory mode.
    """
    client = QdrantClient(
        url, client=NativeQdrantClient(location=":memory:"), allow_private_network=True, timeout=5.0
    )
    client.ensure_collection("devops_code", 4)

    client.upsert_points("devops_code", [{"id": "1", "vector": [0.1] * 4, "payload": {}}])

    (span,) = (span for span in otlp.spans if span.name == "qdrant.upsert_points")
    return span.attributes


@pytest.mark.filterwarnings("ignore:Payload indexes have no effect in the local Qdrant")
@pytest.mark.parametrize(
    ("url", "server"),
    [
        ("http://example.com:6333", ("example.com", 6333)),
        ("http://user:secret@example.com:6333/prefix/path", ("example.com", 6333)),
        ("https://token@example.com", ("example.com", 443)),
        ("k8s://devops/qdrant:6333", ("qdrant.devops", 6333)),
        ("k8s+https://user:secret@devops/qdrant:6333/path?q=secret", ("qdrant.devops", 6333)),
        ("k8s://devops/qdrant:http", ("qdrant.devops", None)),
    ],
    ids=["port", "userinfo-and-path", "user-only-default-port", "k8s", "k8s-userinfo", "k8s-named"],
)
def test_upsert_span_names_the_server_by_host_and_port(
    otlp: FakeCollector, url: str, server: tuple[str, int | None]
) -> None:
    attributes = _upsert_span_attributes(url, otlp)

    port = attributes.get("server.port")
    assert (attributes["server.address"], None if port is None else int(port)) == server
    assert not [
        value
        for value in attributes.values()
        if any(text in str(value) for text in ("secret", "token", "user", "/prefix", "://"))
    ]


@pytest.mark.filterwarnings("ignore:Api key is used with an insecure connection")
def test_a_retried_request_is_counted_by_the_error_behind_it(
    otlp: FakeCollector, clock: ClockFake
) -> None:
    """Each retry counts once, by operation and the transport error qdrant_client wrapped.

    qdrant_client raises every transport error as a `ResponseHandlingException`, so labelling
    by that class gave every transient error the same `error_type`. The real client sends to a
    loopback server that cuts the first connection and then answers.
    """
    point = {"id": 7, "version": 0, "score": 0.9, "payload": {"file_path": "a.py"}}
    with serving_qdrant(points=[point]) as served:
        served.drop_connections = 1
        client = QdrantClient(served.url, api_key="test-key", timeout=5.0)

        hits = client.search_points("code", [1.0, 0.0], limit=3)

    assert (hits, otlp.points(QDRANT_RETRIES_TOTAL.name), len(served.requests)) == (
        [{"id": 7, "score": 0.9, "payload": {"file_path": "a.py"}}],
        [({"operation": "search_points", "error_type": "RemoteProtocolError"}, 1.0)],
        2,
    )


@pytest.mark.filterwarnings("ignore:Api key is used with an insecure connection")
def test_a_request_that_keeps_failing_backs_off_longer_each_time_before_it_succeeds(
    clock: ClockFake,
) -> None:
    with serving_qdrant(collections=["devops_code"]) as served:
        served.drop_connections = 2
        client = QdrantClient(served.url, api_key="test-key", timeout=5.0)

        collections = client.list_collections()

    assert (collections, clock.waits, len(served.requests)) == (["devops_code"], [0.5, 1.0], 3)
