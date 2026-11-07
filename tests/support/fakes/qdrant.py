"""In-memory Qdrant fake for tests (#1317).

Provides an in-memory vector store matching the QdrantProtocol seam, supporting
upserts, cosine search, payload filtering, and simulated unreachable / refusing modes.
"""

from __future__ import annotations

import json
import math
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from devops_cli.ai.kb import knowledge_base_digest
from devops_cli.ai.rag.qdrant import QdrantClientError, QdrantProtocol
from devops_cli.config.constants import CONST_RAG_KB_PROJECT


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _matches_fake_filter(payload: dict[str, Any], filter_payload: dict[str, Any] | None) -> bool:
    if not filter_payload:
        return True
    must_not = filter_payload.get("must_not")
    for k, v in filter_payload.items():
        if k == "must_not":
            continue
        if payload.get(k) != v:
            return False
    if must_not and isinstance(must_not, dict):
        for nk, nv in must_not.items():
            if payload.get(nk) == nv:
                return False
    return True


class FakeQdrantClient(QdrantProtocol):
    """In-memory Qdrant store supporting cosine similarity and payload filters."""

    def __init__(self, *, refusing: bool = False) -> None:
        self.refusing = refusing
        # What `WorkspaceIndexer` reads of a client it is given: the key and the address.
        self.api_key: str | None = None
        self.base_url = "http://example.com:6333"
        self.collections: dict[str, list[dict[str, Any]]] = {}
        self.vector_sizes: dict[str, int] = {}
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        # Called with the collection name at the start of each search, so a test can hold or
        # fail one collection's search, as a slow or failing server does.
        self.on_search: Callable[[str], None] | None = None
        # The operations that raise `QdrantClientError`, as a server that refuses them does.
        self.failing_operations: set[str] = set()

    def fail_operation(self, *names: str) -> None:
        """Make each later call of the operations `names` raise `QdrantClientError`."""
        self.failing_operations.update(names)

    def recover(self) -> None:
        """Make every operation answer again."""
        self.failing_operations.clear()

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))
        if name in self.failing_operations:
            raise QdrantClientError(f"Simulated {name} failure")

    def is_alive(self, *, force_check: bool = False) -> bool:
        self._record("is_alive", force_check=force_check)
        return not self.refusing

    def ensure_collection(
        self,
        name: str,
        vector_size: int,
        distance: str = "Cosine",
        enable_quantization: bool | None = None,
    ) -> bool:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record(
            "ensure_collection",
            name,
            vector_size,
            distance=distance,
            enable_quantization=enable_quantization,
        )
        if name not in self.collections:
            self.collections[name] = []
        self.vector_sizes[name] = vector_size
        return True

    def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "Cosine",
        enable_quantization: bool | None = None,
    ) -> bool:
        return self.ensure_collection(
            name=collection_name,
            vector_size=vector_size,
            distance=distance,
            enable_quantization=enable_quantization,
        )

    def get_collection_info(self, name: str) -> dict[str, Any]:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record("get_collection_info", name)
        if name in self.collections:
            size = self.vector_sizes.get(name, 4)
            return {
                "points_count": len(self.collections[name]),
                "vector_size": size,
                "config": {"params": {"vectors": {"size": size}}},
            }
        return {}

    def list_collections(self) -> list[str]:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record("list_collections")
        return list(self.collections.keys())

    def delete_collection(self, name: str) -> bool:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record("delete_collection", name)
        self.collections.pop(name, None)
        self.vector_sizes.pop(name, None)
        return True

    def upsert_points(
        self,
        name: str,
        points: list[dict[str, Any]],
        batch_size: int = 64,
    ) -> int:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record("upsert_points", name, points, batch_size=batch_size)
        if name not in self.collections:
            self.collections[name] = []
        # Update existing point if ID matches, else append
        existing_by_id = {p.get("id"): idx for idx, p in enumerate(self.collections[name])}
        for point in points:
            pid = point.get("id")
            if pid in existing_by_id:
                self.collections[name][existing_by_id[pid]] = point
            else:
                existing_by_id[pid] = len(self.collections[name])
                self.collections[name].append(point)
        return len(points)

    def search_points(
        self,
        name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record(
            "search_points",
            name,
            query_vector,
            limit=limit,
            filter_payload=filter_payload,
            score_threshold=score_threshold,
        )
        if self.on_search is not None:
            self.on_search(name)
        points = self.collections.get(name, [])
        scored: list[dict[str, Any]] = []
        for p in points:
            payload = p.get("payload", {})
            if not _matches_fake_filter(payload, filter_payload):
                continue
            sim = _cosine_similarity(query_vector, p.get("vector", []))
            if score_threshold is not None and sim < score_threshold:
                continue
            scored.append({"id": p.get("id"), "score": sim, "payload": payload})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def count_points(self, name: str, filter_payload: dict[str, Any] | None = None) -> int:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record("count_points", name, filter_payload=filter_payload)
        points = self.collections.get(name, [])
        if not filter_payload:
            return len(points)
        return sum(1 for p in points if _matches_fake_filter(p.get("payload", {}), filter_payload))

    def scroll_points(
        self,
        name: str,
        filter_payload: dict[str, Any] | None = None,
        *,
        limit: int = 1,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> list[dict[str, Any]]:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record(
            "scroll_points",
            name,
            filter_payload=filter_payload,
            limit=limit,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )
        pts = self.collections.get(name, [])
        if filter_payload:
            pts = [p for p in pts if _matches_fake_filter(p.get("payload", {}), filter_payload)]
        batch = pts[:limit]
        formatted: list[dict[str, Any]] = []
        for p in batch:
            item: dict[str, Any] = {"id": p.get("id")}
            if with_payload:
                item["payload"] = p.get("payload", {})
            if with_vectors:
                item["vector"] = p.get("vector", [])
            formatted.append(item)
        return formatted

    def set_payload(
        self,
        name: str,
        payload: dict[str, Any],
        filter_payload: dict[str, Any] | None = None,
        *,
        wait: bool = True,
    ) -> bool:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record("set_payload", name, payload, filter_payload=filter_payload, wait=wait)
        points = self.collections.get(name, [])
        for p in points:
            p_payload = p.setdefault("payload", {})
            if _matches_fake_filter(p_payload, filter_payload):
                p_payload.update(payload)
        return True

    def delete_points_by_files(
        self,
        name: str,
        file_paths: list[str],
        project_name: str | None = None,
        batch_size: int = 500,
        wait: bool = True,
    ) -> bool:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record(
            "delete_points_by_files",
            name,
            file_paths,
            project_name=project_name,
            batch_size=batch_size,
            wait=wait,
        )
        if name in self.collections:
            path_set = set(file_paths)
            self.collections[name] = [
                p
                for p in self.collections[name]
                if not (
                    p.get("payload", {}).get("file_path") in path_set
                    and (
                        project_name is None
                        or p.get("payload", {}).get("project_name") == project_name
                    )
                )
            ]
        return True

    def delete_points_by_project(
        self,
        name: str,
        project_name: str,
        batch_size: int = 500,
        wait: bool = True,
    ) -> bool:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record(
            "delete_points_by_project", name, project_name, batch_size=batch_size, wait=wait
        )
        if name in self.collections:
            self.collections[name] = [
                p
                for p in self.collections[name]
                if p.get("payload", {}).get("project_name") != project_name
            ]
        return True


def seed_knowledge_base(
    fake: FakeQdrantClient,
    docs_collection: str = "devops_docs",
    *,
    embedding_model: str | None = None,
) -> None:
    """Hold the installed knowledge base's digest in `docs_collection`, as an indexed store does.

    A RAG search checks the knowledge base before it searches, and rebuilds it when the store
    holds none of its points. With this point the check finds the knowledge base current and
    rebuilds nothing. The point's vector is empty, so it matches no query. A test that indexes
    into the same store gives the embedder's model as `embedding_model`, as the indexer records it.
    """
    fake.upsert_points(
        docs_collection,
        [
            {
                "id": "knowledge-base-seed",
                "vector": [0.0] * fake.vector_sizes.get(docs_collection, 4),
                "payload": {
                    "project_name": CONST_RAG_KB_PROJECT,
                    "kb_digest": knowledge_base_digest(),
                    **({"embedding_model": embedding_model} if embedding_model else {}),
                },
            }
        ],
    )


def seed_chunk(
    fake: FakeQdrantClient,
    embedder: Any,
    content: str,
    *,
    collection: str = "devops_code",
    file_path: str = "src/main.py",
    point_id: str | None = None,
    **payload: Any,
) -> str:
    """Hold one chunk in `collection`, as the indexer stores it, and return its point id.

    The vector is the embedder's vector of `content`, so a search for that text scores 1.0.
    """
    point = point_id or f"{file_path}:{len(fake.collections.get(collection, []))}"
    vector = embedder.embed_texts([content], is_query=False)[0]
    fake.ensure_collection(collection, len(vector))
    fake.upsert_points(
        collection,
        [
            {
                "id": point,
                "vector": vector,
                "payload": {
                    "file_path": file_path,
                    "start_line": 1,
                    "end_line": 10,
                    "content": content,
                    "language": "python",
                    "project_name": "devops-cli",
                    "embedding_model": embedder.model,
                    **payload,
                },
            }
        ],
    )
    return point


def seed_scored_chunk(
    fake: FakeQdrantClient,
    query_vector: Sequence[float],
    score: float,
    content: str,
    *,
    collection: str = "devops_code",
    file_path: str = "src/main.py",
    point_id: str | None = None,
    **payload: Any,
) -> str:
    """Hold one chunk in `collection` that a search with `query_vector` scores exactly `score`.

    The vector of the point is `score` times the unit query vector plus a unit vector at right
    angles to it, so the cosine similarity of the two is `score`. `query_vector` needs two or more
    dimensions and must not be all zero.
    """
    norm = math.sqrt(sum(x * x for x in query_vector))
    unit = [x / norm for x in query_vector]
    axis = min(range(len(unit)), key=lambda i: abs(unit[i]))
    other = [1.0 if i == axis else 0.0 for i in range(len(unit))]
    along = sum(a * b for a, b in zip(other, unit, strict=True))
    ortho = [o - along * u for o, u in zip(other, unit, strict=True)]
    ortho_norm = math.sqrt(sum(x * x for x in ortho))
    spread = math.sqrt(max(0.0, 1.0 - score * score))
    vector = [score * u + spread * o / ortho_norm for u, o in zip(unit, ortho, strict=True)]
    point = point_id or f"{file_path}:{len(fake.collections.get(collection, []))}"
    fake.ensure_collection(collection, len(vector))
    fake.upsert_points(
        collection,
        [
            {
                "id": point,
                "vector": vector,
                "payload": {
                    "file_path": file_path,
                    "start_line": 1,
                    "end_line": 10,
                    "content": content,
                    "language": "python",
                    **payload,
                },
            }
        ],
    )
    return point


@dataclass
class ServedQdrant:
    """The address of a loopback Qdrant REST server, what it answers, and what it received."""

    url: str
    collections: list[str] = field(default_factory=list)
    points: list[dict[str, Any]] = field(default_factory=list)
    drop_connections: int = 0
    collection_info: dict[str, Any] | None = None
    requests: list[tuple[str, str, dict[str, str]]] = field(default_factory=list)
    bodies: list[tuple[str, str, Any]] = field(default_factory=list)

    def headers_of_requests(self) -> list[dict[str, str]]:
        """The headers of each request, in the order the server received them."""
        return [headers for _, _, headers in self.requests]


def _served_result(served: ServedQdrant, prefix: str, method: str, path: str) -> Any:
    """The `result` of the REST answer for one request, or None for a path the server lacks."""
    if method == "GET" and path == f"{prefix}/collections":
        return {"collections": [{"name": name} for name in served.collections]}
    if not path.startswith(f"{prefix}/collections/"):
        return None
    is_collection = path.removeprefix(prefix).count("/") == 2
    if method == "GET" and served.collection_info is not None and is_collection:
        return served.collection_info
    if method == "POST" and path.endswith("/points/query"):
        return {"points": served.points}
    if method == "PUT" and path.endswith("/index"):
        return {"operation_id": 0, "status": "completed"}
    if method == "PUT":
        return True
    return None


@contextmanager
def serving_qdrant(
    *, prefix: str = "", collections: Sequence[str] = (), points: Sequence[dict[str, Any]] = ()
) -> Iterator[ServedQdrant]:
    """A loopback server that speaks the part of the Qdrant REST API that searches and collection setup use.

    It answers `GET <prefix>/collections` with `collections`, `GET <prefix>/collections/<name>`
    with `collection_info` when the test sets it, `POST <prefix>/collections/<name>/
    points/query` with `points`, and `PUT` of a collection or of its index with success. Every other
    path answers 404, as a collection that does not exist does. It records each request's method,
    path and headers, and the JSON body of each request that has one. The next `drop_connections` requests are cut without an answer, as a tunnel
    that closes a keep-alive connection cuts them. A test of what the real native client sends or
    retries, such as its API key header, the proxy prefix of a cluster address or the retry of a
    dropped connection, reads the record. The prefix is the path that a Kubernetes API server
    proxies a Service under.
    """
    served = ServedQdrant(url="", collections=list(collections), points=list(points))

    class Handler(BaseHTTPRequestHandler):
        def _answer(self, method: str) -> None:
            headers = {k.lower(): v for k, v in self.headers.items()}
            served.requests.append((method, self.path, headers))
            length = int(headers.get("content-length", "0"))
            if length:
                served.bodies.append((method, self.path, json.loads(self.rfile.read(length))))
            if served.drop_connections > 0:
                served.drop_connections -= 1
                self.close_connection = True
                return
            result = _served_result(served, prefix, method, self.path.split("?")[0])
            if result is None:
                body, status = b"{}", 404
            else:
                body = json.dumps({"result": result, "status": "ok", "time": 0.0}).encode()
                status = 200
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            self._answer("GET")

        def do_POST(self) -> None:
            self._answer("POST")

        def do_PUT(self) -> None:
            self._answer("PUT")

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    served.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield served
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def qdrant() -> Iterator[Any]:
    """Install an in-memory FakeQdrantClient as the Qdrant seam override, and return it."""
    from devops_cli.ai.rag.qdrant import install_qdrant_client, reset_qdrant_client

    fake = FakeQdrantClient()
    install_qdrant_client(fake)
    try:
        yield fake
    finally:
        reset_qdrant_client()
