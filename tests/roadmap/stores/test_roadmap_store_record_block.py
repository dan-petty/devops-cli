"""The record block after a body that leaves a block open (#6729).

`with_record` writes the record block as a comment after the body, and `split_record` reads it
only as the last block of the body. CommonMark reads all text after an open fenced code block or
an open HTML block as part of that block, so the write closes such a block first: the record then
stays the last block, and GitHub shows no record text in the code of the person.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from markdown_it import MarkdownIt

from devops_cli.roadmap.body_hash import body_hashes
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
    assert (second, body_hashes(second), held) == (read_back, body_hashes(read_back), NEXT_RECORD)


@pytest.mark.parametrize("end", ["", "\n", "\n\n", "\r\n"], ids=["none", "one", "two", "crlf"])
def test_the_code_of_an_open_fence_keeps_its_rendered_form(end: str) -> None:
    """The close of a fence adds no empty line to its code, so CommonMark renders the body that
    the read gives back as it renders the body alone."""
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
