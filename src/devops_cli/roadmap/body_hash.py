"""The sections and the hashes of the body of an item (#744, #3502).

Refine writes its section into the body of an item, and records the hash of the body outside the
section and the hash of the section in the job record. The hashes show whether a person edited the
item since the record. The trust rule reads them too: the review of an item of a bot approves the
text that the hashes cover, so an approval holds only while the body hashes as recorded.

The module imports no job, so that `trust` and `refine` can both import it.

A job block marker bounds a block only where CommonMark parses the marker as an HTML block of its
own (#6627). A marker that a person quotes in a code span, a code block or a paragraph is the
person's text, so a read keeps it and a write adds its block at the end.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Sequence
from typing import Final

from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.stores.store import Item, RefineRecordKey

# The start and the end markers of the blocks that the jobs write in the body. Each one ends a
# section of the body, because the text of a job block is not text of the section (#6613).
JOB_BLOCK_MARKERS: Final[frozenset[str]] = frozenset(
    {
        CONST_ROADMAP_REFINE_START_MARKER,
        CONST_ROADMAP_REFINE_END_MARKER,
        CONST_ROADMAP_ALTERNATIVES_START_MARKER,
        CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    }
)

# GitHub reads a body as CommonMark: an `html_block` is a real comment, and a code span, a code
# block and a paragraph are other tokens, so a marker that a person quotes there is text.
_BODY_MARKDOWN: Final = MarkdownIt("commonmark")
_LINE_BREAK: Final = re.compile(r"\r\n|\r|\n")


def _line_starts(body: str) -> list[int]:
    """The character offset of the first character of each line of `body`."""
    return [0, *(found.end() for found in _LINE_BREAK.finditer(body))]


def _marker_span(
    body: str, token: Token, starts: Sequence[int], markers: Collection[str]
) -> tuple[str, int, int] | None:
    """The marker, its start and its end in `body`, when `token` is an HTML block that holds one
    of `markers` and nothing else. The span is the text of the marker inside the block, so the
    quote of a blockquote or the indent of a list item stays in the outside text."""
    if token.type != "html_block" or token.map is None:
        return None
    marker = token.content.strip()
    if marker not in markers:
        return None
    first, after = token.map
    block = body[starts[first] : starts[after] if after < len(starts) else len(body)]
    offset = block.find(marker)
    if offset < 0:
        return None
    start = starts[first] + offset
    return marker, start, start + len(marker)


def block_marker_spans(
    body: str, markers: Collection[str] = JOB_BLOCK_MARKERS
) -> list[tuple[str, int, int]]:
    """The marker, its start and its end in `body`, for each marker of `markers` that CommonMark
    parses as an HTML block of its own, in the order of the body (#6627)."""
    starts = _line_starts(body)
    spans = (_marker_span(body, token, starts, markers) for token in _BODY_MARKDOWN.parse(body))
    return [span for span in spans if span is not None]


def job_block_bounds(
    body: str,
    start_marker: str = CONST_ROADMAP_REFINE_START_MARKER,
    end_marker: str = CONST_ROADMAP_REFINE_END_MARKER,
) -> tuple[int, int] | None:
    """The start of the first `start_marker` and the end of the `end_marker` that follows it, each
    an HTML block of its own, or None when the body holds no such pair (#6627)."""
    spans = block_marker_spans(body, (start_marker, end_marker))
    start = next((span for span in spans if span[0] == start_marker), None)
    if start is None:
        return None
    end = next((span for span in spans if span[0] == end_marker and span[1] >= start[2]), None)
    if end is None:
        return None
    return start[1], end[2]


def extract_section_and_outside(
    body: str,
    start_marker: str = CONST_ROADMAP_REFINE_START_MARKER,
    end_marker: str = CONST_ROADMAP_REFINE_END_MARKER,
) -> tuple[str, str | None]:
    """Returns (body_outside_section, section_inside_markers_or_none). The section is the one
    between the two markers, refine's by default; another job's block (#2650) has its own. A
    marker bounds the section only as an HTML block, so a quoted marker pair stays in the
    outside text (#6627)."""
    bounds = job_block_bounds(body, start_marker, end_marker)
    if bounds is None:
        return body, None
    start_idx, end_idx = bounds

    section_inside = body[start_idx + len(start_marker) : end_idx - len(end_marker)]
    outside = body[:start_idx] + body[end_idx:]
    return outside, section_inside


def hash_text(text: str) -> str:
    """SHA-256 hex digest of stripped text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def without_alternatives(body: str) -> str:
    """`body` without the block of the alternatives job (#2650): it is not a person's text."""
    kept, _ = extract_section_and_outside(
        body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
    )
    return kept


def text_of_a_person(body: str) -> str:
    """`body` outside the section of the refine job and the block of the alternatives job: the
    text that a person wrote (#1127)."""
    outside, _ = extract_section_and_outside(without_alternatives(body))
    return outside


def body_hashes(body: str) -> tuple[str, str | None]:
    """The hash of `body` outside its refine section, and the section's, None when it holds none.
    The block of the alternatives job (#2650) is no part of either: it is not a person's text."""
    outside, inside = extract_section_and_outside(without_alternatives(body))
    return hash_text(outside), (hash_text(inside) if inside else None)


def is_unchanged(item: Item, body: str) -> bool:
    """Whether `body` hashes as refine last recorded for `item`, outside the section and in it."""
    recorded = (
        item.job_record.get(RefineRecordKey.BODY_HASH),
        item.job_record.get(RefineRecordKey.SECTION_HASH),
    )
    return body_hashes(body) == recorded
