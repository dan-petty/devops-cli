"""Research index of fetched pages keyed by question (#3915)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from devops_cli.ai.page_text import PageText
from devops_cli.config.settings import load_settings
from devops_cli.roadmap.body_hash import hash_text

_DEFAULT_EXPIRY_DAYS: Final[int] = 30


@dataclass
class IndexedAnswer:
    """A fetched page indexed under the question it answered."""

    question: str
    text: str
    source_url: str
    fetched_at: datetime
    content_hash: str
    expiry: datetime

    def is_fresh(self, now: datetime | None = None) -> bool:
        """Whether this answer has not expired and its content hash matches."""
        if now is None:
            now = datetime.now(UTC)
        if self.expiry <= now:
            return False
        expected_hash = hash_text(f"{self.question}\n{self.text}")
        return self.content_hash == expected_hash


class ResearchIndex:
    """SQLite store of fetched pages for ask-mode tools."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            settings = load_settings()
            self.db_path = settings.data.dir / "research" / "index.sqlite3"

    def _get_connection(self, create: bool = False) -> sqlite3.Connection | None:
        if not self.db_path.exists():
            if not create:
                return None
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        if create:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_index (
                    question TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    PRIMARY KEY (question, source_url)
                )
                """
            )
            conn.commit()
        return conn

    def store(
        self,
        question: str,
        page: PageText,
        expiry_days: int = _DEFAULT_EXPIRY_DAYS,
    ) -> IndexedAnswer:
        """Write or update an indexed page for a question."""
        fetched_at = page.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        else:
            fetched_at = fetched_at.astimezone(UTC)

        expiry = fetched_at + timedelta(days=expiry_days)
        content_hash = hash_text(f"{question}\n{page.text}")

        conn = self._get_connection(create=True)
        if conn is None:
            msg = f"Failed to open research index at {self.db_path}"
            raise RuntimeError(msg)
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO research_index
                (question, text, source_url, fetched_at, content_hash, expiry)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    question,
                    page.text,
                    page.source_url,
                    fetched_at.isoformat(),
                    content_hash,
                    expiry.isoformat(),
                ),
            )
        conn.close()

        return IndexedAnswer(
            question=question,
            text=page.text,
            source_url=page.source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            expiry=expiry,
        )

    def lookup(self, question: str) -> IndexedAnswer | None:
        """Find the indexed answer for a question, if stored."""
        conn = self._get_connection(create=False)
        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT question, text, source_url, fetched_at, content_hash, expiry
            FROM research_index
            WHERE question = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (question,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return IndexedAnswer(
            question=row[0],
            text=row[1],
            source_url=row[2],
            fetched_at=datetime.fromisoformat(row[3]),
            content_hash=row[4],
            expiry=datetime.fromisoformat(row[5]),
        )

    def grep(
        self,
        term: str | None = None,
        pattern: str | None = None,
    ) -> list[IndexedAnswer]:
        """Match stored answers by exact substring (SQLite LIKE) or regex pattern."""
        conn = self._get_connection(create=False)
        if conn is None:
            return []

        cursor = conn.cursor()
        if term is not None:
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            cursor.execute(
                """
                SELECT question, text, source_url, fetched_at, content_hash, expiry
                FROM research_index
                WHERE text LIKE ? ESCAPE '\\'
                ORDER BY fetched_at DESC
                """,
                (f"%{escaped}%",),
            )
        else:
            cursor.execute(
                """
                SELECT question, text, source_url, fetched_at, content_hash, expiry
                FROM research_index
                ORDER BY fetched_at DESC
                """
            )
        rows = cursor.fetchall()
        conn.close()

        answers: list[IndexedAnswer] = []
        compiled_re = re.compile(pattern) if pattern is not None else None

        for row in rows:
            text = row[1]
            if compiled_re is not None and not compiled_re.search(text):
                continue
            answers.append(
                IndexedAnswer(
                    question=row[0],
                    text=text,
                    source_url=row[2],
                    fetched_at=datetime.fromisoformat(row[3]),
                    content_hash=row[4],
                    expiry=datetime.fromisoformat(row[5]),
                )
            )

        return answers


__all__ = ["IndexedAnswer", "ResearchIndex"]
