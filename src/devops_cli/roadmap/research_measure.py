"""Measurement of research candidate against web search baseline (#3915)."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from devops_cli.ai.client.models import AIClientError
from devops_cli.ai.web_search import web_search
from devops_cli.exceptions.ai import SearchFailed, SearchQueryRefused
from devops_cli.roadmap.ask_tools import ResearchAsk


@dataclass(frozen=True)
class ResearchQuestion:
    """A question recorded from alternatives or refine discussions."""

    question: str
    date: datetime


@dataclass
class ResearchMeasure:
    """Evaluation metrics comparing the research candidate to web search."""

    candidate_hits: int
    candidate_requests: int
    candidate_elapsed_seconds: float
    baseline_hits: int
    baseline_requests: int
    baseline_elapsed_seconds: float
    total_questions: int

    @property
    def candidate_hit_rate(self) -> float:
        return self.candidate_hits / self.total_questions if self.total_questions else 0.0

    @property
    def baseline_hit_rate(self) -> float:
        return self.baseline_hits / self.total_questions if self.total_questions else 0.0

    def to_markdown_lines(self) -> list[str]:
        """Format measure results as Markdown lines for the pull request comment."""
        cand_rate = f"{self.candidate_hit_rate * 100:.1f}%"
        base_rate = f"{self.baseline_hit_rate * 100:.1f}%"
        cand_req = (
            f"{self.candidate_requests / self.total_questions:.2f}" if self.total_questions else "0"
        )
        base_req = (
            f"{self.baseline_requests / self.total_questions:.2f}" if self.total_questions else "0"
        )
        cand_time = (
            f"{self.candidate_elapsed_seconds / self.total_questions:.2f}s"
            if self.total_questions
            else "0s"
        )
        base_time = (
            f"{self.baseline_elapsed_seconds / self.total_questions:.2f}s"
            if self.total_questions
            else "0s"
        )
        return [
            "### Research Measure Against Baseline",
            "",
            "| Metric | Candidate (Index + Web) | Baseline (Web Only) |",
            "| --- | --- | --- |",
            f"| Hit rate | {cand_rate} | {base_rate} |",
            f"| Cost per question (requests) | {cand_req} | {base_req} |",
            f"| Elapsed time per question | {cand_time} | {base_time} |",
            f"| Total questions measured | {self.total_questions} | {self.total_questions} |",
        ]


def _extract_questions_from_text(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip().endswith("?")]
    if lines:
        return lines
    stripped = text.strip()
    if stripped.endswith("?") or "?" in text:
        return [stripped]
    return []


def recorded_questions(
    comments: Sequence[tuple[str, datetime]],
    now: datetime | None = None,
) -> list[ResearchQuestion]:
    """Extract at most 10 unique questions from comments within the last 30 days."""
    if now is None:
        now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)

    seen: set[str] = set()
    questions: list[ResearchQuestion] = []

    for text, date in comments:
        utc_date = date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
        if utc_date < cutoff:
            continue

        for q in _extract_questions_from_text(text):
            if q not in seen:
                seen.add(q)
                questions.append(ResearchQuestion(question=q, date=utc_date))
                if len(questions) >= 10:
                    return questions

    return questions


def measure_research(
    questions: Sequence[ResearchQuestion | str],
    ask: ResearchAsk,
    search_fn: Callable[..., Any] | None = None,
) -> ResearchMeasure:
    """Measure candidate hit rate and cost per question against baseline web search."""
    search = search_fn if search_fn is not None else web_search
    orig_search = getattr(ask, "search_fn", web_search)
    ask.search_fn = search

    cand_hits = 0
    cand_requests = 0
    cand_elapsed = 0.0

    base_hits = 0
    base_requests = 0
    base_elapsed = 0.0

    try:
        for item in questions:
            q_text = item.question if isinstance(item, ResearchQuestion) else item

            # Run candidate
            calls_before = ask.calls
            fetches_before = ask.pages.fetches
            start = time.perf_counter()
            res = ask.lookup(q_text)
            cand_elapsed += time.perf_counter() - start
            cand_requests += (ask.calls - calls_before) + (ask.pages.fetches - fetches_before)
            val = str(getattr(res, "return_value", ""))
            if (
                not getattr(res, "is_error", False)
                and val
                and "not fetched" not in val
                and "failed" not in val
            ):
                cand_hits += 1

            # Run baseline
            start = time.perf_counter()
            try:
                hits = search(q_text)
                elapsed = time.perf_counter() - start
                base_elapsed += elapsed
                base_requests += 1
                if hits:
                    base_hits += 1
            except SearchFailed, SearchQueryRefused, AIClientError:
                base_elapsed += time.perf_counter() - start
                base_requests += 1
    finally:
        ask.search_fn = orig_search

    return ResearchMeasure(
        candidate_hits=cand_hits,
        candidate_requests=cand_requests,
        candidate_elapsed_seconds=cand_elapsed,
        baseline_hits=base_hits,
        baseline_requests=base_requests,
        baseline_elapsed_seconds=base_elapsed,
        total_questions=len(questions),
    )


__all__ = [
    "ResearchMeasure",
    "ResearchQuestion",
    "measure_research",
    "recorded_questions",
]
