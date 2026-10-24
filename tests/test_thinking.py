"""Unit tests for thinking block parsing and streaming token processing."""

from __future__ import annotations

from devops_cli.ai.thinking_stream import (
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


def test_strip_think_blocks_only_thinking_returns_empty() -> None:
    """strip_think_blocks returns empty string when text contains only thinking blocks."""
    raw = "<think>\nInternal chain of thought\nAnalyzing the code...\n</think>"
    assert strip_think_blocks(raw) == ""


def test_strip_think_blocks_unclosed_returns_empty() -> None:
    """strip_think_blocks returns empty string when text contains unclosed think block."""
    raw = "<think>\nModel ran out of tokens while thinking and never closed tag..."
    assert strip_think_blocks(raw) == ""


def test_strip_think_blocks_thinking_with_json_returns_empty() -> None:
    """strip_think_blocks returns empty string even if think block contains JSON brackets."""
    raw = '<think>Let me formulate JSON: {"findings": [], "status": "ok"}</think>'
    assert strip_think_blocks(raw) == ""


def test_strip_think_blocks_unclosed_with_clean_prefix() -> None:
    """strip_think_blocks preserves clean content preceding unclosed thinking tag."""
    raw = "Actual answer.<think>Unclosed thinking trailing off..."
    assert strip_think_blocks(raw) == "Actual answer."


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


def test_thinking_stream_processor_consolidates_header_and_footer() -> None:
    """Multiple <think> blocks in succession trigger think_start and think_end callbacks once."""
    events: list[str] = []

    proc = ThinkingStreamProcessor(
        show_thinking=True,
        on_think_start=lambda: events.append("think_start"),
        on_think_end=lambda: events.append("think_end"),
    )

    proc.feed("<think>Part 1</think>")
    proc.feed("<think> Part 2</think>")
    proc.feed("Final response content")
    proc.flush()

    assert events == ["think_start", "think_end"]
    assert proc.clean_content == "Final response content"
    assert proc.thinking_content == "Part 1 Part 2"


def test_unopened_closing_tag_counted_and_stripped() -> None:
    """Unopened closing tags are stripped from output and increment unopened_close_tags."""
    # Closing tag only through strip_think_blocks
    assert strip_think_blocks("</think>") == ""
    assert getattr(strip_think_blocks, "unopened_close_tags", 0) == 1

    # Mixed content with unopened closing tag
    chunks = ["Deciding what to commit.", "</think>", "git commit -m x"]
    assert strip_think_blocks("".join(chunks)) == "Deciding what to commit.git commit -m x"
    assert getattr(strip_think_blocks, "unopened_close_tags", 0) == 1

    proc = ThinkingStreamProcessor(show_thinking=False)
    for chunk in chunks:
        proc.feed(chunk)
    proc.flush()

    assert proc.clean_content == "Deciding what to commit.git commit -m x"
    assert getattr(proc, "unopened_close_tags", 0) == 1
    assert proc.to_dict()["unopened_close_tags"] == 1


def test_unclosed_thinking_stream_at_eof() -> None:
    """ThinkingStreamProcessor reports unclosed streams at EOF in to_dict() without leaking content."""
    proc = ThinkingStreamProcessor(show_thinking=False)
    proc.feed("Prefix <think>Unfinished thoughts cut off...")
    proc.flush()

    assert proc.clean_content == "Prefix "
    assert proc.thinking_content == "Unfinished thoughts cut off..."
    assert getattr(proc, "unclosed_stream", None) is True
    summary = proc.to_dict()
    assert summary["unclosed_stream"] is True


def test_thought_buffer_cap_and_discard() -> None:
    """Thought buffers cap at 65,536 chars and track discarded characters."""
    raw = "<think>" + "a" * 70_000 + "</think>Answer"
    cleaned = strip_think_blocks(raw)

    assert cleaned == "Answer"
    assert len(getattr(strip_think_blocks, "thinking_content", "")) == 65_536
    assert getattr(strip_think_blocks, "discarded_thought_chars", 0) == 4_464


def test_thinking_stream_processor_initial_state_profile() -> None:
    """ThinkingStreamProcessor accepts initial_state and model_profile to start in THINKING."""
    proc = ThinkingStreamProcessor(show_thinking=False, initial_state="thinking")
    assert proc.in_think is True
    proc.feed("Initial reasoning chunk")
    assert proc.in_think is True
    assert proc.thinking_content == "Initial reasoning chunk"
    assert proc.clean_content == ""

    proc.feed("</think>Final clean content")
    proc.flush()
    assert proc.in_think is False
    assert proc.clean_content == "Final clean content"

    proc_profile = ThinkingStreamProcessor(
        show_thinking=False, model_profile={"initial_state": "thinking"}
    )
    assert proc_profile.in_think is True
    proc_profile.feed("Single chunk")
    assert proc_profile.in_think is True
    assert proc_profile.thinking_content == "Single chunk"
