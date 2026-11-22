"""The sections and the blocks of the body of an item (#744, #3502, #6627).

A job block marker bounds a block only where CommonMark reads the marker as an HTML block of its
own. A marker that a person quotes in a code span, a code block or a paragraph is the person's
text, so a read keeps it and a write adds its block at the end.
"""

from __future__ import annotations

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.body_hash import extract_section_and_outside, without_alternatives

_QUOTED_REFINE = (
    f"A person writes `{CONST_ROADMAP_REFINE_START_MARKER}` and "
    f"`{CONST_ROADMAP_REFINE_END_MARKER}`, with the design text between them."
)
_QUOTED_ALTERNATIVES = (
    f"A person writes `{CONST_ROADMAP_ALTERNATIVES_START_MARKER}` and "
    f"`{CONST_ROADMAP_ALTERNATIVES_END_MARKER}`, with the result between them."
)
_REAL_REFINE_BLOCK = (
    "Intro\n\n"
    f"{CONST_ROADMAP_REFINE_START_MARKER}\n"
    "## Proposed design\n"
    "Proposal text.\n"
    f"{CONST_ROADMAP_REFINE_END_MARKER}\n"
    "\nOutro"
)


def test_a_quoted_marker_pair_is_no_block() -> None:
    """A quoted pair is the text of a person, so a read keeps it and the text between it, and a
    real block whose markers are each on a line of its own is still cut byte for byte."""
    assert (
        extract_section_and_outside(_QUOTED_REFINE),
        without_alternatives(_QUOTED_ALTERNATIVES),
        extract_section_and_outside(_REAL_REFINE_BLOCK),
    ) == (
        (_QUOTED_REFINE, None),
        _QUOTED_ALTERNATIVES,
        ("Intro\n\n\n\nOutro", "\n## Proposed design\nProposal text.\n"),
    )


def test_a_marker_in_a_code_span_a_code_block_or_a_paragraph_is_no_block() -> None:
    """A fenced code block, an indented code block and a paragraph hold a marker as text, and so
    does a code span after a real start marker: each body keeps its text and gives no section."""
    start = CONST_ROADMAP_REFINE_START_MARKER
    end = CONST_ROADMAP_REFINE_END_MARKER
    fenced = f"```\n{start}\n{end}\n```"
    indented = f"    {start}\n    {end}"
    paragraph = f"A paragraph names {start} and {end}."
    quoted_end = f"{start}\n\nA person writes `{end}` here."

    assert (
        extract_section_and_outside(fenced),
        extract_section_and_outside(indented),
        extract_section_and_outside(paragraph),
        extract_section_and_outside(quoted_end),
    ) == ((fenced, None), (indented, None), (paragraph, None), (quoted_end, None))
