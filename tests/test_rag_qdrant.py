"""Unit tests for Qdrant vector database client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.qdrant import QdrantClient, QdrantClientError

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_qdrant_is_alive() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.get_collections.return_value = MagicMock(collections=[])
    client._client = mock_native
    client._build_client = lambda: mock_native

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
    client._build_client = lambda: mock_native

    colls = client.list_collections()
    assert colls == ["devops_code", "devops_docs"]


def test_qdrant_ensure_collection() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.get_collection.side_effect = Exception("Collection not found")
    client._client = mock_native
    client._build_client = lambda: mock_native

    assert client.ensure_collection("devops_code", vector_size=384) is True
    mock_native.create_collection.assert_called_once()


def test_qdrant_upsert_and_search() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    info = MagicMock()
    info.config.params.vectors.size = 384
    info.points_count = 1
    info.status = "green"
    mock_native.get_collection.return_value = info
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
    client._build_client = lambda: mock_native

    points = [{"id": "1", "vector": [0.1] * 384, "payload": {"file_path": "src/main.py"}}]
    upserted = client.upsert_points("devops_code", points)
    assert upserted == 1

    results = client.search_points("devops_code", query_vector=[0.1] * 384, limit=5)
    assert len(results) == 1
    assert results[0]["payload"]["file_path"] == "src/main.py"


def test_qdrant_upsert_dimension_mismatch_fails_without_recreating() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    # Simulate existing collection with 768 dims
    info = MagicMock()
    info.config.params.vectors.size = 768
    info.points_count = 100
    info.status = "green"
    mock_native.get_collection.return_value = info
    client._client = mock_native
    client._build_client = lambda: mock_native

    # Upsert with 1024 dims
    points = [{"id": "1", "vector": [0.1] * 1024, "payload": {"file_path": "src/main.py"}}]
    with pytest.raises(EmbeddingsError) as exc_info:
        client.upsert_points("devops_code", points)

    assert exc_info.value.is_transient is False
    assert "768" in str(exc_info.value)
    assert "1024" in str(exc_info.value)
    mock_native.delete_collection.assert_not_called()
    mock_native.create_collection.assert_not_called()


def test_qdrant_search_dimension_mismatch_raises_permanent_error() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.query_points.side_effect = Exception(
        "Vector dimension error: expected dim: 768, got 1024"
    )
    client._client = mock_native
    client._build_client = lambda: mock_native

    with pytest.raises(EmbeddingsError) as exc_info:
        client.search_points("devops_code", query_vector=[0.1] * 1024, limit=5)

    assert exc_info.value.is_transient is False
    assert "768" in str(exc_info.value)
    assert "1024" in str(exc_info.value)
    mock_native.delete_collection.assert_not_called()
    mock_native.create_collection.assert_not_called()


def test_qdrant_delete_collection() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.delete_collection.return_value = True
    client._client = mock_native
    client._build_client = lambda: mock_native

    assert client.delete_collection("devops_code") is True


def test_qdrant_delete_points_by_files() -> None:
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.delete.return_value = True
    client._client = mock_native
    client._build_client = lambda: mock_native

    # Empty list returns True with no calls
    assert client.delete_points_by_files("devops_code", []) is True
    assert mock_native.delete.call_count == 0

    # Single file via delete_points_by_files
    assert (
        client.delete_points_by_files("devops_code", ["src/main.py"], project_name="devops") is True
    )
    assert mock_native.delete.call_count == 1
    assert mock_native.delete.call_args.kwargs.get("wait") is True

    # Delete points by project
    assert client.delete_points_by_project("devops_code", "devops") is True
    assert mock_native.delete.call_count == 2
    assert mock_native.delete.call_args.kwargs.get("wait") is True

    # 150 files should be split into 2 batches (100 + 50)
    assert (
        client.delete_points_by_files("devops_code", [f"file_{i}.py" for i in range(150)]) is True
    )
    assert mock_native.delete.call_count == 4

    # Deletes raise QdrantClientError on failure
    mock_native.delete.side_effect = RuntimeError("network timeout")
    with pytest.raises(QdrantClientError):
        client.delete_points_by_files("devops_code", ["src/main.py"])
    with pytest.raises(QdrantClientError):
        client.delete_points_by_project("devops_code", "devops")


def test_qdrant_build_client_port_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from typing import Any

    captured_calls: list[tuple[str, int | None]] = []

    def mock_native_init(url: str, port: int | None = None, **kwargs: Any) -> MagicMock:
        captured_calls.append((url, port))
        return MagicMock()

    monkeypatch.setattr("devops_cli.ai.rag.qdrant.NativeQdrantClient", mock_native_init)

    c1 = QdrantClient("https://example.com", allow_private_network=True)
    _ = c1._build_client()

    c2 = QdrantClient("http://localhost:6333", allow_private_network=True)
    _ = c2._build_client()

    assert captured_calls == [
        ("https://example.com", None),
        ("http://localhost:6333", 6333),
    ]
