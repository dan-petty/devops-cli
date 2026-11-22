"""A Qdrant request gets a retry after a rate-limit or gateway answer, and no retry after another error status."""

from __future__ import annotations

import pytest

from devops_cli.ai.rag.qdrant import QdrantClient, QdrantClientError
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.qdrant import ServedQdrant, serving_qdrant

pytestmark = pytest.mark.filterwarnings("ignore:Api key is used with an insecure connection")

COLLECTION = "devops_docs"
POINT = {"id": 1, "vector": [1.0, 0.0], "payload": {"file_path": "docs/README.md"}}


def _upsert_requests(served: ServedQdrant) -> list[tuple[str, str]]:
    """The method and the path of each upsert request that the server got."""
    return [
        (method, path.split("?")[0])
        for method, path, _ in served.requests
        if path.split("?")[0].endswith("/points")
    ]


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_a_gateway_or_rate_limit_answer_gets_a_retry(clock: ClockFake, status: int) -> None:
    """The proxy in front of Qdrant answers one upsert with an HTML error page (#6757)."""
    with serving_qdrant() as served:
        client = QdrantClient(served.url, api_key="test-key", timeout=5.0)
        client.ensure_collection(COLLECTION, 2)
        served.error_statuses = [status]

        upserted = client.upsert_points(COLLECTION, [POINT])

    assert (upserted, clock.waits, _upsert_requests(served)) == (
        1,
        [0.5],
        [("PUT", f"/collections/{COLLECTION}/points")] * 2,
    )


@pytest.mark.parametrize("status", [400, 401, 403, 404, 408, 500])
def test_another_error_status_ends_the_operation_at_once(clock: ClockFake, status: int) -> None:
    """The status alone decides: the word "Timeout" in the reason phrase of a 408 gets no retry."""
    with serving_qdrant() as served:
        client = QdrantClient(served.url, api_key="test-key", timeout=5.0)
        client.ensure_collection(COLLECTION, 2)
        served.error_statuses = [status]

        with pytest.raises(QdrantClientError, match=f"Unexpected Response: {status} "):
            client.upsert_points(COLLECTION, [POINT])

    assert (clock.waits, _upsert_requests(served)) == (
        [],
        [("PUT", f"/collections/{COLLECTION}/points")],
    )
