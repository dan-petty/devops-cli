"""The issues a pull request body declares it closes, read as GitHub reads closing keywords, and
the issues it declares it delivers part of.

GitHub acts on a closing keyword only when the pull request merges into the repository's
default branch; item pull requests here target a release branch, so `devops roadmap close`
does the closing from the same links (#743), and readiness checks a body closes one issue. An
item planned as several pull requests names it with `Part of #N` in each but the last; that
closes nothing, and readiness judges the item it names as it judges a closed one.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from devops_cli.config.constants import (
    CONST_ISSUE_CLOSING_KEYWORDS,
    CONST_ISSUE_PART_PHRASE,
)

if TYPE_CHECKING:
    from markdown_it import MarkdownIt

logger = logging.getLogger(__name__)

# After a keyword or phrase: an optional colon, then the issue reference. The owner/repo prefix
# is captured so a cross-repository link is recognised and skipped rather than read as the
# same-numbered issue in this repository.
_ISSUE_REFERENCE = r"\s*:?\s+(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<number>\d+)"
# A closing keyword, then the issue reference. Matched case-insensitively.
_CLOSING_REFERENCE_RE = re.compile(r"\b(?P<keyword>[a-z]+)\b" + _ISSUE_REFERENCE, re.IGNORECASE)
# The part phrase, its words separated by any whitespace, then the issue reference.
_PART_REFERENCE_RE = re.compile(
    r"\b" + r"\s+".join(map(re.escape, CONST_ISSUE_PART_PHRASE.split())) + r"\b" + _ISSUE_REFERENCE,
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LinkedIssue:
    """An issue a pull request body declares it closes."""

    number: int
    keyword: str


@cache
def _commonmark() -> MarkdownIt:
    """markdown-it-py's CommonMark parser, built once."""
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark")


def reset_issue_closure_cache() -> None:
    """Clear the cached CommonMark parser."""
    _commonmark.cache_clear()


def strip_non_prose(body: str) -> str:
    """The body's prose, as markdown-it-py's CommonMark parser reads it: the text of its
    paragraphs, headings and list items outside block quotes, one piece per line.

    Code in any form (backtick or tilde fences, an unclosed fence, indented blocks, inline code)
    and raw HTML, such as the pull request template's comments, are not prose: a body that
    documents the syntax must not be read as a live declaration. Nor is a quote, someone else's
    text. Closing an unrelated issue is not recoverable by the person who wrote the prose.
    """
    quoted = 0
    prose: list[str] = []
    for token in _commonmark().parse(body or ""):
        if token.tag == "blockquote":
            quoted += token.nesting
        elif token.type == "inline" and not quoted:
            prose.extend(child.content for child in token.children or () if child.type == "text")
    return "\n".join(prose)


def _references(pattern: re.Pattern[str], body: str, repo: str | None) -> Iterator[re.Match[str]]:
    """The references `pattern` finds in the body's prose, skipping those to another repository."""
    for match in pattern.finditer(strip_non_prose(body)):
        qualifier = match.group("repo")
        if qualifier and repo and qualifier.lower() != repo.lower():
            logger.debug("Ignoring cross-repository issue reference '%s'.", match.group(0))
            continue
        yield match


def extract_linked_issues(body: str, repo: str | None = None) -> list[LinkedIssue]:
    """Extract the issues a pull request body declares it closes.

    Only the keywords GitHub itself honours are accepted, so what this closes is exactly
    what GitHub would have closed had the pull request targeted the default branch. A bare
    `#317`, or a reference qualified with a different repository, is deliberately ignored.
    """
    found: dict[int, str] = {}
    for match in _references(_CLOSING_REFERENCE_RE, body, repo):
        keyword = match.group("keyword").lower()
        if keyword in CONST_ISSUE_CLOSING_KEYWORDS:
            found.setdefault(int(match.group("number")), keyword)
    return [
        LinkedIssue(number=number, keyword=keyword) for number, keyword in sorted(found.items())
    ]


def extract_part_references(body: str, repo: str | None = None) -> list[int]:
    """Extract the issues a pull request body declares it delivers part of, once each, in order.

    The body is read as `extract_linked_issues` reads it: only its prose, by `strip_non_prose`,
    and not a reference qualified with a different repository. `Part 1 of #317` is not the phrase.
    """
    return sorted(
        {int(match.group("number")) for match in _references(_PART_REFERENCE_RE, body, repo)}
    )


__all__ = ["LinkedIssue", "extract_linked_issues", "extract_part_references", "strip_non_prose"]
