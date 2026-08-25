"""High-reliability client for Qdrant Vector Database using official qdrant-client SDK."""

from __future__ import annotations

import logging
import time
import urllib.parse
import uuid
from collections.abc import Callable
from typing import Any

from qdrant_client import QdrantClient as NativeQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import ResponseHandlingException

from devops_cli.config.defaults import DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
from devops_cli.http.validation import validate_service_url
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)


class QdrantClientError(RuntimeError):
    """Raised when an interaction with Qdrant fails."""


def _is_transient_qdrant_error(exc: Exception) -> bool:
    """Check if an exception is a transient connection, timeout, or server disconnect error."""
    if isinstance(exc, ResponseHandlingException):
        return True
    err_str = str(exc).lower()
    return any(
        kw in err_str
        for kw in (
            "server disconnected",
            "connection reset",
            "connection refused",
            "remote protocol error",
            "transport error",
            "broken pipe",
            "timed out",
            "timeout",
        )
    )


def _coerce_point_id(p_id: Any) -> int | str:
    """Coerce arbitrary point ID to valid Qdrant integer or UUID string."""
    if isinstance(p_id, int):
        return p_id
    if isinstance(p_id, str):
        try:
            uuid.UUID(p_id)
            return p_id
        except ValueError:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, p_id))
    return str(uuid.uuid4())


def _build_point_struct(p: dict[str, Any]) -> qmodels.PointStruct:
    """Convert point dictionary to Qdrant PointStruct."""
    return qmodels.PointStruct(
        id=_coerce_point_id(p.get("id")),
        vector=p["vector"],
        payload=p.get("payload", {}),
    )


def _build_payload_filter(filter_payload: dict[str, Any] | None) -> qmodels.Filter | None:
    """Construct Qdrant Filter from payload match criteria."""
    if not filter_payload:
        return None
    conditions: list[Any] = [
        qmodels.FieldCondition(key=k, match=qmodels.MatchValue(value=v))
        for k, v in filter_payload.items()
    ]
    return qmodels.Filter(must=conditions)


