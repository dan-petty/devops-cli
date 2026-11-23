"""Ask-mode tools for roadmap jobs (#3915)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic_ai.messages import ToolReturn

from devops_cli.ai.page_text import PageText
from devops_cli.ai.web_search import _guard, web_search
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.ai import SearchFailed, SearchQueryRefused
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.agent_run import empty_answer, error_answer, ok_answer
from devops_cli.roadmap.ask_index import ResearchIndex
from devops_cli.roadmap.fence import code_fence
from devops_cli.roadmap.page_fetch import PageFetch


class ResearchAsk:
    """Ask-mode research coordinator reading the index before web search."""

    def __init__(
        self,
        index: ResearchIndex,
        pages: PageFetch,
        max_calls: int | None = None,
        search_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.index = index
        self.pages = pages
        if max_calls is None:
            max_calls = load_settings().roadmap.research.max_calls_per_run
        self.max_calls = max_calls
        self.calls = 0
        self._search_fn = search_fn

    @property
    def search_fn(self) -> Callable[..., Any] | None:
        return self._search_fn

    @search_fn.setter
    def search_fn(self, value: Callable[..., Any] | None) -> None:
        self._search_fn = value

    def lookup(self, question: str = "") -> ToolReturn:
        """Answer a question from the research index first, or search and fetch if missing or stale."""
        if self.calls >= self.max_calls:
            return error_answer(
                f"The research call limit for this run is reached ({self.max_calls})."
            )

        try:
            _guard(question)
        except SearchQueryRefused as exc:
            return error_answer(str(exc))

        self.calls += 1

        record = self.index.lookup(question)
        if record is not None and record.is_fresh():
            texts = MESSAGES.roadmap
            framed = texts.page_fetch_frame.format(
                url=record.source_url,
                date=record.fetched_at.date().isoformat(),
                cut="",
                fence=code_fence(record.text),
                text=record.text,
            )
            return ok_answer(framed)

        try:
            search_fn = self._search_fn or web_search
            hits = search_fn(question)
        except (SearchQueryRefused, SearchFailed) as exc:
            return error_answer(str(exc))

        if not hits:
            return empty_answer("No search results found.")

        self.pages.offer(hit.url for hit in hits)
        outcome = self.pages.page_of(hits[0].url)
        if not isinstance(outcome, PageText):
            return outcome

        stored = self.index.store(question, outcome)
        texts = MESSAGES.roadmap
        framed = texts.page_fetch_frame.format(
            url=stored.source_url,
            date=stored.fetched_at.date().isoformat(),
            cut="",
            fence=code_fence(stored.text),
            text=stored.text,
        )
        return ok_answer(framed)

    def grep(self, term: str = "", pattern: str = "") -> ToolReturn:
        """Search stored page text in the research index by exact term or regular expression."""
        if self.calls >= self.max_calls:
            return error_answer(
                f"The research call limit for this run is reached ({self.max_calls})."
            )

        if term:
            try:
                _guard(term)
            except SearchQueryRefused as exc:
                return error_answer(str(exc))

        self.calls += 1

        matches = self.index.grep(term=term or None, pattern=pattern or None)
        if not matches:
            return empty_answer("No matching pages found in the research index.")

        parts = [f"URL: {m.source_url}\n{m.text}" for m in matches]
        return ok_answer("\n\n---\n\n".join(parts))


class ResearchToolset:
    """Mixin for toolsets that offer ask-mode research tools."""

    research: ResearchAsk | None = None

    def research_lookup(self, question: str = "") -> ToolReturn:
        """Answer a question from the research index first, or search and fetch if missing or stale.

        Args:
            question: The question to answer.
        """
        if self.research is None:
            return error_answer("The research index is off for this run.")
        return self.research.lookup(question)

    def research_grep(self, term: str = "", pattern: str = "") -> ToolReturn:
        """Search stored page text in the research index by exact term or regular expression.

        Args:
            term: Exact substring to match in stored text.
            pattern: Regular expression pattern to match in stored text.
        """
        if self.research is None:
            return error_answer("The research index is off for this run.")
        return self.research.grep(term=term, pattern=pattern)


def research_ask(
    pages: PageFetch | None,
    toolset: str | None = None,
    index: ResearchIndex | None = None,
    max_calls: int | None = None,
    search_fn: Callable[..., Any] | None = None,
) -> ResearchAsk | None:
    """Build a ResearchAsk instance if page fetching is active, else None."""
    if pages is None:
        return None
    if index is None:
        index = ResearchIndex()
    return ResearchAsk(index=index, pages=pages, max_calls=max_calls, search_fn=search_fn)


__all__ = [
    "ResearchAsk",
    "ResearchToolset",
    "research_ask",
]
