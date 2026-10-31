"""Contract suite for Qdrant client over real local mode and shared fake (#1317)."""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient as NativeQdrantClient

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.qdrant import QdrantClient, QdrantClientError, QdrantProtocol
from tests.support.fakes.qdrant import FakeQdrantClient

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def memory_qdrant_client() -> QdrantClient:
    """A real QdrantClient wrapper running over native in-memory local mode."""
    native = NativeQdrantClient(location=":memory:")
    return QdrantClient("http://localhost:6333", client=native, allow_private_network=True)


def test_qdrant_protocol_and_fake() -> None:
    fake = FakeQdrantClient()
    assert isinstance(fake, QdrantProtocol)
    assert fake.ensure_collection("c1", 4) is True
    fake.upsert_points(
        "c1",
        [{"id": "p1", "vector": [1.0, 0.0, 0.0, 0.0], "payload": {"file": "a.py"}}],
    )
    points = fake.scroll_points("c1")
    assert len(points) == 1
    assert points[0]["id"] == "p1"
    assert fake.count_points("c1", {"file": "a.py"}) == 1


def test_qdrant_fixture(qdrant: FakeQdrantClient) -> None:
    from devops_cli.ai.rag.indexer import resolve_qdrant_client

    client = resolve_qdrant_client()
    assert client is qdrant
    assert client.is_alive() is True


def test_qdrant_is_alive(memory_qdrant_client: QdrantClient) -> None:
    assert memory_qdrant_client.is_alive() is True


def test_qdrant_collections(memory_qdrant_client: QdrantClient) -> None:
    assert memory_qdrant_client.ensure_collection("devops_code", vector_size=4) is True
    assert memory_qdrant_client.ensure_collection("devops_docs", vector_size=4) is True
    colls = memory_qdrant_client.list_collections()
    assert "devops_code" in colls
    assert "devops_docs" in colls


def test_qdrant_upsert_and_search(memory_qdrant_client: QdrantClient) -> None:
    memory_qdrant_client.ensure_collection("devops_code", vector_size=4)

    p1 = {
        "id": "1",
        "vector": [1.0, 0.0, 0.0, 0.0],
        "payload": {"file_path": "src/main.py", "kind": "code"},
    }
    p2 = {
        "id": "2",
        "vector": [0.0, 1.0, 0.0, 0.0],
        "payload": {"file_path": "src/utils.py", "kind": "code"},
    }
    upserted = memory_qdrant_client.upsert_points("devops_code", [p1, p2])
    assert upserted == 2

    # Query closest to p1
    results = memory_qdrant_client.search_points(
        "devops_code", query_vector=[0.9, 0.1, 0.0, 0.0], limit=2
    )
    assert len(results) == 2
    assert results[0]["payload"]["file_path"] == "src/main.py"
    assert results[0]["score"] > results[1]["score"]

    # Filter by payload
    filtered = memory_qdrant_client.search_points(
        "devops_code",
        query_vector=[0.0, 1.0, 0.0, 0.0],
        filter_payload={"file_path": "src/utils.py"},
        limit=5,
    )
    assert len(filtered) == 1
    assert filtered[0]["payload"]["file_path"] == "src/utils.py"


def test_qdrant_count_and_scroll(memory_qdrant_client: QdrantClient) -> None:
    memory_qdrant_client.ensure_collection("devops_code", vector_size=4)
    p1 = {"id": "1", "vector": [0.1, 0.2, 0.3, 0.4], "payload": {"project": "devops"}}
    p2 = {"id": "2", "vector": [0.5, 0.6, 0.7, 0.8], "payload": {"project": "other"}}
    memory_qdrant_client.upsert_points("devops_code", [p1, p2])

    assert memory_qdrant_client.count_points("devops_code") == 2
    pts = memory_qdrant_client.scroll_points("devops_code", limit=1)
    assert len(pts) == 1


def test_qdrant_delete_points_by_files_and_project(memory_qdrant_client: QdrantClient) -> None:
    memory_qdrant_client.ensure_collection("devops_code", vector_size=4)
    p1 = {
        "id": "1",
        "vector": [0.1, 0.2, 0.3, 0.4],
        "payload": {"file_path": "src/main.py", "project_name": "devops"},
    }
    p2 = {
        "id": "2",
        "vector": [0.5, 0.6, 0.7, 0.8],
        "payload": {"file_path": "src/lib.py", "project_name": "other"},
    }
    memory_qdrant_client.upsert_points("devops_code", [p1, p2])

    assert memory_qdrant_client.delete_points_by_files("devops_code", ["src/main.py"]) is True
    assert memory_qdrant_client.count_points("devops_code") == 1

    assert memory_qdrant_client.delete_points_by_project("devops_code", "other") is True
    assert memory_qdrant_client.count_points("devops_code") == 0


def test_qdrant_delete_collection(memory_qdrant_client: QdrantClient) -> None:
    memory_qdrant_client.ensure_collection("temp_col", vector_size=4)
    assert memory_qdrant_client.delete_collection("temp_col") is True
    assert "temp_col" not in memory_qdrant_client.list_collections()


def test_qdrant_upsert_dimension_mismatch_fails_without_recreating(
    memory_qdrant_client: QdrantClient,
) -> None:
    memory_qdrant_client.ensure_collection("mismatch_col", vector_size=4)
    points = [{"id": "1", "vector": [0.1] * 8, "payload": {"file_path": "src/main.py"}}]
    with pytest.raises(EmbeddingsError) as exc_info:
        memory_qdrant_client.upsert_points("mismatch_col", points)

    assert exc_info.value.is_transient is False
    assert "4" in str(exc_info.value)
    assert "8" in str(exc_info.value)


def test_qdrant_search_dimension_mismatch_raises_permanent_error(
    memory_qdrant_client: QdrantClient,
) -> None:
    memory_qdrant_client.ensure_collection("search_mismatch_col", vector_size=4)
    with pytest.raises(EmbeddingsError) as exc_info:
        memory_qdrant_client.search_points("search_mismatch_col", query_vector=[0.1] * 8, limit=5)

    assert exc_info.value.is_transient is False


def test_qdrant_unreachable_server_raises_qdrant_client_error(refusing_port: int) -> None:
    native = NativeQdrantClient(url=f"http://127.0.0.1:{refusing_port}", timeout=0.01)
    client = QdrantClient(
        f"http://127.0.0.1:{refusing_port}", client=native, timeout=0.01, allow_private_network=True
    )
    with pytest.raises(QdrantClientError) as raised:
        client.list_collections()
    assert raised.value.error_code == "DEVOPS_CLI_ERROR"
