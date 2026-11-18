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

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.page_text import PageText
from devops_cli.ai.rag.qdrant import QdrantProtocol
from devops_cli.config.defaults import (
    DEFAULT_RAG_RESEARCH_COLLECTION,
    DEFAULT_RESEARCH_EXPIRY_DAYS,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.security.prompt_injection import scan_injection_text


def research_point_id(source_url: str) -> str:
    """The id of the point that holds `source_url`: a UUID version 5 of the URL."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, source_url))


# How many pages one search reads at most. A page whose text holds an injection pattern is left out
# after the search, so the reply can hold fewer pages than this.
_SEARCH_RESULT_LIMIT = 10


def _isoformat(moment: datetime) -> str:
    """`moment` as an ISO 8601 UTC string, as a Qdrant date filter reads it."""
    return moment.astimezone(UTC).isoformat()


def _check_page(page: object) -> None:
    """Guard a page that no fetch of the project produced, before any write (#3906).

    A search hit holds a title and a snippet and no page text, so a point cannot come from it. A
    page with a blank source URL has no provenance. The store keeps fetched pages only.
    """
    if not isinstance(page, PageText):
        raise ValidationError("The research index stores a fetched page only", field="page")
    if not page.source_url.strip():
        raise ValidationError(
            "The research index needs the source URL of the page", field="source_url"
        )


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


class ResearchHit(BaseModel):
    """One stored research page, with the provenance that a search returns (#3906)."""

    model_config = ConfigDict(frozen=True)

    source_url: str = Field(description="The URL that the project fetched the page from")
    fetch_date: datetime = Field(description="When the project fetched the page")
    question: str = Field(description="The question that the page answers")
    text: str = Field(description="The text of the fetched page")
    score: float = Field(description="The similarity of the page to the question")


def _research_hit(raw: dict[str, Any]) -> ResearchHit | None:
    """The hit of one Qdrant point, or None when it holds no provenance or an injection pattern."""
    payload = raw.get("payload") or {}
    source_url = payload.get("source_url")
    fetch_date = payload.get("fetch_date")
    text = payload.get("text", "")
    if not source_url or not fetch_date or scan_injection_text(text):
        return None
    return ResearchHit(
        source_url=source_url,
        fetch_date=datetime.fromisoformat(fetch_date),
        question=payload.get("question", ""),
        text=text,
        score=float(raw.get("score") or 0.0),
    )


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

        Raises `ValidationError` with the field `page` for a page that is not a `PageText`, and with
        the field `source_url` for a page with a blank source URL, before any write.
        """
        _check_page(page)
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

    def search_pages(
        self,
        question: str,
        *,
        limit: int = _SEARCH_RESULT_LIMIT,
        now: datetime | None = None,
    ) -> list[ResearchHit]:
        """The stored pages that answer `question`, with no expired page and no injected page.

        The search keeps only the points whose `expiry` is later than `now`, which is the current
        UTC time when the caller gives none, so a page that no sweep has removed yet stays out of
        the reply. A page whose text gives a finding to `scan_injection_text` is left out as well,
        so the agent gets no fetched page with an injection pattern, and the six fields of ADR 0028
        stay as they are.
        """
        moment = now or datetime.now(UTC)
        found = self.qdrant_client.search_points(
            self.collection_name,
            self.embedder.embed_query(question),
            limit=limit,
            filter_payload={"must_range": {"expiry": {"gt": _isoformat(moment)}}},
        )
        return [hit for hit in map(_research_hit, found) if hit is not None]

    def expire(self, *, now: datetime | None = None) -> None:
        """Delete each stored page whose `expiry` is earlier than `now`.

        `now` is the current UTC time when the caller gives none. A search already leaves an
        expired page out, so the sweep only frees the space that the page holds.
        """
        self.qdrant_client.delete_points_by_expiry(
            self.collection_name, _isoformat(now or datetime.now(UTC))
        )
