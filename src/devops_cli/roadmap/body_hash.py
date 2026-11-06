"""The sections and the hashes of the body of an item (#744, #3502).

Refine writes its section into the body of an item, and records the hash of the body outside the
section and the hash of the section in the job record. The hashes show whether a person edited the
item since the record. The trust rule reads them too: the review of an item of a bot approves the
text that the hashes cover, so an approval holds only while the body hashes as recorded.

The module imports no job, so that `trust` and `refine` can both import it.
"""

from __future__ import annotations

import hashlib

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.store import Item, RefineRecordKey


def extract_section_and_outside(
    body: str,
    start_marker: str = CONST_ROADMAP_REFINE_START_MARKER,
    end_marker: str = CONST_ROADMAP_REFINE_END_MARKER,
) -> tuple[str, str | None]:
    """Returns (body_outside_section, section_inside_markers_or_none). The section is the one
    between the two markers, refine's by default; another job's block (#2650) has its own."""
    start_idx = body.find(start_marker)
    if start_idx == -1:
        return body, None
    end_idx = body.find(end_marker, start_idx + len(start_marker))
    if end_idx == -1:
        return body, None

    section_inside = body[start_idx + len(start_marker) : end_idx]
    outside = body[:start_idx] + body[end_idx + len(end_marker) :]
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