def _format_query_hits(points: list[Any]) -> list[dict[str, Any]]:
    """Format Qdrant search point results into dictionaries."""
    return [{"id": hit.id, "score": hit.score, "payload": hit.payload or {}} for hit in points]


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
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid base_url: missing scheme or host in '{base_url}'")
        self.base_url = urllib.parse.urlunparse(parsed).rstrip("/")
        self.api_key = api_key
        self.allow_private_network = allow_private_network
        self.timeout = max(timeout, 60.0)

        # Validate URL for SSRF protection
        validate_service_url(self.base_url, "Qdrant", allow=self.allow_private_network)

        self._client: NativeQdrantClient | None = None

    def _get_client(self, force_refresh: bool = False) -> NativeQdrantClient:
        if self._client is None or force_refresh:
            self._client = NativeQdrantClient(
                url=self.base_url,
                api_key=self.api_key,
                timeout=int(self.timeout),
            )
        return self._client

    def _execute_with_retry(
        self, fn: Callable[[NativeQdrantClient], Any], op_desc: str, max_attempts: int = 3
    ) -> Any:
        """Execute a Qdrant client operation with automatic reconnect and exponential backoff."""
        for attempt in range(1, max_attempts + 1):
            try:
                client = self._get_client(force_refresh=(attempt > 1))
                return fn(client)
            except Exception as exc:
                if attempt < max_attempts and _is_transient_qdrant_error(exc):
                    logger.warning(
                        "Transient error in Qdrant %s (attempt %d/%d): %s. Reconnecting...",
                        op_desc,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    time.sleep(0.5 * attempt)
                    continue
                raise

    def is_alive(self) -> bool:
        """Check if Qdrant server is reachable and responsive."""
        try:
            self._execute_with_retry(lambda c: c.get_collections(), "is_alive", max_attempts=2)
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """List all collection names in the Qdrant instance."""
        try:
            res = self._execute_with_retry(lambda c: c.get_collections(), "list_collections")
            return [c.name for c in res.collections]
        except Exception as exc:
            logger.debug("Failed to list Qdrant collections from %s: %s", self.base_url, exc)
            raise QdrantClientError(f"Error connecting to Qdrant: {exc}") from exc

    def get_collection_info(self, name: str) -> dict[str, Any]:
        """Fetch metadata, vectors count, and status for a collection."""
        try:
            info = self._execute_with_retry(
                lambda c: c.get_collection(collection_name=name),
                f"get_collection_info({name})",
            )
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
            self._execute_with_retry(
                lambda c: c.create_collection(
                    collection_name=name,
                    vectors_config=qmodels.VectorParams(size=vector_size, distance=dist_enum),
                ),
                f"create_collection({name})",
            )
            return True
        except Exception as exc:
            logger.error("Error creating collection %s in Qdrant: %s", name, exc)
            raise QdrantClientError(f"Error creating collection '{name}': {exc}") from exc

    def delete_collection(self, name: str) -> bool:
        """Delete a collection from Qdrant."""
        try:
            res = self._execute_with_retry(
                lambda c: c.delete_collection(collection_name=name),
                f"delete_collection({name})",
            )
            return bool(res)
        except Exception as exc:
            err_str = str(exc)
            if "not found" in err_str.lower() or "404" in err_str:
                return True
            logger.error("Error deleting collection %s in Qdrant: %s", name, exc)
            raise QdrantClientError(f"Error deleting collection '{name}': {exc}") from exc

    def _upsert_batch_with_retry(self, name: str, point_structs: list[qmodels.PointStruct]) -> None:
        """Upsert a single batch of point structs with exponential backoff on transient errors."""
        try:
            self._execute_with_retry(
                lambda c: c.upsert(collection_name=name, points=point_structs, wait=True),
                f"upsert_points({name})",
            )
        except Exception as exc:
            logger.error("Error during Qdrant batch upsert: %s", exc)
            raise QdrantClientError(f"Error upserting points into '{name}': {exc}") from exc

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

        total_upserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            point_structs = [_build_point_struct(p) for p in batch]
            self._upsert_batch_with_retry(name, point_structs)
            total_upserted += len(batch)

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
        with trace_span(
            "qdrant.search_points",
            attributes={
                "db.system": "qdrant",
                "db.operation": "search_points",
                "db.collection.name": name,
                "collection": name,
                "server.address": str(self.base_url),
                "limit": limit,
            },
        ) as q_span:
            query_filter = _build_payload_filter(filter_payload)

            try:
                res = self._execute_with_retry(
                    lambda c: c.query_points(
                        collection_name=name,
                        query=query_vector,
                        limit=limit,
                        score_threshold=score_threshold,
                        query_filter=query_filter,
                        with_payload=True,
                    ),
                    f"search_points({name})",
                )
                hits = _format_query_hits(res.points)
                q_span.set_attribute("db.response.returned_points", len(hits))
                if hits:
                    q_span.set_attribute("db.response.top_score", hits[0]["score"])
                record_metric("qdrant.search_hits_count", float(len(hits)), unit="1")
                return hits
            except Exception as exc:
                err_str = str(exc)
                if "not found" in err_str.lower() or "404" in err_str:
                    return []
                logger.debug("Error searching collection %s: %s", name, exc)
                raise QdrantClientError(f"Search failed in '{name}': {exc}") from exc

    def delete_points_by_file(
        self, name: str, file_path: str, *, project_name: str | None = None
    ) -> bool:
        """Delete all indexed chunks for a file path, optionally scoped to a project."""
        must_conditions: list[qmodels.Condition] = [
            qmodels.FieldCondition(
                key="file_path",
                match=qmodels.MatchValue(value=file_path),
            )
        ]
        if project_name:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="project_name",
                    match=qmodels.MatchValue(value=project_name),
                )
            )
        file_filter = qmodels.Filter(must=must_conditions)
        try:
            self._execute_with_retry(
                lambda c: c.delete(
                    collection_name=name,
                    points_selector=qmodels.FilterSelector(filter=file_filter),
                    wait=True,
                ),
                f"delete_points_by_file({name}, {file_path}, project={project_name})",
            )
            return True
        except Exception as exc:
            logger.debug(
                "Failed to delete points by file for %s (project: %s): %s",
                file_path,
                project_name,
                exc,
            )
            return False
