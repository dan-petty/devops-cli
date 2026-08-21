"""Unit tests for Qdrant vector database client."""

from __future__ import annotations

from unittest.mock import MagicMock

from devops_cli.ai.rag.qdrant import QdrantClient


def test_qdrant_is_alive() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.get_collections.return_value = MagicMock(collections=[])
    client._client = mock_native

    assert client.is_alive() is True


def test_qdrant_list_collections() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    c1 = MagicMock()
    c1.name = "devops_code"
    c2 = MagicMock()
    c2.name = "devops_docs"
    mock_native.get_collections.return_value = MagicMock(collections=[c1, c2])
    client._client = mock_native

    colls = client.list_collections()
    assert colls == ["devops_code", "devops_docs"]


def test_qdrant_ensure_collection() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.get_collection.side_effect = Exception("Collection not found")
    client._client = mock_native

    assert client.ensure_collection("devops_code", vector_size=384) is True
    mock_native.create_collection.assert_called_once()


def test_qdrant_upsert_and_search() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    hit = MagicMock(
        id="1",
        score=0.89,
        payload={
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 10,
            "content": "def main(): pass",
            "language": "python",
            "doc_type": "code",
        },
    )
    mock_native.query_points.return_value = MagicMock(points=[hit])
    client._client = mock_native

    points = [{"id": "1", "vector": [0.1] * 384, "payload": {"file_path": "src/main.py"}}]
    upserted = client.upsert_points("devops_code", points)
    assert upserted == 1

    results = client.search_points("devops_code", query_vector=[0.1] * 384, limit=5)
    assert len(results) == 1
    assert results[0]["payload"]["file_path"] == "src/main.py"


def test_qdrant_delete_collection() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.delete_collection.return_value = True
    client._client = mock_native

    assert client.delete_collection("devops_code") is True
