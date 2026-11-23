"""Tests for roadmap research ask index (#3915)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from devops_cli.ai.page_text import PageText
from devops_cli.roadmap.ask_index import IndexedAnswer, ResearchIndex
from devops_cli.roadmap.body_hash import hash_text


def test_a_new_answer_writes_page_fields_only(tmp_path: Path) -> None:
    db_path = tmp_path / "research" / "index.sqlite3"
    index = ResearchIndex(db_path)

    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    page = PageText(
        text="# Python Guide\nDetails about python.",
        source_url="https://example.com/python",
        fetched_at=now,
        truncated=False,
    )
    answer = index.store(
        question="How does Python work?",
        page=page,
        expiry_days=30,
    )

    assert answer.question == "How does Python work?"
    assert answer.text == page.text
    assert answer.source_url == "https://example.com/python"
    assert answer.fetched_at == now
    assert answer.content_hash == hash_text(f"How does Python work?\n{page.text}")
    assert answer.expiry == now + timedelta(days=30)
    assert answer.is_fresh(now)

    # Verify SQLite schema has only the expected columns and no search result fields
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(research_index)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    expected_cols = {"question", "text", "source_url", "fetched_at", "content_hash", "expiry"}
    assert columns == expected_cols
    for forbidden in ("title", "snippet", "rank", "age"):
        assert forbidden not in columns


def test_freshness_rules(tmp_path: Path) -> None:
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    q = "What is Foo?"
    text = "Foo is a bar."
    h = hash_text(f"{q}\n{text}")

    fresh = IndexedAnswer(
        question=q,
        text=text,
        source_url="https://example.com/foo",
        fetched_at=now,
        content_hash=h,
        expiry=now + timedelta(days=1),
    )
    assert fresh.is_fresh(now)

    expired = IndexedAnswer(
        question=q,
        text=text,
        source_url="https://example.com/foo",
        fetched_at=now - timedelta(days=35),
        content_hash=h,
        expiry=now - timedelta(days=5),
    )
    assert not expired.is_fresh(now)

    bad_hash = IndexedAnswer(
        question=q,
        text=text,
        source_url="https://example.com/foo",
        fetched_at=now,
        content_hash="tampered-hash",
        expiry=now + timedelta(days=1),
    )
    assert not bad_hash.is_fresh(now)


def test_read_back_by_question_and_grep_match(tmp_path: Path) -> None:
    db_path = tmp_path / "research" / "index.sqlite3"
    index = ResearchIndex(db_path)

    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    page1 = PageText(
        text="Alpha beta gamma 100% complete.",
        source_url="https://example.com/alpha",
        fetched_at=now,
        truncated=False,
    )
    page2 = PageText(
        text="Delta epsilon zeta_func() test.",
        source_url="https://example.com/delta",
        fetched_at=now,
        truncated=False,
    )

    index.store(question="alpha question", page=page1)
    index.store(question="delta question", page=page2)

    # Read back by question
    read1 = index.lookup("alpha question")
    assert read1 is not None
    assert read1.source_url == "https://example.com/alpha"
    assert read1.text == page1.text

    # Exact term match (LIKE with ESCAPE)
    matches_exact = index.grep(term="100%")
    assert len(matches_exact) == 1
    assert matches_exact[0].source_url == "https://example.com/alpha"

    # Regex pattern match
    matches_regex = index.grep(pattern=r"zeta_\w+\(\)")
    assert len(matches_regex) == 1
    assert matches_regex[0].source_url == "https://example.com/delta"
