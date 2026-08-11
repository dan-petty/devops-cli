"""Unit tests for thinking block parsing and streaming token processing."""

from __future__ import annotations

from devops_cli.ai.thinking import (
    ThinkingStreamProcessor,
    extract_think_blocks,
    strip_think_blocks,
)


def test_strip_think_blocks_basic() -> None:
    """strip_think_blocks removes <think>...</think> tags and inner reasoning content."""
    raw = "<think>\nAnalyzing the request...\n</think>\nHere is the final answer."
    assert strip_think_blocks(raw) == "Here is the final answer."


def test_strip_think_blocks_multiple() -> None:
    """strip_think_blocks handles multiple thinking blocks."""
    raw = "<think>Step 1</think>Part 1<think>Step 2</think>Part 2"
    assert strip_think_blocks(raw) == "Part 1Part 2"


def test_extract_think_blocks() -> None:
    """extract_think_blocks separates reasoning blocks from clean text."""
    raw = "<think>First thought</think>Answer text<think>Second thought</think>"
    thinks, clean = extract_think_blocks(raw)
    assert thinks == ["First thought", "Second thought"]
    assert clean == "Answer text"


def test_thinking_stream_processor_suppress_thinking() -> None:
    """ThinkingStreamProcessor with show_thinking=False suppresses think blocks completely."""
    proc = ThinkingStreamProcessor(show_thinking=False)
    proc.feed("<think>\nInternal reasoning here\n</think>\nUseful response text.")
    proc.flush()

    assert proc.clean_content == "\nUseful response text."
    assert proc.thinking_content == "\nInternal reasoning here\n"


def test_thinking_stream_processor_split_across_chunks() -> None:
    """ThinkingStreamProcessor handles think tags split across token chunks."""
    proc = ThinkingStreamProcessor(show_thinking=False)

    # Split <think> tag
    proc.feed("<th")
    proc.feed("ink>Reasoning line</th")
    proc.feed("ink>Final response")
    proc.flush()

    assert proc.clean_content == "Final response"
    assert proc.thinking_content == "Reasoning line"


def test_thinking_stream_processor_callbacks() -> None:
    """ThinkingStreamProcessor triggers callbacks for think start, think end, and content."""
    events: list[str] = []
    content_chunks: list[str] = []

    proc = ThinkingStreamProcessor(
        show_thinking=True,
        on_think_start=lambda: events.append("think_start"),
        on_think_end=lambda: events.append("think_end"),
        on_content_chunk=lambda chunk: content_chunks.append(chunk),
    )

    proc.feed("<think>Reasoning</think>Hello World")
    proc.flush()

    assert events == ["think_start", "think_end"]
    assert "".join(content_chunks) == "Hello World"
    assert proc.clean_content == "Hello World"
