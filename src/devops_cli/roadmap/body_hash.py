"""The sections and the hashes of the body of an item (#744, #3502).

Refine writes its section into the body of an item, and records the hash of the body outside the
section and the hash of the section in the job record. The hashes show whether a person edited the
item since the record. The trust rule reads them too: the review of an item of a bot approves the
text that the hashes cover, so an approval holds only while the body hashes as recorded.

The module imports no job, so that `trust` and `refine` can both import it.

A job block marker bounds a block only where CommonMark parses the marker as an HTML block of its
own (#6627). CommonMark ends a comment at the first line that holds `-->`, and a declaration such
as `<!DOCTYPE` at the first line that holds `>`. So a marker is also a bound when it is the whole
last line of such a block that a person leaves open above it. A marker that a person quotes in a
code span, a code block or a paragraph is the person's text, so a read keeps it and a write adds
its block at the end. A writer closes a fenced code block or an HTML block that is open before a
marker that it writes (`close_open_block`), so the next read finds the block again.

A fenced code block or an HTML block that no close ends runs to the end of the body, and GitHub
shows each later line as code, the job blocks too. A person leaves such a block open by accident.
The jobs write their blocks at the end of the body, so the job blocks at the end of the open block
end it for a read (#6736): from their first line on, the job block marker lines are whole blocks,
one for each job at most. The outside text of a block holds the close of the open block before
that line (`close_blocks_before_markers`), so a write that keeps the outside text replaces the old
block and adds no second one. Each other marker line in the open block, and each marker in a block
that a close ends, is still a quote.

CommonMark ends an HTML block of kind 6 or 7 only at a blank line. Such a block starts with a tag
such as `<details>` or `</div>`, or with a whole tag on a line of its own. A person can remove the
blank line between such a line and a job block. The marker line is then a line of that HTML block.
The job blocks at the end of the body end such a block too, with the rule of an open block
(#6791). The cut must leave no block open, so the text after the cut parses as before. The
outside text of a block holds a blank line before the first marker line. So the next read parses
the marker as an HTML block of its own. Each other marker line in such a block is the text of the
person. So is a job block that text of a person follows. Every reader of a job block marker uses
this rule: `block_marker_of` for one token, and `block_marker_spans` for a body.
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

# The start and the end marker of the block of each job that writes a block in the body.
_JOB_BLOCKS: Final[tuple[tuple[str, str], ...]] = (
    (CONST_ROADMAP_REFINE_START_MARKER, CONST_ROADMAP_REFINE_END_MARKER),
    (CONST_ROADMAP_ALTERNATIVES_START_MARKER, CONST_ROADMAP_ALTERNATIVES_END_MARKER),
)
_END_OF: Final[dict[str, str]] = dict(_JOB_BLOCKS)
_START_OF: Final[dict[str, str]] = {end: start for start, end in _JOB_BLOCKS}
# The start and the end markers of the blocks that the jobs write in the body. Each one ends a
# section of the body, because the text of a job block is not text of the section (#6613).
JOB_BLOCK_MARKERS: Final[frozenset[str]] = frozenset(_END_OF) | frozenset(_START_OF)

# GitHub reads a body as CommonMark: an `html_block` is a real comment, and a code span, a code
# block and a paragraph are other tokens, so a marker that a person quotes there is text. The rule
# reads only the blocks, so the core rule `inline` is off: a code span stays inside its paragraph.
_BODY_MARKDOWN: Final = MarkdownIt("commonmark").disable("inline")
_LINE_BREAK: Final = re.compile(r"\r\n|\r|\n")


def _line_starts(body: str) -> list[int]:
    """The character offset of the first character of each line of `body`."""
    return [0, *(found.end() for found in _LINE_BREAK.finditer(body))]


# The close of each kind of HTML block that only an end tag or an end text ends, by the start of
# its first line (CommonMark kinds 1 to 5). A blank line ends each other kind of HTML block.
_HTML_BLOCK_CLOSES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"<(script|pre|style|textarea)(?=[\s>]|$)", re.IGNORECASE), "</{tag}>"),
    (re.compile(r"<!--"), "-->"),
    (re.compile(r"<\?"), "?>"),
    (re.compile(r"<![A-Za-z]"), ">"),
    (re.compile(r"<!\[CDATA\["), "]]>"),
)


def _end_text(block: str) -> str | None:
    """The end tag or the end text that ends the HTML block `block`, by the start of its first
    line (`_HTML_BLOCK_CLOSES`), or None when a blank line ends its kind."""
    for opener, close in _HTML_BLOCK_CLOSES:
        if (match := opener.match(block)) is not None:
            return close.format(tag=match.group(1).lower() if match.groups() else "")
    return None


def ends_at_a_blank_line(block: str) -> bool:
    """Whether only a blank line ends the HTML block whose text is `block`: no end text of
    `_HTML_BLOCK_CLOSES` starts it. These are CommonMark kinds 6 and 7, such as `<details>`,
    `</div>` or a whole tag on a line of its own (#6791)."""
    return _end_text(block.lstrip()) is None


def block_marker_of(token: Token, markers: Collection[str] = JOB_BLOCK_MARKERS) -> str | None:
    """The marker of `markers` that bounds a job block in `token`, or None. When `token` is an
    HTML block, the marker is its whole text, or its whole last line when the first end text of
    the block (`_end_text`) ends the marker. CommonMark ends a comment at the first line that
    holds `-->` and a declaration such as `<!DOCTYPE` at the first line that holds `>`. So such a
    block that a person leaves open above a job block ends at the marker (#6627). For each other
    token, None. Each reader of a job block marker in a token uses this test (#6736)."""
    if token.type != "html_block":
        return None
    block = token.content.strip()
    if block in markers:
        return block
    last = block.rsplit("\n", 1)[-1].strip()
    close = _end_text(block)
    if last in markers and close is not None and block.find(close) == len(block) - len(close):
        return last
    return None


def _marker_span(
    body: str, token: Token, starts: Sequence[int], markers: Collection[str]
) -> tuple[str, int, int] | None:
    """The marker, its start and its end in `body`, when one of `markers` bounds a block in
    `token` (`block_marker_of`). The span is the text of the marker inside the block, so the quote
    of a blockquote or the indent of a list item stays in the outside text."""
    marker = block_marker_of(token, markers)
    if marker is None or token.map is None:
        return None
    first, after = token.map
    block = body[starts[first] : starts[after] if after < len(starts) else len(body)]
    offset = block.rfind(marker)
    if offset < 0:
        return None
    start = starts[first] + offset
    return marker, start, start + len(marker)


# The kinds of the last token of a text that can be open at its end: CommonMark ends each other
# kind of block at a blank line or at the end of its container.
_OPEN_KINDS: Final = frozenset({"fence", "html_block"})


def _open_block(
    text: str, tokens: Sequence[Token], starts: Sequence[int]
) -> tuple[int, Token] | None:
    """The first line of the fenced code block or the HTML block that is open at the end of `text`,
    and its token when a job block marker follows it after a blank line, or None when no block is
    open. `tokens` are the tokens of `text` and `starts` the starts of its lines.

    The parser decides: it reads the last block with a job block marker after a blank line. When
    the marker is part of that block, the block is open (#6627)."""
    last = tokens[-1] if tokens else None
    if last is None or last.type not in _OPEN_KINDS or last.map is None:
        return None
    probe = CONST_ROADMAP_REFINE_START_MARKER
    first = last.map[0]
    probed = _BODY_MARKDOWN.parse(f"{text[starts[first] :]}\n\n{probe}")[-1]
    if probed.type == "html_block" and probed.content.strip() == probe:
        return None
    return first, probed


def _marker_lines(text: str, starts: Sequence[int], first: int) -> list[tuple[int, str]]:
    """The offset in `text` and the marker of each line after line `first` that CommonMark reads
    on its own as a job block marker (`block_marker_of`). `starts` are the starts of the lines."""
    lines: list[tuple[int, str]] = []
    for line in range(first + 1, len(starts)):
        own = text[starts[line] : starts[line + 1] if line + 1 < len(starts) else len(text)]
        marker = own.strip()
        if marker in JOB_BLOCK_MARKERS and any(
            block_marker_of(token) for token in _BODY_MARKDOWN.parse(own)
        ):
            lines.append((starts[line], marker))
    return lines


def _are_job_blocks(markers: Sequence[str], before: Sequence[tuple[str, int, int]]) -> bool:
    """Whether `markers`, the last job block marker lines of an open block in their order, are
    the blocks of the jobs (#6736). `before` are the bounds before the open block. The first
    marker can be the end marker of a job whose block starts in `before`. Each other pair is the
    start and the end marker of one job, at most one pair for each job, and none of a job with a
    start marker in `before`. So a quote of a person is no block: a lone marker, a block of a job
    that a later block of the job follows, and a block of a job whose block comes first."""
    bound = {marker for marker, _, _ in before}
    used: set[str] = set()
    rest = list(markers)
    if rest and (opened := _START_OF.get(rest[0])) is not None:
        if opened not in bound or _bounds(before, opened, rest[0]) is not None:
            return False
        used.add(opened)
        rest = rest[1:]
    if len(rest) % 2:
        return False
    for start, end in zip(rest[::2], rest[1::2], strict=True):
        if _END_OF.get(start) != end or start in used or start in bound:
            return False
        used.add(start)
    return True


def _open_block_end(
    text: str, tokens: Sequence[Token], before: Sequence[tuple[str, int, int]]
) -> int | None:
    """The offset in `text` of the line that ends a block open to the end of `text`, or None: the
    first line of the job blocks at the end of the block (`_are_job_blocks`, #6736). Jobs write
    their blocks at the end of the body, so the most lines that are blocks of the jobs win.
    `tokens` are the tokens of `text`, and `before` the bounds before `text`."""
    starts = _line_starts(text)
    found = _open_block(text, tokens, starts)
    if found is None:
        return None
    lines = _marker_lines(text, starts, found[0])
    for count in range(min(len(lines), 2 * len(_JOB_BLOCKS)), 0, -1):
        if _are_job_blocks([marker for _, marker in lines[-count:]], before):
            return lines[-count][0]
    return None


def _html_block_with_marker_text(token: Token) -> bool:
    """Whether `token` is a top-level HTML block that only a blank line ends and that holds the
    text of a job block marker (`ends_at_a_blank_line`)."""
    return (
        token.type == "html_block"
        and not token.level
        and token.map is not None
        and any(marker in token.content for marker in JOB_BLOCK_MARKERS)
        and ends_at_a_blank_line(token.content)
    )


def _html_block_end(body: str, parts: Sequence[tuple[int, list[Token]]]) -> tuple[int, int] | None:
    """The index of an HTML block in the tokens of the last part of `parts`, and the offset of
    its end line (#6791). The block is a top-level HTML block that only a blank line ends. The end
    line is a marker line, and its offset is in the text of the part. None when no line ends such
    a block.

    The line must start the job blocks at the end of the text, as in a block that a person leaves
    open (`_are_job_blocks`, #6736). No text follows the last marker line. The cut leaves no block
    open at the end of the text (`close_open_block`). So a marker in an HTML block that a person
    writes stays their text, and a write keeps that block as it is."""
    start, tokens = parts[-1]
    blocks = [
        (index, token) for index, token in enumerate(tokens) if _html_block_with_marker_text(token)
    ]
    if not blocks:
        return None
    text = body[start:]
    starts = _line_starts(text)
    lines = _marker_lines(text, starts, 0)
    if not lines or text[lines[-1][0] :].strip() != lines[-1][1]:
        return None
    for count in range(min(len(lines), 2 * len(_JOB_BLOCKS)), 0, -1):
        offset = lines[-count][0]
        index = next(
            (
                index
                for index, token in blocks
                if token.map is not None
                and starts[token.map[0]] < offset
                and (token.map[1] >= len(starts) or offset < starts[token.map[1]])
            ),
            None,
        )
        if index is None:
            continue
        before = _spans(body, [*parts[:-1], (start, tokens[:index])], JOB_BLOCK_MARKERS)
        rest = text[offset:]
        if (
            _are_job_blocks([marker for _, marker in lines[-count:]], before)
            and close_open_block(rest) == rest
        ):
            return index, offset
    return None


def _parts(body: str) -> list[tuple[int, list[Token]]]:
    """The start of each part of `body`, and the tokens of its text (#6736). The tokens of a part
    are the tokens of the text from its start, up to the block that the next part ends. A new
    part starts at a job block marker line that ends a block for a read. A block that no close
    ends runs to the end of the body, and the job blocks at its end end it (`_open_block_end`).
    An HTML block that only a blank line ends also ends at the job blocks at the end of the body
    (`_html_block_end`, #6791). The first marker of a part bounds a block, so each job block marker
    line ends one block at most. A job can end two blocks. Its start marker ends a block above its
    block, and its end marker ends a block in its block. So a body has at most one part more than
    there are job block markers. A body with no such block is one part."""
    parts = [(0, _BODY_MARKDOWN.parse(body))]
    while len(parts) <= len(JOB_BLOCK_MARKERS):
        start, tokens = parts[-1]
        found = _html_block_end(body, parts)
        if found is None:
            end = _open_block_end(body[start:], tokens, _spans(body, parts, JOB_BLOCK_MARKERS))
            if end is None:
                break
        else:
            index, end = found
            parts[-1] = (start, tokens[: index + 1])
        parts.append((start + end, _BODY_MARKDOWN.parse(body[start + end :])))
    return parts


def _spans(
    body: str, parts: Sequence[tuple[int, list[Token]]], markers: Collection[str]
) -> list[tuple[str, int, int]]:
    """The marker, its start and its end in `body`, for each marker of `markers` that bounds a
    block in a part of `parts` (`_parts`), in the order of the body."""
    spans: list[tuple[str, int, int]] = []
    for start, tokens in parts:
        text = body[start:]
        starts = _line_starts(text)
        for token in tokens:
            span = _marker_span(text, token, starts, markers)
            if span is not None:
                spans.append((span[0], start + span[1], start + span[2]))
    return spans


def block_marker_spans(
    body: str, markers: Collection[str] = JOB_BLOCK_MARKERS
) -> list[tuple[str, int, int]]:
    """The marker, its start and its end in `body`, for each marker of `markers` that bounds a
    block (`block_marker_of`), in the order of the body (#6627). The job blocks at the end of the
    body end a block that a person leaves open (#6736). They also end an HTML block that only a
    blank line ends (`_parts`, #6791). So a marker of these blocks is read as in a body with the
    close in place."""
    return _spans(body, _parts(body), markers)


def _bounds(
    spans: Sequence[tuple[str, int, int]], start_marker: str, end_marker: str
) -> tuple[int, int] | None:
    """The start of the first `start_marker` of `spans` and the end of the `end_marker` that
    follows it, or None when `spans` hold no such pair."""
    start = next((span for span in spans if span[0] == start_marker), None)
    if start is None:
        return None
    end = next((span for span in spans if span[0] == end_marker and span[1] >= start[2]), None)
    if end is None:
        return None
    return start[1], end[2]


def job_block_bounds(
    body: str,
    start_marker: str = CONST_ROADMAP_REFINE_START_MARKER,
    end_marker: str = CONST_ROADMAP_REFINE_END_MARKER,
) -> tuple[int, int] | None:
    """The start of the first `start_marker` and the end of the `end_marker` that follows it, each
    a bound of a block (`block_marker_spans`), or None when the body holds no such pair (#6627)."""
    markers = (start_marker, end_marker)
    return _bounds(block_marker_spans(body, markers), start_marker, end_marker)


def close_open_block(text: str) -> str:
    """`text` with a close on a line of its own for the fenced code block or the HTML block that
    is open at its end, or `text` itself when no such block is open.

    CommonMark reads all text after an open fenced code block or an open HTML block as part of
    that block. A job block marker after `text` is then no HTML block of its own, and the next
    read does not find the block of the job (#6627). A blank line ends each other block, and a
    writer puts one before its block. The close keeps the text of the open block in that block."""
    found = _open_block(text, _BODY_MARKDOWN.parse(text), _line_starts(text))
    if found is None:
        return text
    last = found[1]
    if last.type == "fence":
        return f"{text}\n{last.markup}"
    close = _end_text(last.content.lstrip())
    return text if close is None else f"{text}\n{close}"


def _closed(body: str, parts: Sequence[tuple[int, list[Token]]]) -> str:
    """`body` with the close of each open block that a new part of `parts` ends (`_parts`). The
    close goes on a line of its own before the part, and a blank line follows it. An HTML block
    that only a blank line ends gets no close (`close_open_block`), so the blank line ends it
    (#6791)."""
    starts = [start for start, _ in parts]
    texts = [body[start:end] for start, end in zip(starts, [*starts[1:], len(body)], strict=True)]
    closed = (f"{close_open_block(text.rstrip())}\n\n" for text in texts[:-1])
    return "".join(closed) + texts[-1]


def close_blocks_before_markers(body: str) -> str:
    """`body` with a close on a line of its own before each line that ends a block open to the end
    of the body (#6736). A marker line that ends an HTML block that only a blank line ends gets a
    blank line before it (#6791). CommonMark then reads each job block of the result as
    `block_marker_spans` reads it in `body`. So a write that keeps this text keeps each block
    readable. A body with no such block is returned as it is."""
    parts = _parts(body)
    return body if len(parts) == 1 else _closed(body, parts)


def extract_section_and_outside(
    body: str,
    start_marker: str = CONST_ROADMAP_REFINE_START_MARKER,
    end_marker: str = CONST_ROADMAP_REFINE_END_MARKER,
) -> tuple[str, str | None]:
    """Returns (body_outside_section, section_inside_markers_or_none). The section is the one
    between the two markers, refine's by default; another job's block (#2650) has its own. A
    marker bounds the section only as an HTML block, so a quoted marker pair stays in the
    outside text (#6627). The cut is of the body as `close_blocks_before_markers` gives it. That
    body has the close of each block that a person leaves open above a job block (#6736). It also
    has a blank line before a marker line that ends an HTML block (#6791). So a write that keeps
    the outside text keeps the next job block readable."""
    parts = _parts(body)
    if len(parts) > 1:
        body = _closed(body, parts)
        parts = _parts(body)
    markers = (start_marker, end_marker)
    bounds = _bounds(_spans(body, parts, markers), start_marker, end_marker)
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
