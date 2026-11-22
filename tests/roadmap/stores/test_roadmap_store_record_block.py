"""The record block after a body that leaves a block open (#6729), and below a block that a person
opens above it (#6785).

`with_record` writes the record block as a comment after the body, and `split_record` reads it
as the last block of the body. CommonMark reads all text after an open fenced code block or
an open HTML block as part of that block. So the write closes such a block first. The record
then stays the last block, and GitHub shows no record text in the code of the person. A person
can later open a block above the record. The read then ends that block at the record line, and
the next write closes the block before the record.
"""

from __future__ import annotations

import logging

import pytest
from hypothesis import given
from hypothesis import strategies as st
from markdown_it import MarkdownIt

from devops_cli.config.constants import (
    CONST_ROADMAP_RECORD_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.body_hash import body_hashes, extract_section_and_outside, job_block_bounds
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    RefineRecordKey,
    encode_job_record,
    split_record,
    with_record,
)

RECORD = {ImplementRecordKey.STOPPED.value: "group 1"}
BLOCK = encode_job_record({}, RECORD)
NEXT_RECORD = {**RECORD, RefineRecordKey.BODY_HASH.value: "b1"}
NEXT_BLOCK = encode_job_record(RECORD, {RefineRecordKey.BODY_HASH: "b1"})

# A body that ends in an open block, and the body that a read gives back after the write: the
# body with its close on a line of its own. The close takes the place of one line break at the
# end, so the code of the block gets no new empty line.
OPEN_BLOCKS = {
    "backtick-fence": ("Text.\n\n```python\nx = 1", "Text.\n\n```python\nx = 1\n```"),
    "tilde-fence": ("Text.\n\n~~~~\nx = 1\n", "Text.\n\n~~~~\nx = 1\n~~~~"),
    "comment": ("Text.\n\n<!-- a note", "Text.\n\n<!-- a note\n-->"),
    "pre": ("Text.\n\n<pre>\nx = 1\r\n", "Text.\n\n<pre>\nx = 1\n</pre>"),
}

NO_OPEN_BLOCKS = {
    "paragraph": "Text.",
    "line-break-at-the-end": "Text.\n",
    "closed-fence": "Text.\n\n```\ncode\n```",
    "closed-pre": "Text.\n\n<pre>\ncode\n</pre>",
    "closed-comment": "Text.\n\n<!-- a note -->",
    "div-that-a-blank-line-ends": "Text.\n\n<div>\ncode",
    "fence-in-a-quote": "> ```\n> code in a quote",
    "indented-code": "Text.\n\n    indented code",
    "empty": "",
}


@pytest.mark.parametrize(("body", "read_back"), OPEN_BLOCKS.values(), ids=OPEN_BLOCKS.keys())
def test_a_record_after_an_open_block_reads_back(body: str, read_back: str) -> None:
    """The record block is the last block of the body that the write gives, so the read finds
    the record, and the body that it gives back is the body with the close of its block."""
    assert split_record(with_record(body, BLOCK)) == (read_back, RECORD)


@pytest.mark.parametrize("body", NO_OPEN_BLOCKS.values(), ids=NO_OPEN_BLOCKS.keys())
def test_a_body_with_no_open_block_is_written_as_before(body: str) -> None:
    """A body that leaves no block open, or only a block that the blank line before the record
    ends, gets no close: the write gives the same text as before, and the read gives the body."""
    written = with_record(body, BLOCK)
    assert (written, split_record(written)) == (
        f"{body}\n\n{BLOCK}" if body else BLOCK,
        (body, RECORD),
    )


@pytest.mark.parametrize(("body", "read_back"), OPEN_BLOCKS.values(), ids=OPEN_BLOCKS.keys())
def test_a_second_record_write_keeps_the_body_and_its_hashes(body: str, read_back: str) -> None:
    """The close changes the text of the person one time. A second write of the record to the
    body that the read gave back writes that body again, so its body hash stays the same and a
    job that compares the hash sees no new change."""
    first, _ = split_record(with_record(body, BLOCK))
    second, held = split_record(with_record(first, NEXT_BLOCK))
    assert (second, body_hashes(second), held) == (read_back, body_hashes(first), NEXT_RECORD)


@pytest.mark.parametrize("end", ["\n", "\n\n", "\r\n"], ids=["one", "two", "crlf"])
def test_the_code_of_an_open_fence_keeps_its_rendered_form(end: str) -> None:
    """The close of a fence adds no empty line to the code of a body that ends in line breaks,
    so CommonMark renders the body that the read gives back as it renders the body alone. The
    backtick case of `OPEN_BLOCKS` holds a body with no line break at its end."""
    body = f"Text.\n\n```python\nx = 1{end}"
    render = MarkdownIt("commonmark").render
    assert render(split_record(with_record(body, BLOCK))[0]) == render(body)


