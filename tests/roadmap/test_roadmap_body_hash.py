"""The sections and the blocks of the body of an item (#744, #3502, #6627).

A job block marker bounds a block only where CommonMark reads the marker as an HTML block of its
own, or as the whole last line of a comment that the marker ends. A marker that a person quotes in
a code span, a code block or a paragraph is the person's text, so a read keeps it and a write adds
its block at the end.
"""

from __future__ import annotations

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap import body_hash
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


_A_BLOCK = f"{CONST_ROADMAP_REFINE_START_MARKER}\nX\n{CONST_ROADMAP_REFINE_END_MARKER}"


def test_a_marker_that_ends_an_open_comment_of_a_person_bounds_the_block() -> None:
    """CommonMark ends a comment at the first line that holds `-->`. A person opens a comment
    above a job block, so the start marker is the last line of that comment, and it bounds the
    block of refine and of the alternatives job. A marker after other text on that last line is
    the text of the person."""
    head = "Text.\n\n<!-- a note\n\n"
    refine = f"{head}{_A_BLOCK}"
    alternatives = f"{head}{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nX\n{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
    same_line = f"Text.\n\n<!-- a note {_A_BLOCK}"

    assert (
        body_hash.job_block_bounds(refine),
        body_hash.job_block_bounds(
            alternatives,
            CONST_ROADMAP_ALTERNATIVES_START_MARKER,
            CONST_ROADMAP_ALTERNATIVES_END_MARKER,
        ),
        body_hash.job_block_bounds(same_line),
    ) == ((len(head), len(refine)), (len(head), len(alternatives)), None)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Text.\n\n```python\ncode", id="backtick-fence"),
        pytest.param("Text.\n\n~~~~\ncode", id="tilde-fence"),
        pytest.param("Text.\n\n<pre>\ncode", id="pre"),
        pytest.param("Text.\n\n<!-- a note", id="comment"),
        pytest.param("Text.\n\n<?php echo 1;", id="processing-instruction"),
        pytest.param("Text.\n\n<!DOCTYPE html", id="declaration"),
        pytest.param("Text.\n\n<![CDATA[ data", id="cdata"),
    ],
)
def test_an_open_block_is_closed_so_that_a_block_after_it_is_found(text: str) -> None:
    """CommonMark reads all text after an open fenced code block or an open HTML block as part of
    it. The close goes on a line of its own after the text, so a job block after it is found and
    the text stays as it was."""
    closed = body_hash.close_open_block(text)

    assert (
        closed.startswith(f"{text}\n"),
        extract_section_and_outside(f"{closed}\n\n{_A_BLOCK}")[1],
    ) == (True, "\nX\n")


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Text.", id="paragraph"),
        pytest.param("Text.\n\n```\ncode\n```", id="closed-fence"),
        pytest.param("Text.\n\n<pre>\ncode\n</pre>", id="closed-pre"),
        pytest.param("Text.\n\n<div>\ncode", id="div-that-a-blank-line-ends"),
        pytest.param("Text.\n\n    ```\n    indented code", id="indented-code"),
        pytest.param("> ```\n> code in a quote", id="fence-in-a-quote"),
        pytest.param("", id="empty"),
    ],
)
def test_a_text_with_no_open_block_stays_as_it_is(text: str) -> None:
    """A text that holds no open block, or only a block that the blank line before a job block
    ends, gets no close."""
    assert body_hash.close_open_block(text) == text


