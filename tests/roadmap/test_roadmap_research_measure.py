"""Tests for roadmap research measure against web search (#3915)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.ai.page_text import PageText
from devops_cli.ai.web_search import SearchHit
from devops_cli.roadmap.ask_index import ResearchIndex
from devops_cli.roadmap.ask_tools import ResearchAsk
from devops_cli.roadmap.page_fetch import PageFetch
from devops_cli.roadmap.research_measure import (
    ResearchMeasure,
    ResearchQuestion,
    measure_research,
    recorded_questions,
)


def test_recorded_questions_extracts_up_to_10_recent_questions() -> None:
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    comments = [(f"How to test feature {i}?", now - timedelta(days=i)) for i in range(15)]
    # Comments older than 30 days should be excluded
    comments.append(("Too old question?", now - timedelta(days=35)))

    questions = recorded_questions(comments, now=now)
    assert len(questions) <= 10
    assert all(isinstance(q, ResearchQuestion) for q in questions)
    assert all(q.date >= now - timedelta(days=30) for q in questions)
    assert not any(q.question == "Too old question?" for q in questions)


def test_measure_research_evaluates_candidate_and_baseline(tmp_path: Path) -> None:
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    index = ResearchIndex(tmp_path / "index.sqlite3")
    pages = PageFetch("stage")

    # Pre-populate index with answer to q1
    page1 = PageText(
        text="Cached answer",
        source_url="https://example.com/cached",
        fetched_at=now,
        truncated=False,
    )
    index.store("What is Q1?", page1)

    ask = ResearchAsk(index=index, pages=pages, max_calls=20)

    # Fake page_of for live fetch on miss
    fresh_page = PageText(
        text="Fresh fetched page",
        source_url="https://example.com/live",
        fetched_at=now,
        truncated=False,
    )
    setattr(pages, "page_of", MagicMock(return_value=fresh_page))

    fake_hits = [
        SearchHit(
            url="https://example.com/live", title="Live", snippet="snippet", provider="searxng"
        )
    ]
    fake_web_search = MagicMock(return_value=fake_hits)

    questions = [
        ResearchQuestion(question="What is Q1?", date=now),
        ResearchQuestion(question="What is Q2?", date=now),
    ]

    measure = measure_research(questions, ask=ask, search_fn=fake_web_search)
    assert isinstance(measure, ResearchMeasure)
    assert measure.total_questions == 2
    assert measure.candidate_hits == 2
    assert measure.baseline_hits == 2
    assert measure.candidate_hit_rate == 1.0
    assert measure.baseline_hit_rate == 1.0

    lines = measure.to_markdown_lines()
    assert any("Hit rate" in line for line in lines)
    assert any("100.0%" in line for line in lines)
