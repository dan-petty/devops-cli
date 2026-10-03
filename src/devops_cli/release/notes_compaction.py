"""Release notes that fit GitHub's body limits (#1097).

`release.yml` publishes each GitHub Release with `devops release notes --raw` as its body, and
`devops release pr` puts the same notes in the release pull request. GitHub refuses a Release
body over 125,000 characters and a pull request body over 65,536, and v0.2.25's section ran to
196,525. Notes that fit are left alone. Longer notes keep every `###` category and each entry's
title, drop the entries' sub-bullets, and end with a pointer to the full section in
`CHANGELOG.md`. If even the titles do not fit, they are cut at the last whole entry, with a line
counting the entries left out. Entries are read with the changelog parser the cut uses; notes
it refuses, such as a commit log, go by their own headings and blocks.
"""

from __future__ import annotations

from bisect import bisect_right

from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.release.changelog_fragments import (
    ChangelogEntry,
    parse_changelog_categories,
    parse_changelog_entries,
)

# A heading, or None for the blocks above the first one, and the entries below it.
_Section = tuple[str | None, tuple[ChangelogEntry, ...]]


def _by_heading(heading: str | None, entries: tuple[ChangelogEntry, ...]) -> list[_Section]:
    """`entries` under `heading`, a section of their own after each heading among them."""
    sections: list[tuple[str | None, list[ChangelogEntry]]] = [(heading, [])]
    for entry in entries:
        if entry.block == "heading":
            sections.append(("\n".join(entry.title), []))
        else:
            sections[-1][1].append(entry)
    return [(name, tuple(kept)) for name, kept in sections if name is not None or kept]


def _sections(notes: str) -> list[_Section]:
    """The notes' categories and their entries; notes no category holds go by their headings."""
    try:
        categories = parse_changelog_categories(notes, "release notes")
    except ValidationError:
        return _by_heading(None, parse_changelog_entries(notes.splitlines()))
    return [
        section
        for name, lines in categories.items()
        for section in _by_heading(f"### {name}", parse_changelog_entries(lines))
    ]


def _titles(section: _Section) -> str:
    """A section's heading, if it has one, over its entries' title lines.

    Consecutive list items share a list; any other block stands apart, so a paragraph after an
    item does not continue it.
    """
    heading, entries = section
    parts = [heading] if heading else []
    for previous, entry in zip((None, *entries), entries, strict=False):
        listed = entry.block == "list_item" and (previous is None or previous.block == entry.block)
        if parts:
            parts.append("\n" if listed else "\n\n")
        parts.append("\n".join(entry.title))
    return "".join(parts)


def _render(sections: list[_Section], *footer: str) -> str:
    """Each section's titles, then the footer paragraphs."""
    blocks = (block for block in map(_titles, sections) if block)
    return "\n\n".join([*blocks, *footer])


def _first_entries(sections: list[_Section], count: int) -> list[_Section]:
    """The sections up to the one holding entry number `count`, with only the first `count`."""
    kept: list[_Section] = []
    for heading, entries in sections:
        if count == 0:
            break
        kept.append((heading, entries[:count]))
        count -= len(kept[-1][1])
    return kept


def fit_release_notes(notes: str, budget: int, full_notes: str) -> str:
    """`notes` when they fit in `budget` characters, else their titles and `full_notes`.

    `full_notes` names where the full notes are, such as a Markdown link to the version's
    section of `CHANGELOG.md`. The pointer to it is never cut, so a budget too small for it
    gets the count of entries left out and the pointer alone.
    """
    if len(notes) <= budget:
        return notes
    sections = _sections(notes)
    pointer = MESSAGES.release.notes_full_notes.format(full_notes=full_notes)
    if any(entry.details for _, entries in sections for entry in entries):
        pointer = f"{MESSAGES.release.notes_details_left_out} {pointer}"
    compact = _render(sections, pointer)
    if len(compact) <= budget:
        return compact
    total = sum(len(entries) for _, entries in sections)

    def cut_at(count: int) -> str:
        left_out = MESSAGES.release.notes_entries_left_out.format(count=total - count)
        return _render(_first_entries(sections, count), left_out, pointer)

    fitting = bisect_right(range(total), budget, key=lambda count: len(cut_at(count)))
    return cut_at(max(fitting - 1, 0))
