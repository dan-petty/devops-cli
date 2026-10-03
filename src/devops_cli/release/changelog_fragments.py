"""Changelog fragments: each item's entries in a file of its own, collected at the cut (#933).

Every pull request into a release branch added its entries at the top of `## [Unreleased]` in
`CHANGELOG.md`, so any two open pull requests edited the same lines. Each merge made every other
one conflict, and each then had to be rebased and run CI again. A fragment is
`changelog.d/<issue>.md`, a new file whose name no other pull request uses, holding house-style
entries under Keep a Changelog's `###` categories.

The cut reads every fragment, checks them all before anything is written, and merges their
entries into the version's section: categories in Keep a Changelog order, fragments in issue
order within a category, each fragment's text unchanged.

The release notes read the same text back (#1097): a version's section with its heading, each
category's entries as markdown-it-py's CommonMark parser finds them, and the anchor GitHub gives
the heading, from mdit-py-plugins' anchors plugin, whose slug follows GitHub's.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from functools import cache
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from devops_cli.config.constants import (
    CONST_CHANGELOG_FILENAME,
    CONST_CHANGELOG_FRAGMENT_NAME_RE,
    CONST_CHANGELOG_FRAGMENTS_DIR,
    CONST_KEEP_A_CHANGELOG_CATEGORIES,
    CONST_README_FILENAME,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import ERRORS

if TYPE_CHECKING:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token

# A Markdown ATX heading. Only `### <category>` belongs among entries: a `##` line would open a
# version section of its own once the text is in CHANGELOG.md.
_HEADING_RE = re.compile(r"(?P<hashes>#{1,6})(?:[ \t]+(?P<title>.*?))?[ \t#]*")
_CATEGORY_LIST = ", ".join(f"### {category}" for category in CONST_KEEP_A_CHANGELOG_CATEGORIES)

# Each category's lines, in the order the text gives them.
Categories = dict[str, list[str]]


class ChangelogFragment(NamedTuple):
    """One item's changelog entries, read from `changelog.d/<issue>.md`."""

    path: Path
    issue: int
    categories: Categories


class ChangelogEntry(NamedTuple):
    """One entry of a category: its title lines, the lines below it (its sub-bullets), and its block.

    `block` is markdown-it-py's token type for the block, less `_open`: `list_item` for a list
    entry, else `paragraph`, `heading`, `fence` and so on.
    """

    title: tuple[str, ...]
    details: tuple[str, ...]
    block: str


class ChangelogSection(NamedTuple):
    """A version's section of a changelog: its `## [X.Y.Z] - date` line, then its body."""

    heading: str
    body: str


def _refusal(template: str, source: str, **fields: object) -> ValidationError:
    """The error that stops a cut, naming the file (and line) that is not a changelog entry."""
    message = template.format(path=source, categories=_CATEGORY_LIST, **fields)
    return ValidationError(message, field="changelog", details={"path": source})


def _category(heading: re.Match[str], source: str, line: int) -> str:
    """The Keep a Changelog category a heading opens, raising for any other heading."""
    title = heading["title"] or ""
    if heading["hashes"] == "###" and title in CONST_KEEP_A_CHANGELOG_CATEGORIES:
        return title
    raise _refusal(
        ERRORS.release.changelog_unknown_category, source, line=line, heading=heading[0].strip()
    )


def _trimmed(lines: list[str]) -> list[str]:
    """The lines without the blank lines that part one category from the next."""
    filled = [index for index, line in enumerate(lines) if line.strip()]
    return lines[filled[0] : filled[-1] + 1] if filled else []


def parse_changelog_categories(text: str, source: str, first_line: int = 1) -> Categories:
    """Split house-style changelog text into each category's lines.

    Every non-blank line sits under a `### <category>` heading from Keep a Changelog's set. Text
    before the first heading, or any other heading, raises a ValidationError naming `source`
    and the line, counted from `first_line`.
    """
    categories: Categories = {}
    current: list[str] | None = None
    for number, line in enumerate(text.splitlines(), start=first_line):
        heading = _HEADING_RE.fullmatch(line)
        if heading is not None:
            current = categories.setdefault(_category(heading, source, number), [])
            continue
        if current is None and line.strip():
            raise _refusal(ERRORS.release.changelog_text_outside_category, source, line=number)
        if current is not None:
            current.append(line)
    return {category: _trimmed(lines) for category, lines in categories.items()}


@cache
def _commonmark(anchors: bool = False) -> MarkdownIt:
    """A CommonMark parser; with `anchors`, each heading gets the id GitHub would give it."""
    from markdown_it import MarkdownIt
    from mdit_py_plugins.anchors import anchors_plugin

    parser = MarkdownIt("commonmark")
    return parser.use(anchors_plugin, min_level=1, max_level=6) if anchors else parser


def _entry(lines: Sequence[str], tokens: list[Token], index: int) -> ChangelogEntry | None:
    """The entry a top-level block opens: a list item's first paragraph and the rest, or a block.

    A list holds entries rather than being one, and closing tokens and nested blocks open none.
    """
    token = tokens[index]
    if token.map is None or token.nesting == -1 or token.type.endswith("_list_open"):
        return None
    start, end = token.map
    block = token.type.removesuffix("_open")
    if block != "list_item":
        return ChangelogEntry(tuple(lines[start:end]), (), block) if token.level == 0 else None
    if token.level != 1:
        return None
    first = tokens[index + 1]
    title_end = first.map[1] if first.type == "paragraph_open" and first.map else start + 1
    return ChangelogEntry(
        tuple(lines[start:title_end]), tuple(_trimmed(list(lines[title_end:end]))), block
    )


