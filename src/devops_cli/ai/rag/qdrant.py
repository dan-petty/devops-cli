"""High-reliability HTTP client for Qdrant Vector Database."""

from __future__ import annotations

import logging
from typing import Any

import httpx2

from devops_cli.config.defaults import DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
from devops_cli.http.validation import validate_service_url

logger = logging.getLogger(__name__)


class QdrantClientError(RuntimeError):
    """Raised when an interaction with the Qdrant REST API fails."""


class QdrantClient:
    """Client for Qdrant vector database using secure httpx2 transport."""

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

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    def _validate_url(self, endpoint: str) -> str:
        url = f"{self.base_url}{endpoint}"
        validate_service_url(url, "Qdrant", allow=self.allow_private_network)
        return url

    def is_alive(self) -> bool:
        """Check if Qdrant server is reachable and responsive."""
        try:
            url = self._validate_url("/readyz")
            with httpx2.Client(timeout=2.0) as client:
                res = client.get(url, headers=self._get_headers())
                return res.status_code == 200
        except Exception:
            try:
                url = self._validate_url("/collections")
                with httpx2.Client(timeout=2.0) as client:
                    res = client.get(url, headers=self._get_headers())
                    return res.status_code == 200
            except Exception:
                return False

    def list_collections(self) -> list[str]:
        """List all collection names in the Qdrant instance."""
        url = self._validate_url("/collections")
        try:
            with httpx2.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._get_headers())
                if res.status_code != 200:
                    raise QdrantClientError(
                        f"Failed to list collections: HTTP {res.status_code} {res.text}"
                    )
                data = res.json()
                collections = data.get("result", {}).get("collections", [])
                return [c.get("name", "") for c in collections if c.get("name")]
        except Exception as exc:
            logger.debug("Failed to list Qdrant collections from %s: %s", url, exc)
            raise QdrantClientError(f"Error connecting to Qdrant: {exc}") from exc

    def get_collection_info(self, name: str) -> dict[str, Any]:
        """Fetch metadata, vectors count, and status for a collection."""
        url = self._validate_url(f"/collections/{name}")
        try:
            with httpx2.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._get_headers())
                if res.status_code == 404:
                    return {}
                if res.status_code != 200:
                    raise QdrantClientError(
                        f"Failed to get collection info for '{name}': HTTP {res.status_code}"
                    )
                return res.json().get("result", {})  # type: ignore[no-any-return]
        except Exception as exc:
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

        url = self._validate_url(f"/collections/{name}")
        payload = {
            "vectors": {
                "size": vector_size,
                "distance": distance,
            }
        }
        try:
            with httpx2.Client(timeout=self.timeout) as client:
                res = client.put(url, headers=self._get_headers(), json=payload)
                if res.status_code not in (200, 201):
                    raise QdrantClientError(
                        f"Failed to create collection '{name}': HTTP {res.status_code} {res.text}"
                    )
                return True
        except Exception as exc:
            logger.error("Error creating collection %s in Qdrant: %s", name, exc)
            raise QdrantClientError(f"Error creating collection '{name}': {exc}") from exc

    def delete_collection(self, name: str) -> bool:
        """Delete a collection from Qdrant."""
        url = self._validate_url(f"/collections/{name}")
        try:
            with httpx2.Client(timeout=self.timeout) as client:
                res = client.delete(url, headers=self._get_headers())
                return res.status_code in (200, 404)
        except Exception as exc:
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

        url = self._validate_url(f"/collections/{name}/points?wait=true")
        total_upserted = 0

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            payload = {"points": batch}
            try:
                with httpx2.Client(timeout=self.timeout) as client:
                    res = client.put(url, headers=self._get_headers(), json=payload)
                    if res.status_code not in (200, 201):
                        raise QdrantClientError(
                            f"Upsert points failed: HTTP {res.status_code} {res.text}"
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
        url = self._validate_url(f"/collections/{name}/points/search")
        payload: dict[str, Any] = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
        }
        if score_threshold is not None:
            payload["score_threshold"] = score_threshold

        if filter_payload:
            must_conditions = []
            for key, val in filter_payload.items():
                must_conditions.append({"key": key, "match": {"value": val}})
            payload["filter"] = {"must": must_conditions}

        try:
            with httpx2.Client(timeout=self.timeout) as client:
                res = client.post(url, headers=self._get_headers(), json=payload)
                if res.status_code == 404:
                    return []
                if res.status_code != 200:
                    raise QdrantClientError(
                        f"Search failed in '{name}': HTTP {res.status_code} {res.text}"
                    )
                return res.json().get("result", [])  # type: ignore[no-any-return]
        except Exception as exc:
            logger.debug("Error searching collection %s: %s", name, exc)
            raise QdrantClientError(f"Search failed in '{name}': {exc}") from exc

    def delete_points_by_file(self, name: str, file_path: str) -> bool:
        """Delete all indexed chunks belonging to a given file path."""
        url = self._validate_url(f"/collections/{name}/points/delete?wait=true")
        payload = {
            "filter": {
                "must": [
                    {
                        "key": "file_path",
                        "match": {"value": file_path},
                    }
                ]
            }
        }
        try:
            with httpx2.Client(timeout=self.timeout) as client:
                res = client.post(url, headers=self._get_headers(), json=payload)
                return res.status_code == 200
        except Exception as exc:
            logger.debug("Failed to delete points by file for %s: %s", file_path, exc)
            return False