_LINES = st.sampled_from(
    [
        "Text.",
        "",
        "```",
        "```python",
        "~~~~",
        "<!-- a note",
        "-->",
        "<pre>",
        "</pre>",
        "<script>",
        "<?php",
        "<!DOCTYPE html",
        "<![CDATA[ data",
        "<div>",
        "> quote",
        "> ```",
        "- item",
        "  ```",
        "    indented",
    ]
)


@given(st.lists(_LINES, max_size=12), st.sampled_from(["", "\n", "\r\n"]))
def test_every_record_write_reads_back_and_a_second_write_keeps_the_body(
    lines: list[str], end: str
) -> None:
    """For a body of any of these lines, the read finds the record of each write, and a second
    write gives the body of the first."""
    body = "\n".join(lines) + end
    first, held = split_record(with_record(body, BLOCK))
    second, held_next = split_record(with_record(first, NEXT_BLOCK))
    assert (held, second, held_next) == (RECORD, first, NEXT_RECORD)


# The refine block at the end of a block that a person opened above it and left open. The
# readers end such an open block at the job blocks at its end (#6736).
_JOB_BLOCK = f"{CONST_ROADMAP_REFINE_START_MARKER}\nThe section.\n{CONST_ROADMAP_REFINE_END_MARKER}"
JOB_BLOCKS_IN_AN_OPEN_BLOCK = {
    "fence": f"Text.\n\n```\ncode\n\n{_JOB_BLOCK}",
    "pre": f"Text.\n\n<pre>\ncode\n\n{_JOB_BLOCK}",
}


@pytest.mark.parametrize(
    "body", JOB_BLOCKS_IN_AN_OPEN_BLOCK.values(), ids=JOB_BLOCKS_IN_AN_OPEN_BLOCK.keys()
)
def test_a_record_write_keeps_a_job_block_in_an_open_block_readable(body: str) -> None:
    """The write closes the open block before the job block, not after it. So the read of the
    written body finds the job block where the read of the body finds it, and the record too."""
    written, held = split_record(with_record(body, BLOCK))
    section = extract_section_and_outside(body)[1]
    assert (
        section,
        job_block_bounds(written) is not None,
        extract_section_and_outside(written)[1],
        held,
    ) == ("\nThe section.\n", True, section, RECORD)


# A body that a job wrote, and the opener of a block that a person then puts above "More text."
# and does not close. CommonMark reads the record as part of that block. A fence and a `<pre>`
# block run to the end of the body. A comment ends at the record line, the first line that holds
# `-->`.
_WRITTEN = with_record("Text.\n\nMore text.", BLOCK)
OPENED_BLOCKS = {
    "backtick-fence": "```python",
    "tilde-fence": "~~~~",
    "pre": "<pre>",
    "comment": "<!-- a note",
}
_RENDER = MarkdownIt("commonmark").render
_BLOCKS = MarkdownIt("commonmark").disable("inline")


def _opened(opener: str, line_break: str) -> str:
    """`_WRITTEN` with `opener` on a line of its own above "More text.", with `line_break`
    between the lines, as the web editor of GitHub sends `\r\n`."""
    return _WRITTEN.replace("More text.", f"{opener}\nMore text.").replace("\n", line_break)


