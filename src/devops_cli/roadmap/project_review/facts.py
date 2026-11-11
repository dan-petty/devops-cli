"""The git and lizard facts of a project review window (#4686).

git gives the commits, their Conventional Commit types, the net change between the two trees, the
churn of the commits, the release tags and the hot files. The net change and the churn count
generated files apart: a path that the `.gitattributes` of the head mark `linguist-generated`, as
GitHub reads it. Hot files follow renames (`-M`), so the commits at an old path count for the path
at the head. lizard measures the functions of the hottest files at the base and at the head, from
the blobs of each commit, so the checkout stays as it is.
"""

from __future__ import annotations

import importlib.util
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from packaging.version import InvalidVersion, Version
from pydantic import JsonValue

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.project_review.data import Fact, FactStatus, ReviewWindow
from devops_cli.roadmap.project_review.git_read import (
    Commit,
    FileChange,
    blob_args,
    commits,
    diff_args,
    generated_paths,
    log_args,
    numstat,
    query_text,
    run_git,
    tag_args,
    try_git,
)
from devops_cli.roadmap.project_review.window import Tag, tags_in

_HOTSPOT_ROWS: Final = 20
_COMPLEXITY_FILES: Final = 10
_NO_TYPE: Final = "other"
_LIZARD: Final = "lizard"
_LIZARD_LANGUAGES: Final = "lizard_languages"


@dataclass
class Hotspot:
    """The commits and lines of one path, with the older paths that git found as renames."""

    path: str
    commits: int = 0
    added: int = 0
    deleted: int = 0
    renamed_from: list[str] = field(default_factory=list)

    def row(self) -> dict[str, JsonValue]:
        return {
            "path": self.path,
            "commits": self.commits,
            "added": self.added,
            "deleted": self.deleted,
            "renamed_from": list(self.renamed_from),
        }


def hotspots(found: Sequence[Commit]) -> list[Hotspot]:
    """The paths of the commits (newest first), each under its newest name, most commits first.

    A rename maps its old path to the newest name of its new path, so an older commit at the old
    path counts for the same row."""
    newest: dict[str, str] = {}
    rows: dict[str, Hotspot] = {}
    for commit in found:
        touched: set[str] = set()
        for change in commit.changes:
            name = newest.get(change.path, change.path)
            row = rows.setdefault(name, Hotspot(name))
            if change.old_path is not None:
                newest[change.old_path] = name
                if change.old_path not in row.renamed_from:
                    row.renamed_from.append(change.old_path)
            row.added += change.added
            row.deleted += change.deleted
            touched.add(name)
        for name in touched:
            rows[name].commits += 1
    return sorted(
        rows.values(), key=lambda row: (-row.commits, -(row.added + row.deleted), row.path)
    )


def _lines(changes: Iterable[FileChange], paths: set[str]) -> dict[str, JsonValue]:
    """The files, added lines and deleted lines of the changes."""
    counted = list(changes)
    return {
        "files": len(paths),
        "added": sum(change.added for change in counted),
        "deleted": sum(change.deleted for change in counted),
    }


def _split(changes: Sequence[FileChange], generated: frozenset[str]) -> dict[str, JsonValue]:
    """All the lines of the changes, and the lines of the generated paths apart."""
    made = [change for change in changes if change.path in generated]
    return {
        "all": _lines(changes, {change.path for change in changes}),
        "generated": _lines(made, {change.path for change in made}),
    }


def _release_kind(name: str) -> str:
    try:
        version = Version(name)
    except InvalidVersion:
        return _NO_TYPE
    if version.micro:
        return "patch"
    return "minor" if version.minor else "major"


class _Facts:
    """Builds facts, each with its source, its definition and the time of its read."""

    def ok(self, fact_id: str, value: JsonValue, unit: str, n: int | None, query: str) -> Fact:
        source = fact_id.partition(".")[0]
        definition = MESSAGES.roadmap.review_fact_definitions[fact_id]
        return Fact(
            id=fact_id,
            value=value,
            unit=unit,
            n=n,
            source=source,
            query=query,
            definition=definition,
            read_at=datetime.now(UTC),
            status=FactStatus.OK,
        )

    def not_ok(self, fact_id: str, unit: str, query: str, status: FactStatus, reason: str) -> Fact:
        return Fact(
            id=fact_id,
            value=None,
            unit=unit,
            n=None,
            source=fact_id.partition(".")[0],
            query=query,
            definition=MESSAGES.roadmap.review_fact_definitions[fact_id],
            read_at=datetime.now(UTC),
            status=status,
            reason=reason,
        )


