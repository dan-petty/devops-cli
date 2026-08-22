"""High-reliability client for Qdrant Vector Database using official qdrant-client SDK."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient as NativeQdrantClient
from qdrant_client.http import models as qmodels

from devops_cli.config.defaults import DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
from devops_cli.http.validation import validate_service_url
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)


class QdrantClientError(RuntimeError):
    """Raised when an interaction with Qdrant fails."""


class QdrantClient:
    """Client for Qdrant vector database using official Qdrant Python SDK."""

    def __init__(
        self,
        base_url: str = "http://localhost:6333",
        *,
        api_key: str | None = None,
        allow_private_network: bool = True,
        timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.allow_private_network = allow_private_network
        self.timeout = min(timeout, 30.0)

        # Validate URL for SSRF protection
        validate_service_url(self.base_url, "Qdrant", allow=self.allow_private_network)

        self._client: NativeQdrantClient | None = None

    def _get_client(self) -> NativeQdrantClient:
        if self._client is None:
            self._client = NativeQdrantClient(
                url=self.base_url,
                api_key=self.api_key,
                timeout=int(self.timeout),
            )
        return self._client

    def is_alive(self) -> bool:
        """Check if Qdrant server is reachable and responsive."""
        try:
            client = self._get_client()
            client.get_collections()
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """List all collection names in the Qdrant instance."""
        try:
            client = self._get_client()
            res = client.get_collections()
            return [c.name for c in res.collections]
        except Exception as exc:
            logger.debug("Failed to list Qdrant collections from %s: %s", self.base_url, exc)
            raise QdrantClientError(f"Error connecting to Qdrant: {exc}") from exc

    def get_collection_info(self, name: str) -> dict[str, Any]:
        """Fetch metadata, vectors count, and status for a collection."""
        try:
            client = self._get_client()
            info = client.get_collection(collection_name=name)
            points_count = info.points_count or 0
            vectors_count = getattr(info, "indexed_vectors_count", None) or points_count
            status_val = (
                str(info.status.value) if hasattr(info.status, "value") else str(info.status)
            )
            return {
                "status": status_val,
                "points_count": points_count,
                "vectors_count": vectors_count,
            }
        except Exception as exc:
            err_str = str(exc)
            if "not found" in err_str.lower() or "404" in err_str:
                return {}
            logger.debug("Failed to get Qdrant collection %s info: %s", name, exc)
            raise QdrantClientError(f"Error fetching collection info: {exc}") from exc

    def ensure_collection(
        self,
        name: str,
        vector_size: int,
        distance: str = "Cosine",
    ) -> bool:
        """Create collection if it does not already exist."""
        info = self.get_collection_info(name)
        if info:
            return True

        dist_enum = getattr(qmodels.Distance, distance.upper(), qmodels.Distance.COSINE)
        try:
            client = self._get_client()
            client.create_collection(
                collection_name=name,
                vectors_config=qmodels.VectorParams(size=vector_size, distance=dist_enum),
            )
            return True
        except Exception as exc:
            logger.error("Error creating collection %s in Qdrant: %s", name, exc)
            raise QdrantClientError(f"Error creating collection '{name}': {exc}") from exc

    def delete_collection(self, name: str) -> bool:
        """Delete a collection from Qdrant."""
        try:
            client = self._get_client()
            return bool(client.delete_collection(collection_name=name))
        except Exception as exc:
            err_str = str(exc)
            if "not found" in err_str.lower() or "404" in err_str:
                return True
            logger.error("Error deleting collection %s in Qdrant: %s", name, exc)
            raise QdrantClientError(f"Error deleting collection '{name}': {exc}") from exc

    def upsert_points(
        self,
        name: str,
        points: list[dict[str, Any]],
        *,
        batch_size: int = 64,
    ) -> int:
        """Upsert a list of point dictionaries (id, vector, payload) in batches."""
        if not points:
            return 0

        client = self._get_client()
        total_upserted = 0

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            point_structs: list[qmodels.PointStruct] = []
            for p in batch:
                p_id = p.get("id")
                point_id: int | str
                if isinstance(p_id, int):
                    point_id = p_id
                elif isinstance(p_id, str):
                    try:
                        uuid.UUID(p_id)
                        point_id = p_id
                    except ValueError:
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, p_id))
                else:
                    point_id = str(uuid.uuid4())
                point_structs.append(
                    qmodels.PointStruct(
                        id=point_id,
                        vector=p["vector"],
                        payload=p.get("payload", {}),
                    )
                )
            try:
                client.upsert(
                    collection_name=name,
                    points=point_structs,
                    wait=True,
                )
                total_upserted += len(batch)
            except Exception as exc:
                logger.error("Error during Qdrant batch upsert: %s", exc)
                raise QdrantClientError(f"Error upserting points into '{name}': {exc}") from exc

        return total_upserted

    def search_points(
        self,
        name: str,
        query_vector: list[float],
        *,
        limit: int = 5,
        score_threshold: float | None = None,
        filter_payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search nearest vector points in the specified collection."""
        with trace_span("qdrant.search_points", attributes={"collection": name, "limit": limit}):
            client = self._get_client()
            query_filter = None
            if filter_payload:
                conditions: list[qmodels.Condition] = []
                for key, val in filter_payload.items():
                    conditions.append(
                        qmodels.FieldCondition(
                            key=key,
                            match=qmodels.MatchValue(value=val),
                        )
                    )
                query_filter = qmodels.Filter(must=conditions)

            try:
                res = client.query_points(
                    collection_name=name,
                    query=query_vector,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=query_filter,
                    with_payload=True,
                )
                hits = [
                    {
                        "id": hit.id,
                        "score": hit.score,
                        "payload": hit.payload or {},
                    }
                    for hit in res.points
                ]
                record_metric("qdrant.search_hits_count", float(len(hits)), unit="1")
                return hits
            except Exception as exc:
                err_str = str(exc)
                if "not found" in err_str.lower() or "404" in err_str:
                    return []
                logger.debug("Error searching collection %s: %s", name, exc)
                raise QdrantClientError(f"Search failed in '{name}': {exc}") from exc

    def delete_points_by_file(self, name: str, file_path: str) -> bool:
        """Delete all indexed chunks belonging to a given file path."""
        client = self._get_client()
        file_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="file_path",
                    match=qmodels.MatchValue(value=file_path),
                )
            ]
        )
        try:
            client.delete(
                collection_name=name,
                points_selector=qmodels.FilterSelector(filter=file_filter),
                wait=True,
            )
            return True
        except Exception as exc:
            logger.debug("Failed to delete points by file for %s: %s", file_path, exc)
            return False
