"""The research index: one Qdrant point for each fetched page (#3906, ADR 0028).

ADR 0028 fixes one collection, `devops_research`, that holds one point for each fetched page with
the six fields `source_url`, `fetch_date`, `content_hash`, `expiry`, `question` and `text`. The point
id is a UUID version 5 of the source URL, so a second write of the same URL reaches the same point
and no lookup by a payload filter is needed to keep one point for one URL.

A page whose text is unchanged refreshes the two dates through `set_payload`, so a fetch that reads
the same page again writes no vector. A page whose text changed replaces the text and its vector.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from devops_cli.ai.page_text import PageText
from devops_cli.ai.rag.qdrant import QdrantProtocol
from devops_cli.config.defaults import (
    DEFAULT_RAG_RESEARCH_COLLECTION,
    DEFAULT_RESEARCH_EXPIRY_DAYS,
)


def research_point_id(source_url: str) -> str:
    """The id of the point that holds `source_url`: a UUID version 5 of the URL."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, source_url))


def _isoformat(moment: datetime) -> str:
    """`moment` as an ISO 8601 UTC string, as a Qdrant date filter reads it."""
    return moment.astimezone(UTC).isoformat()


def _payload(page: PageText, question: str) -> dict[str, Any]:
    """The six fields of ADR 0028 for one fetched page."""
    expiry = page.fetched_at + timedelta(days=DEFAULT_RESEARCH_EXPIRY_DAYS)
    return {
        "source_url": page.source_url,
        "fetch_date": _isoformat(page.fetched_at),
        "content_hash": hashlib.sha256(page.text.encode()).hexdigest(),
        "expiry": _isoformat(expiry),
        "question": question,
        "text": page.text,
    }


class ResearchStore:
    """The research collection: one point for each fetched page, keyed to its source URL.

    The store takes its Qdrant client, its embedder and its collection name, as
    `LibraryVectorStore` does, so a test gives it the in-memory fake and a deterministic embedder.
    """

    def __init__(
        self,
        qdrant_client: QdrantProtocol,
        embedder: Any,
        collection_name: str = DEFAULT_RAG_RESEARCH_COLLECTION,
    ) -> None:
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.collection_name = collection_name

    def upsert(self, page: PageText, question: str) -> str:
        """Store `page` as the point of its source URL, and return the point id.

        A stored page with the same `content_hash` only gets the new `fetch_date` and `expiry`, and
        writes no vector. A changed page, or a URL that the collection does not hold, writes the
        text, its hash, the dates and the question.
        """
        payload = _payload(page, question)
        point_id = research_point_id(page.source_url)
        stored = self._stored_payload(page.source_url)
        if stored is not None and stored.get("content_hash") == payload["content_hash"]:
            self.qdrant_client.set_payload(
                self.collection_name,
                {"fetch_date": payload["fetch_date"], "expiry": payload["expiry"]},
                {"source_url": page.source_url},
            )
            return point_id
        vector = self.embedder.embed_texts([page.text], is_query=False)[0]
        self.qdrant_client.ensure_collection(self.collection_name, len(vector))
        self.qdrant_client.upsert_points(
            self.collection_name,
            [{"id": point_id, "vector": vector, "payload": payload}],
        )
        return point_id

    def _stored_payload(self, source_url: str) -> dict[str, Any] | None:
        """The payload of the point that holds `source_url`, or None when it holds none."""
        found = self.qdrant_client.scroll_points(
            self.collection_name, {"source_url": source_url}, limit=1
        )
        return found[0]["payload"] if found else None
