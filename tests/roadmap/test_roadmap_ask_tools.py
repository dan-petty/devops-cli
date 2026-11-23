"""Tests for roadmap research ask tools (#3915)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.messages import ToolReturn

from devops_cli.ai.page_text import PageText
from devops_cli.ai.web_search import SearchHit
from devops_cli.roadmap.ask_index import ResearchIndex
from devops_cli.roadmap.ask_tools import ResearchAsk, ResearchToolset, research_ask
from devops_cli.roadmap.page_fetch import PageFetch


@pytest.fixture
def fake_pages() -> PageFetch:
    return PageFetch("refine")


def test_a_fresh_record_answers_the_lookup_with_zero_web_calls(
    tmp_path: Path, fake_pages: PageFetch
) -> None:
    index = ResearchIndex(tmp_path / "index.sqlite3")
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    page = PageText(
        text="Cached answer text",
        source_url="https://example.com/cached",
        fetched_at=now,
        truncated=False,
    )
    index.store("What is caching?", page, expiry_days=30)

    ask = ResearchAsk(index=index, pages=fake_pages, max_calls=20)

    with patch("devops_cli.roadmap.ask_tools.web_search") as mock_search:
        result = ask.lookup("What is caching?")
        assert isinstance(result, ToolReturn)
        assert "Cached answer text" in str(result.return_value)
        assert "https://example.com/cached" in str(result.return_value)
        mock_search.assert_not_called()


def test_an_expired_record_causes_one_web_call_and_updates_store(
    tmp_path: Path, fake_pages: PageFetch
) -> None:
    index = ResearchIndex(tmp_path / "index.sqlite3")
    old_time = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    old_page = PageText(
        text="Old stale text",
        source_url="https://example.com/stale",
        fetched_at=old_time,
        truncated=False,
    )
    # Stored with 1 day expiry, so it is expired today
    index.store("What is stale?", old_page, expiry_days=1)

    new_now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    new_page = PageText(
        text="Refreshed fresh text",
        source_url="https://example.com/fresh",
        fetched_at=new_now,
        truncated=False,
    )

    setattr(fake_pages, "page_of", MagicMock(return_value=new_page))
    ask = ResearchAsk(index=index, pages=fake_pages, max_calls=20)

    with patch(
        "devops_cli.roadmap.ask_tools.web_search",
        return_value=[
            SearchHit(
                url="https://example.com/fresh",
                title="Fresh",
                snippet="snippet",
                provider="searxng",
            )
        ],
    ) as mock_search:
        result = ask.lookup("What is stale?")
        mock_search.assert_called_once_with("What is stale?")
        fake_pages.page_of.assert_called_once_with("https://example.com/fresh")
        assert "Refreshed fresh text" in str(result.return_value)
        assert "https://example.com/fresh" in str(result.return_value)

    # Check that store was updated
    updated = index.lookup("What is stale?")
    assert updated is not None
    assert updated.text == "Refreshed fresh text"


def test_a_query_with_a_private_address_is_refused(tmp_path: Path, fake_pages: PageFetch) -> None:
    index = ResearchIndex(tmp_path / "index.sqlite3")
    ask = ResearchAsk(index=index, pages=fake_pages, max_calls=20)

    with patch("devops_cli.roadmap.ask_tools.web_search") as mock_search:
        result = ask.lookup("Check host at 192.168.1.100")
        assert isinstance(result, ToolReturn)
        assert "The search was refused: the query holds a private address." in str(
            result.return_value
        )
        mock_search.assert_not_called()


def test_research_grep_regular_expression_over_stored_text(
    tmp_path: Path, fake_pages: PageFetch
) -> None:
    index = ResearchIndex(tmp_path / "index.sqlite3")
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    page1 = PageText(
        text="Package foo version 1.2.3 released",
        source_url="https://example.com/pkg-foo",
        fetched_at=now,
        truncated=False,
    )
    page2 = PageText(
        text="Package bar version 2.0.0 released",
        source_url="https://example.com/pkg-bar",
        fetched_at=now,
        truncated=False,
    )
    index.store("q1", page1)
    index.store("q2", page2)

    ask = ResearchAsk(index=index, pages=fake_pages, max_calls=20)
    result = ask.grep(pattern=r"foo version \d+\.\d+\.\d+")
    assert isinstance(result, ToolReturn)
    text = str(result.return_value)
    assert "https://example.com/pkg-foo" in text
    assert "https://example.com/pkg-bar" not in text


def test_the_limit_stops_a_run(tmp_path: Path, fake_pages: PageFetch) -> None:
    index = ResearchIndex(tmp_path / "index.sqlite3")
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    page = PageText(
        text="Some text",
        source_url="https://example.com/page",
        fetched_at=now,
        truncated=False,
    )
    index.store("q", page)

    ask = ResearchAsk(index=index, pages=fake_pages, max_calls=1)
    res1 = ask.lookup("q")
    assert "Some text" in str(res1.return_value)

    res2 = ask.lookup("q")
    assert "limit for this run is reached" in str(res2.return_value)


def test_research_toolset_and_research_ask(tmp_path: Path, fake_pages: PageFetch) -> None:
    assert research_ask(None) is None

    class MyTools(ResearchToolset):
        pass

    tools = MyTools()
    assert "off" in str(tools.research_lookup("hi").return_value)
    assert "off" in str(tools.research_grep("hi").return_value)

    tools.research = research_ask(fake_pages, index=ResearchIndex(tmp_path / "index.sqlite3"))
    assert tools.research is not None
