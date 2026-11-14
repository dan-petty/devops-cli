"""Mark a finding that an open issue of the repository already names (#2346).

AGENTS.md rule 11 asks for an issue for each recurring problem, and a person files one by hand or
through `devops roadmap intake`. The audit must not report that problem as new in every session
after, so a finding whose warning an open issue names is tracked: the report renders it apart from
the findings that no issue holds yet.

A signature and an issue write the same warning in two ways. The signature replaces each path, each
number and each flag value with a placeholder, and it masks a private host name, so it holds no word
that a host names; the issue quotes the warning as the host printed it. The two texts are compared
as words: a placeholder stands for any run of words, the words of the issue are masked as the words
of a signature are, and the words of the signature must appear in the issue in their order. An issue
that quotes the warning matches, and a paraphrase that names other words does not, so a problem
stays new rather than becoming tracked by a text that only looks like it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import replace
from typing import Protocol

from devops_cli.ai.agent_audit.finding import Finding
from devops_cli.ai.agent_audit.transcript import sanitize_text
from devops_cli.roadmap.stores.store import GitHubState, IssueRecord, get_roadmap_store

# The placeholders that a signature writes in place of a path, a number, a flag value and a status
# it does not know (`signature.py`). A placeholder names no word of the problem, so it matches any
# run of the words of an issue.
_PLACEHOLDERS: tuple[str, ...] = ("<path>", "<n>", "<value>", "<unknown>")
_PLACEHOLDER_RE = re.compile("|".join(re.escape(each) for each in _PLACEHOLDERS))
# A word of a warning or of an issue: a run of letters, digits and underscores, in lower case.
_WORD_RE = re.compile(r"\w+")


class TrackedIssues(Protocol):
    """The open issues of a repository, which the audit reads to find the problems a person filed
    (#2346)."""

    def open_issues(self) -> Sequence[IssueRecord]:
        """Every open issue of the repository, with its title and its body."""


class GitHubTrackedIssues:
    """The open issues of `repo`, read through the roadmap store (#2346).

    The store reads every issue of the repository, open and closed, in one listing: no read of it
    gives the open issues alone. The audit filters the state here, and it reads nothing else.
    """

    def __init__(self, repo: str) -> None:
        self._repo = repo

    def open_issues(self) -> Sequence[IssueRecord]:
        """Every open issue of `repo`, with its title and its body."""
        issues = get_roadmap_store(self._repo).issues()
        return tuple(issue for issue in issues if issue.state is GitHubState.OPEN)


def mark_tracked(findings: Iterable[Finding], issues: Iterable[IssueRecord]) -> tuple[Finding, ...]:
    """Each of `findings`, with `tracked` set on the ones that an open issue of `issues` names
    (#2346).

    A finding is tracked when the words of its signature appear, in order, in the title or the body
    of an open issue, with each placeholder of the signature standing for any run of words. A
    finding that no issue names keeps its flag, and so does one that a caller marked as tracked
    already.
    """
    texts = tuple(
        _words_of(f"{issue.title} {issue.body}")
        for issue in issues
        if issue.state is GitHubState.OPEN
    )
    return tuple(_marked(finding, texts) for finding in findings)


def _marked(finding: Finding, texts: Sequence[Sequence[str]]) -> Finding:
    """The finding, marked as tracked when one of `texts` names it."""
    if finding.tracked or not _is_named(finding.signature, texts):
        return finding
    return replace(finding, tracked=True)


def _is_named(signature: str, texts: Sequence[Sequence[str]]) -> bool:
    """Whether one of `texts` holds the words of `signature`, in order."""
    segments = _segments(signature)
    return bool(segments) and any(_holds(text, segments) for text in texts)


def _segments(signature: str) -> tuple[tuple[str, ...], ...]:
    """The runs of words that a placeholder of `signature` separates, with no empty run."""
    return tuple(
        words
        for words in (tuple(_words_of(part)) for part in _PLACEHOLDER_RE.split(signature))
        if words
    )


def _words_of(text: str) -> tuple[str, ...]:
    """The words of a text, in lower case, with each secret, private host and email masked.

    A signature masks a private host name, so the words of an issue are masked the same way: the
    masked host of a signature is the masked host of the issue that quotes the line.
    """
    return tuple(_WORD_RE.findall(sanitize_text(text).lower()))


def _holds(text: Sequence[str], segments: Sequence[Sequence[str]]) -> bool:
    """Whether `text` holds each of `segments` as a run of its words, in their order.

    A segment must appear whole, so a signature of a few words does not match an issue that holds
    the words apart. The run between two segments is free, which is what a placeholder stands for.
    """
    joined = f" {' '.join(text)} "
    position = 0
    for segment in segments:
        needle = f" {' '.join(segment)} "
        found = joined.find(needle, position)
        if found < 0:
            return False
        position = found + len(needle) - 1
    return True


__all__ = ["GitHubTrackedIssues", "TrackedIssues", "mark_tracked"]
