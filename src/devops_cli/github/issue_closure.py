"""The issues a pull request body declares it closes, read as GitHub reads closing keywords.

GitHub acts on a closing keyword only when the pull request merges into the repository's
default branch; item pull requests here target a release branch, so `devops roadmap close`
does the closing from the same links (#743), and readiness checks a body closes one issue.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from devops_cli.config.constants import (
    CONST_ISSUE_CLOSING_KEYWORDS,
)

logger = logging.getLogger(__name__)

# A closing keyword, optional colon, then the issue reference. Matched case-insensitively.
# The owner/repo prefix is captured so a cross-repository link is recognised and skipped
# rather than closing the same-numbered issue in this repository.
_CLOSING_REFERENCE_RE = re.compile(
    r"\b(?P<keyword>[a-z]+)\b\s*:?\s+(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<number>\d+)",
    re.IGNORECASE,
)
# Fenced code blocks and inline code are stripped before scanning: a body that documents
# the syntax, as this project's own docs do, must not be read as a live link.
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# A quoted line is someone else's text, not this author's declaration.
_QUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.MULTILINE)


@dataclass(frozen=True)
class LinkedIssue:
    """An issue a pull request body declares it closes."""

    number: int
    keyword: str


def strip_non_prose(body: str) -> str:
    """Remove code blocks and quoted text before scanning for closing keywords.

    A body that documents the syntax, or quotes a review comment that mentions an issue,
    must not be read as a live declaration; closing an unrelated issue is not recoverable
    by the person who wrote the prose.
    """
    without_fences = _FENCED_CODE_RE.sub(" ", body or "")
    without_inline = _INLINE_CODE_RE.sub(" ", without_fences)
    return _QUOTE_LINE_RE.sub(" ", without_inline)


def extract_linked_issues(body: str, repo: str | None = None) -> list[LinkedIssue]:
    """Extract the issues a pull request body declares it closes.

    Only the keywords GitHub itself honours are accepted, so what this closes is exactly
    what GitHub would have closed had the pull request targeted the default branch. A bare
    `#317`, or a reference qualified with a different repository, is deliberately ignored.
    """
    found: dict[int, str] = {}
    for match in _CLOSING_REFERENCE_RE.finditer(strip_non_prose(body)):
        keyword = match.group("keyword").lower()
        if keyword not in CONST_ISSUE_CLOSING_KEYWORDS:
            continue
        qualifier = match.group("repo")
        if qualifier and repo and qualifier.lower() != repo.lower():
            logger.debug("Ignoring cross-repository closing reference '%s'.", match.group(0))
            continue
        number = int(match.group("number"))
        found.setdefault(number, keyword)
    return [
        LinkedIssue(number=number, keyword=keyword) for number, keyword in sorted(found.items())
    ]


__all__ = ["LinkedIssue", "extract_linked_issues", "strip_non_prose"]