def parse_changelog_entries(lines: Sequence[str]) -> tuple[ChangelogEntry, ...]:
    """Each entry in a category's lines, as `parse_changelog_categories` gives them.

    An entry is a top-level list item: its title is the item's first paragraph and its details
    the lines below, its sub-bullets. Any other top-level block, such as a heading or a
    paragraph, is an entry of its own with no details.
    """
    tokens = _commonmark().parse("\n".join(lines))
    entries = (_entry(lines, tokens, index) for index in range(len(tokens)))
    return tuple(entry for entry in entries if entry is not None)


def changelog_heading_anchor(heading: str) -> str:
    """The anchor GitHub gives a heading line: `0225---2026-10-03` for `## [0.2.25] - 2026-10-03`."""
    tokens = _commonmark(anchors=True).parse(heading)
    return next((str(token.attrs["id"]) for token in tokens if token.type == "heading_open"), "")


def _read_fragment(path: Path) -> ChangelogFragment:
    """Read one fragment, raising for a misnamed file or one that holds no entry."""
    shown = f"{CONST_CHANGELOG_FRAGMENTS_DIR}/{path.name}"
    named = CONST_CHANGELOG_FRAGMENT_NAME_RE.fullmatch(path.name)
    if named is None or path.is_symlink() or not path.is_file():
        raise _refusal(ERRORS.release.changelog_fragment_misnamed, shown)
    categories = parse_changelog_categories(path.read_text(encoding="utf-8"), shown)
    if not any(categories.values()):
        raise _refusal(ERRORS.release.changelog_fragment_empty, shown)
    return ChangelogFragment(path, int(named["issue"]), categories)


def read_changelog_fragments(directory: Path) -> tuple[ChangelogFragment, ...]:
    """Every fragment in `directory`, in issue order; none when there is no such directory.

    All are checked before any is returned, so a misnamed file, text outside a category or an
    unknown category stops the caller before it writes anything. The README is not a fragment.
    """
    if not directory.is_dir():
        return ()
    paths = sorted(path for path in directory.iterdir() if path.name != CONST_README_FILENAME)
    return tuple(sorted(map(_read_fragment, paths), key=lambda fragment: fragment.issue))


def render_changelog_categories(sources: Sequence[Categories]) -> str:
    """One `###` block per category, in Keep a Changelog order, with each source's lines in turn."""
    blocks = (
        [f"### {category}", *chain.from_iterable(source.get(category, []) for source in sources)]
        for category in CONST_KEEP_A_CHANGELOG_CATEGORIES
    )
    return "\n\n".join("\n".join(block) for block in blocks if len(block) > 1)


def _find_section(changelog: str, name: str) -> re.Match[str] | None:
    """The `## [name]` section of a changelog: its heading line, then its body."""
    return re.search(
        rf"^##\s+\[v?{re.escape(name)}\][^\n]*(?:\n|\Z)(?P<body>.*?)(?=^##\s+\[|\Z)",
        changelog,
        re.MULTILINE | re.DOTALL,
    )


def find_changelog_section(changelog: str, version: str) -> ChangelogSection | None:
    """The `## [version]` section of a changelog (a `v` before the version allowed), or None."""
    section = _find_section(changelog, version)
    if section is None:
        return None
    heading = changelog[section.start() : section.start("body")].rstrip("\n")
    return ChangelogSection(heading, section["body"])


def _merge_into(
    changelog: str, section: re.Match[str], kept: str, heading: str, sources: list[Categories]
) -> str:
    """Replace `section` with `kept` and the version's section, its own entries first."""
    first_line = changelog.count("\n", 0, section.start("body")) + 1
    own = parse_changelog_categories(section["body"], CONST_CHANGELOG_FILENAME, first_line)
    body, rest = render_changelog_categories([own, *sources]), changelog[section.end() :]
    ending = "\n\n" if rest else "\n"
    return changelog[: section.start()] + kept + f"{heading}\n\n{body}{ending}" + rest


def collect_changelog_fragments(
    changelog: str, version: str, today: str, fragments: Sequence[ChangelogFragment]
) -> str | None:
    """`changelog` with the fragments' entries under `## [version] - today`, or None.

    The entries join the version's section when it is already open, else a new section under
    `## [Unreleased]`, which stays as an empty heading, else a new section above the newest
    release; a changelog without any `## [` heading has no place for one, and gets None.
    Entries already under the joined heading come first in each category. `fragments` is not
    empty and is in issue order, as `read_changelog_fragments` returns it.
    """
    heading = f"## [{version}] - {today}"
    sources = [fragment.categories for fragment in fragments]
    opened = _find_section(changelog, version)
    if opened is not None:
        return _merge_into(changelog, opened, "", heading, sources)
    unreleased = _find_section(changelog, "Unreleased")
    if unreleased is not None:
        kept = changelog[unreleased.start() : unreleased.start("body")].rstrip("\n") + "\n\n"
        return _merge_into(changelog, unreleased, kept, heading, sources)
    newest = re.search(r"^##\s+\[", changelog, re.MULTILINE)
    if newest is None:
        return None
    section = f"{heading}\n\n{render_changelog_categories(sources)}\n\n"
    return changelog[: newest.start()] + section + changelog[newest.start() :]
