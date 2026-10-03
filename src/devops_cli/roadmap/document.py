"""A hand-written `docs/ROADMAP.md` read as data, for its one-time migration onto GitHub.

The file's grammar is this repository's own: headings, top-level checkbox entries whose bold
title ends in a `(P1 - High, Issue #739)` parenthetical, and the Value vs. Effort matrix as a
Markdown table. Every heading counts, range and `####` headings included. An entry belongs to
the nearest heading above it, and to that heading's release when the heading names exactly one
version; entries under any other heading are backlog entries.

An entry is linked to an issue when its heading names the issue, or when exactly one issue's
title equals the entry's title once both drop a conventional-commit prefix and fold case and
whitespace. Nothing is matched by keyword or similarity.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_ROADMAP_ISSUE_TAGS,
    CONST_ROADMAP_MATRIX_COMPLETED_STATUS,
    CONST_ROADMAP_MATRIX_EFFORT_COLUMN,
    CONST_ROADMAP_MATRIX_FEATURE_COLUMN,
    CONST_ROADMAP_MATRIX_REJECTED_STATUS,
    CONST_ROADMAP_MATRIX_STATUS_COLUMN,
    CONST_ROADMAP_MATRIX_VALUE_COLUMN,
    CONST_ROADMAP_NOT_BUILDING_MARKER,
    CONST_ROADMAP_OVERLAP_TAG,
)
from devops_cli.roadmap.store import IssueRecord

_HEADING = re.compile(r"^#{1,6}\s+(?P<text>.+?)\s*$")
_ENTRY = re.compile(r"^- \[(?P<mark>[ xX])\] \*\*(?P<bold>.+?)\*\*")
_VERSION = re.compile(r"\bv\d+\.\d+\.\d+\b")
_PRIORITY_SUFFIX = re.compile(r"^(?P<title>.*?)\s*\((?P<tags>(?P<priority>P[0-3])\s*-[^()]*)\)$")
_TAG = re.compile(r"(?P<tag>[A-Za-z]+)\s+(?P<numbers>#\d+(?:\s*,\s*#\d+)*)")
_ISSUE_NUMBER = re.compile(r"#(\d+)")
_TABLE_SEPARATOR = re.compile(r"^\|\s*:?-{3,}")
_TABLE_CELL_SPLIT = re.compile(r"(?<!\\)\|")
# A conventional-commit header: a lower-case type, an optional scope and `!`, then `: `.
_CONVENTIONAL_PREFIX = re.compile(r"^[a-z]+(?:\([^()]*\))?!?:\s+")


class RoadmapEntry(BaseModel):
    """One top-level checkbox entry, with where it sits and what its heading names."""

    model_config = ConfigDict(frozen=True)

    line: int
    title: str
    done: bool
    priority: str | None = None
    issues: tuple[int, ...] = ()
    overlaps: tuple[int, ...] = ()
    section: str = ""
    release: str | None = None
    text: str = ""

    @property
    def not_building(self) -> bool:
        """Whether the heading records the entry as investigated and not built."""
        return CONST_ROADMAP_NOT_BUILDING_MARKER in self.title


class MatrixRow(BaseModel):
    """One row of the Value vs. Effort matrix."""

    model_config = ConfigDict(frozen=True)

    line: int
    feature: str
    value: str
    effort: str
    status: str
    text: str

    @property
    def rejected(self) -> bool:
        """Whether the row is marked rejected."""
        return self.status.startswith(CONST_ROADMAP_MATRIX_REJECTED_STATUS)

    @property
    def open(self) -> bool:
        """Whether the row is neither delivered nor rejected."""
        return not (self.rejected or self.status.startswith(CONST_ROADMAP_MATRIX_COMPLETED_STATUS))


class RoadmapDocument(BaseModel):
    """Every entry and matrix row of the file, in file order."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[RoadmapEntry, ...] = ()
    matrix: tuple[MatrixRow, ...] = ()


def normalize_title(title: str) -> str:
    """A title without its conventional-commit prefix, with case and whitespace folded."""
    return " ".join(_CONVENTIONAL_PREFIX.sub("", title.strip(), count=1).split()).casefold()


def _release_of(heading: str) -> str | None:
    """The release a heading names: its one version, or None for a range or no version."""
    versions = _VERSION.findall(heading)
    return versions[0] if len(versions) == 1 else None