_AN_ALTERNATIVES_BLOCK = (
    f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nY\n{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
)


@pytest.mark.parametrize(
    ("opened", "close"),
    [
        pytest.param("```\nA fence of a person.", "```", id="fence"),
        pytest.param("<pre>\nA pre block of a person.", "</pre>", id="pre"),
        pytest.param("<?php echo 1;", "?>", id="processing-instruction"),
    ],
)
def test_a_block_that_a_person_leaves_open_ends_at_the_blocks_of_the_jobs(
    opened: str, close: str
) -> None:
    """A person leaves a block open above the refine section and the alternatives block, so it
    runs to the end of the body. The start marker line of the first of these job blocks ends it,
    so each reader finds both blocks in the body, and the outside text holds the close of the block
    on a line of its own before the first marker (#6736)."""
    body = f"Text.\n\n{opened}\n\n{_A_BLOCK}\n\n{_AN_ALTERNATIVES_BLOCK}"
    closed = f"Text.\n\n{opened}\n{close}\n\n{_A_BLOCK}\n\n{_AN_ALTERNATIVES_BLOCK}"
    start, end = body_hash.job_block_bounds(body) or (0, 0)

    assert (
        body[start:end],
        body_hash.close_blocks_before_markers(body),
        extract_section_and_outside(body),
        extract_section_and_outside(
            body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
        )[1],
    ) == (
        _A_BLOCK,
        closed,
        (f"Text.\n\n{opened}\n{close}\n\n\n\n{_AN_ALTERNATIVES_BLOCK}", "\nX\n"),
        "\nY\n",
    )


# A block of the alternatives job that a person quotes in a log.
_A_QUOTED_ALTERNATIVES_BLOCK = (
    f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nQUOTED PERSON LINE\n"
    f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
)
_A_FENCE_IN_THE_SECTION = (
    f"Text.\n\n{CONST_ROADMAP_REFINE_START_MARKER}\nX\n```\nA fence of a person.\n"
    f"{CONST_ROADMAP_REFINE_END_MARKER}\n\n{_AN_ALTERNATIVES_BLOCK}"
)


@pytest.mark.parametrize(
    ("body", "closed", "refine", "alternatives"),
    [
        pytest.param(
            f"Text.\n\nThe log:\n```\n{_A_QUOTED_ALTERNATIVES_BLOCK}\nmore log\n\n"
            f"{_AN_ALTERNATIVES_BLOCK}",
            f"Text.\n\nThe log:\n```\n{_A_QUOTED_ALTERNATIVES_BLOCK}\nmore log\n```\n\n"
            f"{_AN_ALTERNATIVES_BLOCK}",
            None,
            "\nY\n",
            id="quoted-block-above-the-block",
        ),
        pytest.param(
            f"## Problem\nExample:\n\n```\n{CONST_ROADMAP_REFINE_START_MARKER}\nperson text",
            None,
            None,
            None,
            id="lone-refine-start",
        ),
        pytest.param(
            f"Intro\n\n```\nAn open fence.\n\n{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\n"
            "PERSON TEXT\n",
            None,
            None,
            None,
            id="lone-alternatives-start",
        ),
        pytest.param(
            f"Text.\n\n{_A_BLOCK}\n\n```\n{_A_BLOCK}\nmore",
            None,
            "\nX\n",
            None,
            id="quoted-block-after-the-block-of-the-job",
        ),
        pytest.param(
            f"Text.\n\n```\nAn open fence.\n\n{_A_BLOCK}\n\nA note after the block.",
            f"Text.\n\n```\nAn open fence.\n```\n\n{_A_BLOCK}\n\nA note after the block.",
            "\nX\n",
            None,
            id="text-after-the-block",
        ),
        pytest.param(
            _A_FENCE_IN_THE_SECTION,
            _A_FENCE_IN_THE_SECTION.replace(
                f"person.\n{CONST_ROADMAP_REFINE_END_MARKER}",
                f"person.\n```\n\n{CONST_ROADMAP_REFINE_END_MARKER}",
            ),
            "\nX\n```\nA fence of a person.\n```\n\n",
            "\nY\n",
            id="fence-in-the-section",
        ),
    ],
)
def test_a_block_that_a_person_leaves_open_holds_their_quotes_up_to_the_blocks_of_the_jobs(
    body: str, closed: str | None, refine: str | None, alternatives: str | None
) -> None:
    """A block that a person leaves open ends at the job blocks at the end of the body: from that
    line on, the job block marker lines are whole blocks, one for each job at most, and none of a
    job whose block comes before the open block. The end marker of a section that a person opens
    a fence in ends that fence. Each other marker line in the open block is a quote of the person:
    a lone marker, a block that a later block of the same job follows, and a block of a job whose
    block comes first. So no write replaces the text of the person (#6736). `closed` None means
    that the body does not change."""
    assert (
        body_hash.close_blocks_before_markers(body),
        extract_section_and_outside(body)[1],
        extract_section_and_outside(
            body, CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER
        )[1],
    ) == (body if closed is None else closed, refine, alternatives)


def test_a_block_that_a_close_ends_keeps_the_markers_that_it_quotes() -> None:
    """A person quotes a job block in a closed fence and leaves a later fence open. The quote is
    the text of the person, and the open fence holds no job block marker, so the body has no
    block and the text stays as it is (#6736)."""
    body = f"Text.\n\n```\n{_A_BLOCK}\n```\n\n```\nAn open fence."

    assert (
        body_hash.close_blocks_before_markers(body),
        extract_section_and_outside(body),
        body_hash.block_marker_spans(body),
    ) == (body, (body, None), [])
