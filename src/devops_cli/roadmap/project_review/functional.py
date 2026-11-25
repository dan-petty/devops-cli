"""Functional change fallback for repositories without OpenSpec (#4730):
`CHANGELOG.md` sections (`Features` and `Bug Fixes` in the first release), then `feat` and `fix`
commit subjects, then `listing.merged_titles` pull request titles, else `skipped`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from pydantic import JsonValue

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.markdown import commonmark_parser
from devops_cli.roadmap.project_review.data import Fact, FactStatus, ReviewWindow
from devops_cli.roadmap.project_review.facts import SECTION
from devops_cli.roadmap.project_review.git_read import commits, log_args, query_text, run_git

FACT_ID: Final = "functional.change"
CHANGELOG_FILE: Final = "CHANGELOG.md"
_CHANGELOG_HEADINGS: Final = frozenset({"Features", "Bug Fixes"})
_CHANGE_TYPES: Final = frozenset({"feat", "fix"})
_UNIT: Final = "changes"
_SOURCE_CHANGELOG: Final = "changelog"
_SOURCE_SUBJECTS: Final = "subjects"
_SOURCE_PULL_REQUESTS: Final = "pull_requests"
_SOURCE_FUNCTIONAL: Final = "functional"
_TITLES_FACT: Final = "listing.merged_titles"


def _token_text(token: Any) -> str:
    """Return plain readable text from one CommonMark inline token."""
    children = getattr(token, "children", None)
    if not children:
        return str(getattr(token, "content", "")).strip()
    parts: list[str] = []
    for child in children:
        if child.type in {"text", "code_inline"}:
            parts.append(child.content)
        elif child.type in {"softbreak", "hardbreak"}:
            parts.append(" ")
    return " ".join("".join(parts).split())


def _first_release_tokens(tokens: Sequence[Any]) -> Sequence[Any]:
    """Slice tokens spanning the first `h2` release section up to the next `h2`."""
    start = next(
        (idx for idx, tok in enumerate(tokens) if tok.type == "heading_open" and tok.tag == "h2"),
        None,
    )
    if start is None:
        return ()
    end = next(
        (
            idx
            for idx in range(start + 1, len(tokens))
            if tokens[idx].type == "heading_open" and tokens[idx].tag == "h2"
        ),
        len(tokens),
    )
    return tokens[start:end]


def _collect_bullets(tokens: Sequence[Any]) -> list[str]:
    """Collect plain text of top-level bullet items within one section slice."""
    items: list[str] = []
    depth = 0
    parts: list[str] = []
    for tok in tokens:
        if tok.type == "bullet_list_open":
            depth += 1
        elif tok.type == "bullet_list_close":
            depth = max(0, depth - 1)
        elif tok.type == "list_item_open" and depth == 1:
            parts = []
        elif tok.type == "list_item_close" and depth == 1:
            entry = " ".join(part for part in parts if part).strip()
            if entry:
                items.append(entry)
        elif depth == 1 and tok.type == "inline":
            parts.append(_token_text(tok))
    return items


def changelog_sections(text: str) -> list[str]:
    """Return bullet items under `### Features` and `### Bug Fixes` of the first `## ` release."""
    release = _first_release_tokens(commonmark_parser().parse(text))
    headings = [
        idx for idx, tok in enumerate(release) if tok.type == "heading_open" and tok.tag == "h3"
    ]
    items: list[str] = []
    for pos, start in enumerate(headings):
        end = headings[pos + 1] if pos + 1 < len(headings) else len(release)
        title = _token_text(release[start + 1]) if start + 1 < end else ""
        if title in _CHANGELOG_HEADINGS:
            items.extend(_collect_bullets(release[start:end]))
    return items


def _fact(
    *,
    status: FactStatus,
    value: list[JsonValue] | None,
    n: int | None,
    source: str,
    query: str,
    reason: str = "",
) -> Fact:
    return Fact(
        id=FACT_ID,
        section=SECTION,
        value=value,
        unit=_UNIT,
        n=n,
        source=source,
        query=query,
        definition=MESSAGES.roadmap.review_fact_definitions[FACT_ID],
        read_at=datetime.now(UTC),
        status=status,
        reason=reason,
    )


def functional_change(checkout: Path, window: ReviewWindow, titles: Sequence[str] = ()) -> Fact:
    """Resolve `functional.change` via CHANGELOG -> feat/fix subjects -> PR titles -> skipped."""
    changelog = checkout / CHANGELOG_FILE
    if changelog.is_file():
        items = changelog_sections(changelog.read_text(encoding="utf-8", errors="replace"))
        if items:
            return _fact(
                status=FactStatus.OK,
                value=list(items),
                n=len(items),
                source=_SOURCE_CHANGELOG,
                query=CHANGELOG_FILE,
            )

    args = log_args(window.base_sha, window.head_sha)
    log_query = query_text(args)
    subjects = [
        commit.subject
        for commit in commits(run_git(checkout, args))
        if commit_type(commit.subject) in _CHANGE_TYPES
    ]
    if subjects:
        return _fact(
            status=FactStatus.OK,
            value=list(subjects),
            n=len(subjects),
            source=_SOURCE_SUBJECTS,
            query=log_query,
        )

    cleaned_titles = [title.strip() for title in titles if title.strip()]
    if cleaned_titles:
        return _fact(
            status=FactStatus.OK,
            value=list(cleaned_titles),
            n=len(cleaned_titles),
            source=_SOURCE_PULL_REQUESTS,
            query=_TITLES_FACT,
        )

    return _fact(
        status=FactStatus.SKIPPED,
        value=None,
        n=None,
        source=_SOURCE_FUNCTIONAL,
        query=log_query,
        reason=MESSAGES.roadmap.review_no_functional_change,
    )
