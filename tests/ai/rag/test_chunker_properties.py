"""Properties of the source chunker over open-ended input: coverage, size and overlap.

The chunker is a parser of files, so its invariants are tested with Hypothesis. The `ci` profile
that `addopts` loads sets no deadline and a fixed seed; each property keeps a small example count.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from devops_cli.ai.rag.chunker import (
    SemanticChunker,
    count_chunk_tokens,
    parse_markdown_headings,
)
from devops_cli.ai.rag.models import CodeChunk

PROPERTY = settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

# Words of ASCII letters only: no line is blank, and none is a heading, a comment or a statement.
WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12)
LINE = st.lists(WORD, min_size=1, max_size=6).map(" ".join)
LINES = st.lists(LINE, min_size=1, max_size=60)
# Blank lines among the text lines: a blank line is never part of a chunk of its own.
LINES_WITH_BLANKS = st.lists(st.one_of(LINE, st.just("")), min_size=1, max_size=60).filter(
    lambda lines: any(lines)
)
WINDOW = st.tuples(st.integers(min_value=2, max_value=20), st.integers(min_value=0, max_value=19))


def _chunks(
    root: Path, lines: list[str], *, size: int, overlap: int, max_tokens: int = 4096
) -> list[CodeChunk]:
    """Chunk a plain text file made of `lines` with a sliding window of `size` lines."""
    path = root / "notes.cfg"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    chunker = SemanticChunker(chunk_size=size, chunk_overlap=overlap, max_tokens=max_tokens)
    return chunker.chunk_file(path, relative_to=root)


def _plain_text_chunks(root: Path, lines: list[str], size: int, overlap: int) -> list[CodeChunk]:
    chunks = _chunks(root, lines, size=size, overlap=min(overlap, size - 1))
    # The file must take the sliding-window path; other paths have their own properties.
    assert chunks, "the window chunker returned nothing for non-blank text"
    return chunks


@PROPERTY
@given(lines=LINES_WITH_BLANKS, window=WINDOW)
def test_the_chunks_cover_every_line_of_text_of_the_input(
    tmp_path: Path, lines: list[str], window: tuple[int, int]
) -> None:
    size, overlap = window
    chunks = _plain_text_chunks(tmp_path, lines, size, overlap)

    covered = {n for chunk in chunks for n in range(chunk.start_line, chunk.end_line + 1)}

    assert {n for n, line in enumerate(lines, 1) if line} <= covered


@PROPERTY
@given(lines=LINES_WITH_BLANKS, window=WINDOW)
def test_each_chunk_holds_the_lines_of_its_range_and_nothing_else(
    tmp_path: Path, lines: list[str], window: tuple[int, int]
) -> None:
    size, overlap = window
    chunks = _plain_text_chunks(tmp_path, lines, size, overlap)

    for chunk in chunks:
        assert chunk.content == "\n".join(lines[chunk.start_line - 1 : chunk.end_line]).strip()


@PROPERTY
@given(lines=LINES, window=WINDOW)
def test_no_chunk_spans_more_lines_than_the_window(
    tmp_path: Path, lines: list[str], window: tuple[int, int]
) -> None:
    size, overlap = window
    chunks = _plain_text_chunks(tmp_path, lines, size, overlap)

    assert all(chunk.end_line - chunk.start_line + 1 <= size for chunk in chunks)


@PROPERTY
@given(lines=LINES, window=WINDOW)
def test_a_full_window_overlaps_the_next_one_by_the_overlap(
    tmp_path: Path, lines: list[str], window: tuple[int, int]
) -> None:
    size, requested = window
    overlap = min(requested, size - 1)
    chunks = _plain_text_chunks(tmp_path, lines, size, overlap)

    for current, following in pairwise(chunks):
        if current.end_line - current.start_line + 1 == size:
            assert current.end_line - following.start_line + 1 == overlap


@PROPERTY
@given(lines=LINES, max_tokens=st.integers(min_value=8, max_value=64))
def test_no_chunk_holds_more_tokens_than_the_limit(
    tmp_path: Path, lines: list[str], max_tokens: int
) -> None:
    chunks = _chunks(tmp_path, lines, size=20, overlap=2, max_tokens=max_tokens)

    assert all(count_chunk_tokens(chunk.content) <= max_tokens for chunk in chunks)


@PROPERTY
@given(lines=LINES, window=WINDOW)
def test_the_chunk_ids_of_a_file_are_unique_and_stable(
    tmp_path: Path, lines: list[str], window: tuple[int, int]
) -> None:
    size, overlap = window
    first = _plain_text_chunks(tmp_path, lines, size, overlap)
    again = _plain_text_chunks(tmp_path, lines, size, overlap)

    ids = [chunk.id for chunk in first]
    assert (len(set(ids)), ids) == (len(ids), [chunk.id for chunk in again])


FUNCTION = st.tuples(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10),
    st.integers(min_value=1, max_value=8),
)


@PROPERTY
@given(functions=st.lists(FUNCTION, min_size=1, max_size=8, unique_by=lambda f: f[0]))
def test_every_python_function_is_a_symbol_of_a_chunk_inside_the_file(
    tmp_path: Path, functions: list[tuple[str, int]]
) -> None:
    source = "".join(
        f"def fn_{name}():\n" + "".join(f"    value_{i} = {i}\n" for i in range(body)) + "\n\n"
        for name, body in functions
    )
    path = tmp_path / "module.py"
    path.write_text(source, encoding="utf-8")

    chunks = SemanticChunker(chunk_size=40, chunk_overlap=4).chunk_file(path, relative_to=tmp_path)

    symbols = {symbol for chunk in chunks for symbol in chunk.symbol_names}
    lines = len(source.splitlines())
    assert {f"fn_{name}" for name, _ in functions} <= symbols
    assert all(1 <= chunk.start_line <= chunk.end_line <= lines for chunk in chunks)


HEADING = st.tuples(st.integers(min_value=1, max_value=6), WORD).map(
    lambda parts: f"{'#' * parts[0]} {parts[1]}"
)


@PROPERTY
@given(
    headings=st.lists(HEADING, min_size=0, max_size=6),
    fenced=st.lists(HEADING, min_size=1, max_size=4),
)
def test_a_heading_line_inside_a_code_fence_is_not_a_heading(
    headings: list[str], fenced: list[str]
) -> None:
    document = "\n\n".join([*headings, "```text", *fenced, "```", "closing words"])

    found = parse_markdown_headings(document)

    assert [title for _, _, title in found] == [h.split(" ", 1)[1] for h in headings]


@settings(max_examples=15)
@given(text=st.text(max_size=400))
def test_markdown_headings_of_any_text_have_a_level_from_1_to_6_inside_the_text(
    text: str,
) -> None:
    found = parse_markdown_headings(text)

    lines = len(text.splitlines())
    assert all(1 <= level <= 6 and 0 <= line < max(1, lines) for line, level, _ in found)


@pytest.mark.parametrize("name", ["empty.cfg", "blank.cfg"])
def test_a_file_with_no_text_gives_no_chunk(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("" if name == "empty.cfg" else "\n\n   \n", encoding="utf-8")

    assert (
        SemanticChunker(chunk_size=10, chunk_overlap=2).chunk_file(path, relative_to=tmp_path) == []
    )