def _tagged(tags: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The issue numbers and overlapped item numbers a heading's parenthetical names."""
    named = [
        (match["tag"], int(number))
        for match in _TAG.finditer(tags)
        for number in _ISSUE_NUMBER.findall(match["numbers"])
    ]
    issues = tuple(number for tag, number in named if tag in CONST_ROADMAP_ISSUE_TAGS)
    overlaps = tuple(number for tag, number in named if tag == CONST_ROADMAP_OVERLAP_TAG)
    return issues, overlaps


def _entry(match: re.Match[str], lines: Sequence[str], line: int, section: str) -> RoadmapEntry:
    """The entry `match` found heading `lines`, at 1-based `line` under `section`."""
    bold = match["bold"].strip()
    suffix = _PRIORITY_SUFFIX.match(bold)
    issues, overlaps = _tagged(suffix["tags"]) if suffix else ((), ())
    return RoadmapEntry(
        line=line,
        title=suffix["title"] if suffix else bold,
        done=match["mark"] != " ",
        priority=suffix["priority"] if suffix else None,
        issues=issues,
        overlaps=overlaps,
        section=section,
        release=_release_of(section),
        text="\n".join(lines).rstrip(),
    )


def _entry_extent(lines: Sequence[str], start: int) -> int:
    """The index just past the entry starting at `start`: its indented and blank lines follow it."""
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end][:1].isspace()):
        end += 1
    return end


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in _TABLE_CELL_SPLIT.split(row.strip().strip("|"))]


def _matrix_rows(lines: Sequence[str], header: int) -> Iterator[MatrixRow]:
    """The rows of the table whose header is at `header`, when it is the Value vs. Effort matrix."""
    columns = _cells(lines[header])
    wanted = (
        CONST_ROADMAP_MATRIX_FEATURE_COLUMN,
        CONST_ROADMAP_MATRIX_VALUE_COLUMN,
        CONST_ROADMAP_MATRIX_EFFORT_COLUMN,
        CONST_ROADMAP_MATRIX_STATUS_COLUMN,
    )
    if not all(column in columns for column in wanted):
        return
    at = [columns.index(column) for column in wanted]
    for index in range(header + 2, len(lines)):
        if not lines[index].startswith("|"):
            return
        cells = _cells(lines[index])
        if len(cells) == len(columns):
            feature, value, effort, status = (cells[i] for i in at)
            yield MatrixRow(
                line=index + 1,
                feature=feature,
                value=value,
                effort=effort,
                status=status,
                text=lines[index],
            )


def _is_table_header(lines: Sequence[str], index: int) -> bool:
    return (
        lines[index].startswith("|")
        and index + 1 < len(lines)
        and bool(_TABLE_SEPARATOR.match(lines[index + 1]))
    )


def parse_roadmap(text: str) -> RoadmapDocument:
    """Every entry and matrix row of a hand-written roadmap file."""
    lines = text.splitlines()
    entries: list[RoadmapEntry] = []
    matrix: list[MatrixRow] = []
    section = ""
    index = 0
    while index < len(lines):
        heading = _HEADING.match(lines[index])
        entry = _ENTRY.match(lines[index])
        if heading:
            section = heading["text"]
        elif entry:
            end = _entry_extent(lines, index)
            entries.append(_entry(entry, lines[index:end], index + 1, section))
            index = end
            continue
        elif _is_table_header(lines, index):
            matrix.extend(_matrix_rows(lines, index))
        index += 1
    return RoadmapDocument(entries=tuple(entries), matrix=tuple(matrix))


def titles_index(issues: Iterable[IssueRecord]) -> dict[str, list[int]]:
    """Every issue's number under its normalized title; pull requests are not issues."""
    index: dict[str, list[int]] = defaultdict(list)
    for issue in issues:
        if not issue.pull_request:
            index[normalize_title(issue.title)].append(issue.number)
    return dict(index)


def title_match(title: str, titles: dict[str, list[int]]) -> int | None:
    """The one issue whose normalized title equals `title`'s, or None for none or several."""
    matches = titles.get(normalize_title(title), [])
    return matches[0] if len(matches) == 1 else None


def linked_issues(entry: RoadmapEntry, titles: dict[str, list[int]]) -> tuple[int, ...]:
    """The issues an entry is linked to: those its heading names, else its one title match."""
    if entry.issues:
        return entry.issues
    match = title_match(entry.title, titles)
    return (match,) if match is not None else ()


__all__ = [
    "MatrixRow",
    "RoadmapDocument",
    "RoadmapEntry",
    "linked_issues",
    "normalize_title",
    "parse_roadmap",
    "title_match",
    "titles_index",
]
