"""The parse cost of `split_record` (#4445, #4470): a body that does not hold the opening text of
the record block is not parsed, and the parse of a body that holds it builds only the blocks.

A profile function counts the calls of `MarkdownIt.parse` and keeps the tokens of each call. It
sees the real parse and replaces no object, so the test patches no devops-cli name
(docs/TESTING.md # Doubles).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType

from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.roadmap.stores.store import split_record

RECORD = '<!-- devops-roadmap-record {"Priority": "P2-Medium"} -->'


@contextmanager
def parses() -> Iterator[list[list[Token]]]:
    """The tokens of each `MarkdownIt.parse` call in the block, in the order of the calls."""
    found: list[list[Token]] = []
    parse = MarkdownIt.parse.__code__

    def profile(frame: FrameType, event: str, arg: object) -> None:
        if event == "return" and frame.f_code is parse and isinstance(arg, list):
            found.append([token for token in arg if isinstance(token, Token)])

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        yield found
    finally:
        sys.setprofile(previous)


def test_a_body_without_the_record_opener_is_not_parsed() -> None:
    body = "Plain text with `code` and a comment.\n\n<!-- a person's note -->"
    with parses() as calls:
        result = split_record(body)
    assert (result, len(calls)) == ((body, {}), 0)


def test_a_batch_parses_only_the_bodies_that_hold_the_record_opener() -> None:
    """100 bodies, of which 10 hold the record block, give 10 parses and 10 records."""
    bodies = [f"Body {n}.\n\n{RECORD}" if n % 10 == 0 else f"Body {n}." for n in range(100)]
    with parses() as calls:
        records = [split_record(body)[1] for body in bodies]
    assert (len(calls), records.count({"Priority": "P2-Medium"})) == (10, 10)


def test_the_parse_of_a_body_builds_no_inline_tokens() -> None:
    """The core rule `inline` is off: the `inline` token of a paragraph has empty `children`,
    and the record block at the end reads as before."""
    with parses() as calls:
        result = split_record(f"Plain text.\n\n{RECORD}")
    shape = [(token.type, token.children) for tokens in calls for token in tokens]
    assert (result, shape) == (
        ("Plain text.", {"Priority": "P2-Medium"}),
        [("paragraph_open", None), ("inline", []), ("paragraph_close", None), ("html_block", None)],
    )
