"""In-memory Qdrant fake for tests (#1317).

Provides an in-memory vector store matching the QdrantProtocol seam, supporting
upserts, cosine search, payload filtering, and simulated unreachable / refusing modes.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from devops_cli.ai.rag.qdrant import QdrantClientError, QdrantProtocol


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class FakeQdrantClient(QdrantProtocol):
    """In-memory Qdrant store supporting cosine similarity and payload filters."""

    def __init__(self, *, refusing: bool = False) -> None:
        self.refusing = refusing
        self.collections: dict[str, list[dict[str, Any]]] = {}
        self.vector_sizes: dict[str, int] = {}
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

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
        points = self.collections.get(name, [])
        scored: list[dict[str, Any]] = []
        for p in points:
            payload = p.get("payload", {})
            if filter_payload:
                if not all(payload.get(k) == v for k, v in filter_payload.items()):
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
        return sum(
            1
            for p in points
            if all(p.get("payload", {}).get(k) == v for k, v in filter_payload.items())
        )

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
            pts = [
                p
                for p in pts
                if all(p.get("payload", {}).get(k) == v for k, v in filter_payload.items())
            ]
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

    def delete_points_by_files(
        self,
        name: str,
        file_paths: list[str],
        project_name: str | None = None,
        batch_size: int = 500,
    ) -> bool:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record(
            "delete_points_by_files",
            name,
            file_paths,
            project_name=project_name,
            batch_size=batch_size,
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
    ) -> bool:
        if self.refusing:
            raise QdrantClientError("Server is unreachable")
        self._record("delete_points_by_project", name, project_name, batch_size=batch_size)
        if name in self.collections:
            self.collections[name] = [
                p
                for p in self.collections[name]
                if p.get("payload", {}).get("project_name") != project_name
            ]
        return True