def git_facts(
    checkout: Path, window: ReviewWindow, tags: Sequence[Tag]
) -> tuple[list[Fact], list[Hotspot]]:
    """The git facts of the window, and its hot files for the complexity reader."""
    facts = _Facts()
    base, head = window.base_sha, window.head_sha
    log, diff = log_args(base, head), diff_args(base, head)
    found = commits(run_git(checkout, log))
    tree = numstat(run_git(checkout, diff))
    changes = [change for commit in found for change in commit.changes]
    generated = generated_paths(checkout, head, {c.path for c in (*changes, *tree)})
    types = Counter(commit_type(commit.subject) or _NO_TYPE for commit in found)
    rows = [row for row in hotspots(found) if row.path not in generated]
    released = tags_in(tags, window.start, window.end)
    kinds = Counter(_release_kind(tag.name) for tag in released)
    log_query, tag_query = query_text(log), query_text(tag_args())
    result = [
        facts.ok("git.commits", len(found), "commits", len(found), log_query),
        facts.ok("git.commit_types", dict(types.most_common()), "commits", len(found), log_query),
        facts.ok("git.net_change", _split(tree, generated), "lines", len(tree), query_text(diff)),
        facts.ok("git.churn", _split(changes, generated), "lines", len(found), log_query),
        facts.ok("git.releases", dict(sorted(kinds.items())), "tags", len(released), tag_query),
        facts.ok(
            "git.release_tags",
            [{"tag": tag.name, "created": tag.created.isoformat()} for tag in released],
            "tags",
            len(released),
            tag_query,
        ),
        facts.ok(
            "git.hotspots",
            [row.row() for row in rows[:_HOTSPOT_ROWS]],
            "commits",
            len(rows),
            log_query,
        ),
    ]
    return result, rows


def _measure(lizard: Any, path: str, text: str | None) -> dict[str, JsonValue] | None:
    """The functions of one blob as lizard reads them, or None when the commit has no blob."""
    if text is None:
        return None
    functions = lizard.analyze_file.analyze_source_code(path, text).function_list
    ccn = [function.cyclomatic_complexity for function in functions]
    return {"functions": len(ccn), "ccn_max": max(ccn, default=0), "ccn_sum": sum(ccn)}


def complexity_fact(checkout: Path, window: ReviewWindow, rows: Sequence[Hotspot]) -> Fact:
    """The functions and the cyclomatic complexity of the hottest files that lizard reads, at the
    base and at the head. A path that git renamed in the window is read under its old name at the
    base."""
    facts = _Facts()
    query = query_text(blob_args("<commit>", "<path>"))
    if importlib.util.find_spec(_LIZARD) is None:
        reason = MESSAGES.roadmap.review_lizard_missing
        return facts.not_ok("lizard.complexity", "ccn", query, FactStatus.SKIPPED, reason)
    # lizard ships no type information, so the review loads it by name.
    lizard = importlib.import_module(_LIZARD)
    lizard_languages = importlib.import_module(_LIZARD_LANGUAGES)
    read = [row for row in rows if lizard_languages.get_reader_for(row.path) is not None]
    measured: list[JsonValue] = []
    for row in read[:_COMPLEXITY_FILES]:
        base_path = row.renamed_from[-1] if row.renamed_from else row.path
        base = try_git(checkout, blob_args(window.base_sha, base_path))
        head = try_git(checkout, blob_args(window.head_sha, row.path))
        measured.append(
            {
                "path": row.path,
                "base": _measure(lizard, base_path, base),
                "head": _measure(lizard, row.path, head),
            }
        )
    return facts.ok("lizard.complexity", measured, "ccn", len(measured), query)


def review_facts(checkout: Path, window: ReviewWindow, tags: Sequence[Tag]) -> list[Fact]:
    """Every fact of the window: the git facts, then the complexity of the hot files."""
    found, rows = git_facts(checkout, window, tags)
    return [*found, complexity_fact(checkout, window, rows)]