@pytest.mark.parametrize("line_break", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("opener", OPENED_BLOCKS.values(), ids=OPENED_BLOCKS.keys())
def test_a_record_below_a_block_that_a_person_opens_reads_back(
    opener: str, line_break: str
) -> None:
    """The record line at the end of the body ends the block that the person opened above it. So
    the read gives the record, and the body of the person without the record block."""
    person = f"Text.\n\n{opener}\nMore text.".replace("\n", line_break)
    assert split_record(_opened(opener, line_break)) == (person, RECORD)


@pytest.mark.parametrize("line_break", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("opener", OPENED_BLOCKS.values(), ids=OPENED_BLOCKS.keys())
def test_the_next_write_closes_the_block_that_a_person_opens_before_the_record(
    opener: str, line_break: str
) -> None:
    """The next write closes the block of the person before the record (`closed_body`). So
    CommonMark parses the record of the written body as its last HTML block. The body holds one
    record block with the keys of the old record."""
    person, held = split_record(_opened(opener, line_break))
    written = with_record(person, encode_job_record(held, {RefineRecordKey.BODY_HASH: "b1"}))
    last = [token for token in _BLOCKS.parse(written) if token.level == 0][-1]
    assert (
        (last.type, last.content.strip()),
        written.count(CONST_ROADMAP_RECORD_MARKER),
        split_record(written)[1],
    ) == (("html_block", NEXT_BLOCK), 1, NEXT_RECORD)


@pytest.mark.parametrize("line_break", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("opener", ["```python", "~~~~"], ids=["backtick-fence", "tilde-fence"])
def test_the_code_of_a_fence_that_a_person_opens_keeps_its_rendered_form(
    opener: str, line_break: str
) -> None:
    """Until the next write, GitHub shows the record line as code of the fence. The next write
    closes the fence after the lines of the person. So CommonMark renders the code as the lines of
    the person, each with its line break, and the record lines leave the code. An HTML block
    renders as its own text, so only its close is new in the HTML."""
    lines = f"Text.\n\n{opener}\nMore text.\n".replace("\n", line_break)
    person, held = split_record(_opened(opener, line_break))
    written = with_record(person, encode_job_record(held, {RefineRecordKey.BODY_HASH: "b1"}))
    assert _RENDER(split_record(written)[0]) == _RENDER(lines)


def test_a_fence_above_the_job_block_and_the_record_leaves_no_stale_record() -> None:
    """A person opens a fence above the refine block and the record. The read gives the old
    record, so the next write takes it out. The body then holds one record block, with the keys of
    the old record. A read finds the section of the refine block."""
    edited = with_record(f"Text.\n\n{_JOB_BLOCK}", BLOCK).replace("Text.", "Text.\n\n```")
    person, held = split_record(edited)
    written = with_record(person, encode_job_record(held, {RefineRecordKey.BODY_HASH: "b1"}))
    assert (
        held,
        written.count(CONST_ROADMAP_RECORD_MARKER),
        split_record(written)[1],
        extract_section_and_outside(split_record(written)[0])[1],
    ) == (RECORD, 1, NEXT_RECORD, "\nThe section.\n")


QUOTES_ON_THE_LAST_LINE = {
    "not-json": f"Example:\n\n```text\n<!-- {CONST_ROADMAP_RECORD_MARKER} {{...}} -->",
    "not-an-object": f"Example:\n\n```text\n<!-- {CONST_ROADMAP_RECORD_MARKER} [1] -->",
    "indented": f"Example:\n\n```text\n    {BLOCK}",
    "in-a-list-item": f"- item\n\n  {BLOCK}",
}


@pytest.mark.parametrize(
    "body", QUOTES_ON_THE_LAST_LINE.values(), ids=QUOTES_ON_THE_LAST_LINE.keys()
)
def test_a_quote_on_the_last_line_stays_the_text_of_the_person(
    body: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A job writes the record with no indent and with a JSON object. The record line is the last
    line of a block only when the text before it leaves that block open. So these quotes of the
    record format on the last line stay in the body, read as no record and log no warning. The
    first two hold no JSON object. CommonMark does not parse the third alone as an HTML block.
    The text before the fourth leaves no block open."""
    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.stores.store"):
        found = split_record(body)
    assert (found, caplog.messages) == ((body, {}), [])


def test_a_quote_with_a_json_object_in_an_open_block_reads_as_the_record() -> None:
    """CommonMark cannot tell this quote from a record below a block that a person opens. So the
    read gives the JSON object of the quote as the record. The next write closes the fence of the
    person before the record block."""
    person, held = split_record(f"Example:\n\n```text\n{encode_job_record({}, {'quote': 'x'})}")
    assert (person, held, with_record(person, BLOCK)) == (
        "Example:\n\n```text\n",
        {"quote": "x"},
        f"Example:\n\n```text\n```\n\n{BLOCK}",
    )


_OPENERS = st.sampled_from(["```", "~~~~", "<pre>", "<!-- a note", "<script>", "<?php"])


@given(st.lists(_LINES, max_size=12), st.sampled_from(["", "\n", "\r\n"]), _OPENERS, st.data())
def test_a_block_that_a_person_opens_on_any_line_keeps_the_record(
    lines: list[str], end: str, opener: str, data: st.DataObject
) -> None:
    """For a written body of any of these lines, a person opens a block on any line above the
    record. The read gives the record, and the next write gives one record block that holds the
    keys of the old record."""
    written = with_record("\n".join(lines) + end, BLOCK).split("\n")
    at = data.draw(st.integers(min_value=0, max_value=len(written) - 1))
    person, held = split_record("\n".join([*written[:at], opener, *written[at:]]))
    after = with_record(person, encode_job_record(held, {RefineRecordKey.BODY_HASH: "b1"}))
    assert (held, after.count(CONST_ROADMAP_RECORD_MARKER), split_record(after)[1]) == (
        RECORD,
        1,
        NEXT_RECORD,
    )
