"""The tool `fetch_page` of refine's investigation and of the alternatives check (#3890).

A job lets the model read the text of a page, not only its search snippet. The text comes from the
Crawl4AI client (`fetch_page_text`, #3887). A model chooses the URL, so this module is a boundary:

- The tool is on only when the round has web search and `crawl4ai.url` is set
  (`page_fetch_configured`).
- It fetches an https URL only, and only a URL that a `search_web` result of the same run returned
  or that the item text names. Any other URL is refused with a message, and no request is sent.
- It fetches at most `CONST_ROADMAP_PAGE_FETCH_MAX` times in a run. A fetch that fails uses one.
- The answer frames the page text as data from an outside page, never an instruction, and names
  the source URL and the fetch date so that a comment can cite them. The text is not stored.
- Each call adds 1 to `devops_cli_roadmap_page_fetches_total` by its toolset and result.

Every failure is an answer of the tool, so no URL that the model sends can stop the run.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit

from pydantic_ai.messages import ToolReturn

from devops_cli.ai.page_text import fetch_page_text
from devops_cli.ai.web_search import normalize_url
from devops_cli.config.constants import (
    CONST_PROSE_TRAILING_PUNCTUATION,
    CONST_ROADMAP_PAGE_FETCH_MAX,
    CONST_ROADMAP_PAGE_FETCH_MAX_CHARS,
    CONST_ROADMAP_PAGE_FETCH_RESULT_ERROR,
    CONST_ROADMAP_PAGE_FETCH_RESULT_LIMIT,
    CONST_ROADMAP_PAGE_FETCH_RESULT_OK,
    CONST_ROADMAP_PAGE_FETCH_RESULT_REFUSED,
    CONST_URL_CANDIDATE_RE,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.ai import PageTextError
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.exceptions.validation import InvalidURLError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.agent_run import empty_answer, error_answer, ok_answer
from devops_cli.roadmap.fence import code_fence
from devops_cli.telemetry.instruments import ROADMAP_PAGE_FETCHES_TOTAL, emit

TOOLSET_REFINE: Final[str] = "refine"
TOOLSET_ALTERNATIVES: Final[str] = "alternatives"

# A character that ends a URL in prose or in Markdown, and so is not a part of the URL.
_URL_END: Final[str] = "`<>\"'"


def page_fetch_configured() -> bool:
    """Whether `crawl4ai.url` is set. A round offers `fetch_page` when it has web search (a public
    repository and a search provider) and this is true."""
    return bool(load_settings().crawl4ai.url)


def named_urls(*texts: str) -> frozenset[str]:
    """The http and https URLs that `texts` name, as `normalize_url` spells them. A URL ends at a
    quote, a backtick or an angle bracket, and prose punctuation after it is not a part of it."""
    urls: set[str] = set()
    for text in texts:
        for candidate in CONST_URL_CANDIDATE_RE.findall(text):
            end = min((i for i, char in enumerate(candidate) if char in _URL_END), default=None)
            url = candidate[:end].rstrip(CONST_PROSE_TRAILING_PUNCTUATION)
            if urlsplit(url).scheme in ("http", "https"):
                urls.add(normalize_url(url))
    return frozenset(urls)


@dataclass
class PageFetch:
    """The state of `fetch_page` for one run: the URLs a fetch may take, and the fetches made.

    `named` holds the URLs that the item text names. `offer` adds the URLs that a search returned.
    `fetched` holds the URLs of the pages whose text a fetch returned: a source may cite them.
    """

    toolset: str
    named: frozenset[str] = frozenset()
    found: set[str] = field(default_factory=set)
    fetches: int = 0
    fetched: set[str] = field(default_factory=set)

    def offer(self, urls: Iterable[str]) -> None:
        """Let the tool fetch each URL of `urls`, which a web search of this run returned."""
        self.found.update(normalize_url(url) for url in urls)

    def fetch(self, url: str) -> ToolReturn:
        """The framed text of the page at `url`, or the reason in plain text that it was not
        fetched. The URL is checked before any request, and the fetch is counted when it starts."""
        texts = MESSAGES.roadmap
        key = normalize_url(url.strip())
        if urlsplit(key).scheme != "https":
            return self._refused(texts.page_fetch_not_https)
        if key not in self.found and key not in self.named:
            return self._refused(texts.page_fetch_not_named)
        if self.fetches >= CONST_ROADMAP_PAGE_FETCH_MAX:
            return self._answer(
                CONST_ROADMAP_PAGE_FETCH_RESULT_LIMIT, error_answer(texts.page_fetch_limit)
            )
        self.fetches += 1
        try:
            page = fetch_page_text(key, max_chars=CONST_ROADMAP_PAGE_FETCH_MAX_CHARS)
        except InvalidURLError, SSRFBlockedError:
            return self._refused(texts.page_fetch_not_public)
        except DevOpsCLIError as exc:
            # `fetch_page_text` logged the failure. The reason holds no token and no URL.
            reason = exc.reason if isinstance(exc, PageTextError) else type(exc).__name__
            return self._answer(
                CONST_ROADMAP_PAGE_FETCH_RESULT_ERROR,
                error_answer(texts.page_fetch_failed.format(reason=reason)),
            )
        if not page.text.strip():
            return self._answer(
                CONST_ROADMAP_PAGE_FETCH_RESULT_OK, empty_answer(texts.page_fetch_empty)
            )
        self.fetched.add(page.source_url)
        framed = texts.page_fetch_frame.format(
            url=page.source_url,
            date=page.fetched_at.date().isoformat(),
            cut=texts.page_fetch_cut if page.truncated else "",
            fence=code_fence(page.text),
            text=page.text,
        )
        return self._answer(CONST_ROADMAP_PAGE_FETCH_RESULT_OK, ok_answer(framed))

    def _refused(self, message: str) -> ToolReturn:
        return self._answer(CONST_ROADMAP_PAGE_FETCH_RESULT_REFUSED, error_answer(message))

    def _answer(self, result: str, answer: ToolReturn) -> ToolReturn:
        emit(ROADMAP_PAGE_FETCHES_TOTAL, 1, {"toolset": self.toolset, "result": result})
        return answer


__all__ = [
    "TOOLSET_ALTERNATIVES",
    "TOOLSET_REFINE",
    "PageFetch",
    "named_urls",
    "page_fetch_configured",
]
