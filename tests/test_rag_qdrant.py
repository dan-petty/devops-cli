"""Unit tests for Qdrant vector database HTTP client."""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.ai.rag.qdrant import QdrantClient


def test_qdrant_is_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, headers: dict[str, str] | None = None) -> httpx2.Response:
        return httpx2.Response(200, json={"status": "ok"})

    monkeypatch.setattr(httpx2.Client, "get", lambda self, url, **kwargs: fake_get(url))
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    assert client.is_alive() is True


def test_qdrant_list_collections(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, headers: dict[str, str] | None = None) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={"result": {"collections": [{"name": "devops_code"}, {"name": "devops_docs"}]}},
        )

    monkeypatch.setattr(httpx2.Client, "get", lambda self, url, **kwargs: fake_get(url))
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    colls = client.list_collections()
    assert colls == ["devops_code", "devops_docs"]


def test_qdrant_ensure_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, headers: dict[str, str] | None = None) -> httpx2.Response:
        return httpx2.Response(404, json={})

    def fake_put(
        url: str, headers: dict[str, str] | None = None, json: dict | None = None
    ) -> httpx2.Response:
        return httpx2.Response(200, json={"result": True, "status": "ok"})

    monkeypatch.setattr(httpx2.Client, "get", lambda self, url, **kwargs: fake_get(url))
    monkeypatch.setattr(httpx2.Client, "put", lambda self, url, **kwargs: fake_put(url, **kwargs))

    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    assert client.ensure_collection("devops_code", vector_size=384) is True


def test_qdrant_upsert_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_put(
        url: str, headers: dict[str, str] | None = None, json: dict | None = None
    ) -> httpx2.Response:
        return httpx2.Response(200, json={"status": "ok"})

    def fake_post(
        url: str, headers: dict[str, str] | None = None, json: dict | None = None
    ) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "result": [
                    {
                        "id": "1",
                        "score": 0.89,
                        "payload": {
                            "file_path": "src/main.py",
                            "start_line": 1,
                            "end_line": 10,
                            "content": "def main(): pass",
                            "language": "python",
                            "doc_type": "code",
                        },
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx2.Client, "put", lambda self, url, **kwargs: fake_put(url, **kwargs))
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: fake_post(url, **kwargs))

    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    points = [{"id": "1", "vector": [0.1] * 384, "payload": {"file_path": "src/main.py"}}]
    upserted = client.upsert_points("devops_code", points)
    assert upserted == 1

    results = client.search_points("devops_code", query_vector=[0.1] * 384, limit=5)
    assert len(results) == 1
    assert results[0]["payload"]["file_path"] == "src/main.py"


def test_qdrant_delete_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_delete(url: str, headers: dict[str, str] | None = None) -> httpx2.Response:
        return httpx2.Response(200, json={"result": True})

    monkeypatch.setattr(httpx2.Client, "delete", lambda self, url, **kwargs: fake_delete(url))
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    assert client.delete_collection("devops_code") is True
