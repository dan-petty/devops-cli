"""The research store keeps one point for each fetched page (#3906)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.ai.page_text import PageText

pytestmark = pytest.mark.usefixtures("keyring_store")

_QUESTION = "How does Qdrant keep only the live points?"
_URL = "https://example.com/qdrant-filters"
_FIRST_FETCH = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_LATER_FETCH = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
_FIRST_TEXT = "Qdrant reads a date range with a DatetimeRange condition."
_SECOND_TEXT = "Qdrant reads a date range with a DatetimeRange condition, and a filter."
_EXPIRY_DAYS = 30


def _store(qdrant: Any, embedder: Any) -> Any:
    """A research store over the in-memory Qdrant fake and the deterministic embedder."""
    from devops_cli.ai.research.store import ResearchStore

    return ResearchStore(qdrant, embedder)


def _page(
    text: str = _FIRST_TEXT,
    *,
    url: str = _URL,
    fetched_at: datetime = _FIRST_FETCH,
) -> PageText:
    """One fetched page, as `fetch_page_text` returns it."""
    return PageText(source_url=url, text=text, fetched_at=fetched_at, truncated=False)


def _points(qdrant: Any, store: Any) -> list[dict[str, Any]]:
    """The points that the research collection holds."""
    return list(qdrant.collections.get(store.collection_name, []))


def _calls(qdrant: Any, name: str) -> list[tuple[str, tuple[Any, ...], dict[str, Any]]]:
    """The calls of one operation that the store sent to Qdrant."""
    return [call for call in qdrant.calls if call[0] == name]


def test_upsert_stores_the_six_fields_of_the_adr(qdrant: Any, embedder: Any) -> None:
    store = _store(qdrant, embedder)
    store.upsert(_page(), _QUESTION)

    points = _points(qdrant, store)
    assert len(points) == 1
    payload = points[0]["payload"]
    assert set(payload) == {
        "source_url",
        "fetch_date",
        "content_hash",
        "expiry",
        "question",
        "text",
    }
    assert payload["source_url"] == _URL
    assert payload["question"] == _QUESTION
    assert payload["text"] == _FIRST_TEXT
    assert payload["content_hash"] == hashlib.sha256(_FIRST_TEXT.encode()).hexdigest()
    assert datetime.fromisoformat(payload["fetch_date"]) == _FIRST_FETCH
    assert datetime.fromisoformat(payload["expiry"]) == _FIRST_FETCH + timedelta(days=_EXPIRY_DAYS)


def test_upsert_of_an_equal_hash_refreshes_the_dates(qdrant: Any, embedder: Any) -> None:
    store = _store(qdrant, embedder)
    store.upsert(_page(), _QUESTION)
    first = _points(qdrant, store)[0]

    store.upsert(_page(fetched_at=_LATER_FETCH), _QUESTION)

    points = _points(qdrant, store)
    assert len(points) == 1
    payload = points[0]["payload"]
    assert datetime.fromisoformat(payload["fetch_date"]) == _LATER_FETCH
    assert datetime.fromisoformat(payload["expiry"]) == _LATER_FETCH + timedelta(days=_EXPIRY_DAYS)
    assert payload["content_hash"] == first["payload"]["content_hash"]
    assert payload["text"] == _FIRST_TEXT
    assert points[0]["vector"] == first["vector"]
    assert len(_calls(qdrant, "upsert_points")) == 1
    assert len(embedder.calls) == 1


def test_upsert_of_a_changed_text_replaces_the_text(qdrant: Any, embedder: Any) -> None:
    store = _store(qdrant, embedder)
    store.upsert(_page(), _QUESTION)
    first = _points(qdrant, store)[0]

    store.upsert(_page(_SECOND_TEXT, fetched_at=_LATER_FETCH), _QUESTION)

    points = _points(qdrant, store)
    assert len(points) == 1
    assert points[0]["id"] == first["id"]
    payload = points[0]["payload"]
    assert payload["text"] == _SECOND_TEXT
    assert payload["content_hash"] == hashlib.sha256(_SECOND_TEXT.encode()).hexdigest()
    assert datetime.fromisoformat(payload["fetch_date"]) == _LATER_FETCH
    assert datetime.fromisoformat(payload["expiry"]) == _LATER_FETCH + timedelta(days=_EXPIRY_DAYS)
    assert len(embedder.calls) == 2
