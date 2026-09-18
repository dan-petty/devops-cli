"""Unit tests for streaming token processing, reasoning extraction, and stream bounds."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.ai.client.models import AIClientError
from devops_cli.ai.client.streaming import (
    StreamingReasoningSanitizer,
    StreamingTokenProcessor,
    _attempt_stream_reconnect,
    _consume_streaming_lines,
    _extract_claude_stream_chunk,
    _extract_ollama_stream_chunk,
    _extract_ollama_stream_tuple,
    _extract_openai_stream_chunk,
    _extract_stream_chunk,
    _find_suffix_overlap,
    _read_response_lines,
)
from devops_cli.ai.review.runner import _review_to_markdown
from devops_cli.ai.thinking_stream import ThinkingStreamProcessor


class TestSuffixOverlap:
    """Test suite for suffix-prefix overlap calculation."""

    def test_find_suffix_overlap_matches(self) -> None:
        """Verify suffix overlap identifies partial prefix matches."""
        assert (
            _find_suffix_overlap("abc<th", "<think>") == 3
            and _find_suffix_overlap("content</", "</think>") == 2
            and _find_suffix_overlap("nothing", "<think>") == 0
        )


class TestStreamingTokenProcessorBasic:
    """Test suite for basic token feeding, reasoning extraction, and scratchpad access."""

    def test_process_simple_thinking_and_content(self) -> None:
        """Verify processor separates think block from final markdown response."""
        proc = StreamingTokenProcessor()
        proc.feed("<think>Analyzing repository architecture...</think>Here is the clean answer.")
        proc.flush()

        assert (proc.clean_content, proc.reasoning_scratchpad, proc.has_reasoning) == (
            "Here is the clean answer.",
            "Analyzing repository architecture...",
            True,
        )

    def test_alias_streaming_reasoning_sanitizer(self) -> None:
        """Verify StreamingReasoningSanitizer is identical alias to StreamingTokenProcessor."""
        assert StreamingReasoningSanitizer is StreamingTokenProcessor

    def test_to_dict_summary(self) -> None:
        """Verify to_dict produces structured metadata summary."""
        proc = StreamingTokenProcessor()
        proc.feed("<think>Quick thought</think>Summary output")
        proc.flush()
        summary = proc.to_dict()

        assert (
            summary["clean_content"],
            summary["reasoning_scratchpad"],
            summary["has_reasoning"],
            summary["total_bytes"] > 0,
        ) == ("Summary output", "Quick thought", True, True)


class TestTokenChunkBoundaries:
    """Test suite verifying tag boundary handling across split chunks."""

    def test_split_open_tag_across_chunks(self) -> None:
        """Verify opening <think> tag split across two chunks is cleanly parsed."""
        proc = StreamingTokenProcessor()
        emitted_1 = proc.feed("Prefix <th")
        emitted_2 = proc.feed("ink>Reasoning inside</think>Suffix")
        proc.flush()

        assert (
            "".join(emitted_1),
            "".join(emitted_2),
            proc.clean_content,
            proc.reasoning_scratchpad,
        ) == ("Prefix ", "Suffix", "Prefix Suffix", "Reasoning inside")

    def test_split_close_tag_across_chunks(self) -> None:
        """Verify closing </think> tag split across two chunks is cleanly parsed."""
        proc = StreamingTokenProcessor()
        proc.feed("<think>Reasoning step</th")
        proc.feed("ink>Result")
        proc.flush()

        assert (proc.clean_content, proc.reasoning_scratchpad) == (
            "Result",
            "Reasoning step",
        )

    def test_unclosed_thinking_at_stream_end(self) -> None:
        """Verify unclosed thinking tag does not leak <think> into clean content."""
        proc = StreamingTokenProcessor()
        proc.feed("Safe prefix.<think>Unfinished thoughts cut off...")
        proc.flush()

        assert (proc.clean_content, proc.reasoning_scratchpad, proc.in_think) == (
            "Safe prefix.",
            "Unfinished thoughts cut off...",
            False,
        )

    def test_multiple_sequential_thinking_blocks(self) -> None:
        """Verify multiple think blocks in succession are consolidated into scratchpad."""
        proc = StreamingTokenProcessor()
        proc.feed("<think>Phase 1</think>Interim<think>Phase 2</think>Conclusion")
        proc.flush()

        assert (proc.clean_content, proc.reasoning_scratchpad) == (
            "InterimConclusion",
            "Phase 1Phase 2",
        )


class TestStreamSanitizerGenerators:
    """Test suite for generator-based stream sanitization."""

    def test_sanitize_stream_synchronous(self) -> None:
        """Verify sanitize_stream consumes chunk generator and yields only clean tokens."""
        proc = StreamingTokenProcessor()
        raw_chunks = ["<th", "ink>Pondering</th", "ink>Hello", " world!"]
        clean_tokens = list(proc.sanitize_stream(raw_chunks))

        assert ("".join(clean_tokens), proc.reasoning_scratchpad) == (
            "Hello world!",
            "Pondering",
        )

    @pytest.mark.anyio
    async def test_async_sanitize_stream(self) -> None:
        """Verify async_sanitize_stream consumes async chunk generator cleanly."""

        async def _mock_stream() -> Any:
            for c in ["<think>Thinking</think>", "Async", " response"]:
                yield c

        proc = StreamingTokenProcessor()
        tokens = [t async for t in proc.async_sanitize_stream(_mock_stream())]

        assert ("".join(tokens), proc.reasoning_scratchpad) == (
            "Async response",
            "Thinking",
        )


class TestCallbacksAndExplicitThinking:
    """Test suite for event callbacks and provider explicit thinking."""

    def test_callbacks_lifecycle(self) -> None:
        """Verify lifecycle callbacks on reasoning start, chunk, end, and token."""
        events: list[str] = []
        tokens: list[str] = []
        thinks: list[str] = []

        proc = StreamingTokenProcessor(
            on_token=tokens.append,
            on_reasoning=thinks.append,
            on_reasoning_start=lambda: events.append("start"),
            on_reasoning_end=lambda: events.append("end"),
        )
        proc.feed("<think>Thought</think>Answer")
        proc.flush()

        assert (events, thinks, tokens) == (["start", "end"], ["Thought"], ["Answer"])

    def test_explicit_thinking_feed_parameter(self) -> None:
        """Verify is_thinking=True feeds directly into scratchpad without content emission."""
        proc = StreamingTokenProcessor()
        emitted = proc.feed("Model internal monologue", is_thinking=True)
        proc.flush()

        assert (emitted, proc.clean_content, proc.reasoning_scratchpad) == (
            [],
            "",
            "Model internal monologue",
        )


class TestMaxStreamBytesBoundary:
    """Test suite verifying MAX_STREAM_BYTES limit raises AIClientError."""

    def test_feed_exceeds_max_stream_bytes(self) -> None:
        """Verify feed raises AIClientError when cumulative bytes exceed limit."""
        proc = StreamingTokenProcessor(max_stream_bytes=50)
        proc.feed("A" * 40)
        with pytest.raises(AIClientError, match="Stream exceeded maximum size limit"):
            proc.feed("B" * 20)


class TestProviderChunkExtractors:
    """Test suite for Ollama, Claude, and OpenAI stream line parsers."""

    def test_extract_ollama_content_and_thinking(self) -> None:
        """Verify Ollama extraction handles message.content and message.thinking."""
        line_content = json.dumps({"message": {"content": "Hello Ollama"}})
        line_thinking = json.dumps({"message": {"thinking": "Deep Ollama thoughts"}})
        line_empty = ""

        c_text = _extract_ollama_stream_chunk(line_content)
        c_think = _extract_ollama_stream_chunk(line_thinking)
        c_empty = _extract_ollama_stream_chunk(line_empty)
        c_tuple = _extract_ollama_stream_tuple(line_content)

        assert (c_text, c_think, c_empty, c_tuple) == (
            "Hello Ollama",
            "<think>Deep Ollama thoughts</think>",
            None,
            ("Hello Ollama", False),
        )

    def test_extract_claude_sse_chunks(self) -> None:
        """Verify Claude SSE parser handles text_delta, thinking_delta, and DONE."""
        line_text = "data: " + json.dumps(
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Claude text"}}
        )
        line_think = "data: " + json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "thinking_delta", "thinking": "Claude thoughts"},
            }
        )
        line_done = "data: [DONE]"

        res_text = _extract_claude_stream_chunk(line_text)
        res_think = _extract_claude_stream_chunk(line_think)
        res_done = _extract_claude_stream_chunk(line_done)

        assert (res_text, res_think, res_done) == (
            ("Claude text", False),
            ("<think>Claude thoughts</think>", False),
            (None, True),
        )

    def test_extract_openai_sse_chunks(self) -> None:
        """Verify OpenAI SSE parser handles content, reasoning_content, and DONE."""
        line_content = "data: " + json.dumps({"choices": [{"delta": {"content": "OpenAI answer"}}]})
        line_reasoning = "data: " + json.dumps(
            {"choices": [{"delta": {"reasoning_content": "OpenAI reasoning"}}]}
        )
        line_done = "data: [DONE]"

        res_content = _extract_openai_stream_chunk(line_content)
        res_reasoning = _extract_openai_stream_chunk(line_reasoning)
        res_done = _extract_openai_stream_chunk(line_done)

        assert (res_content, res_reasoning, res_done) == (
            ("OpenAI answer", False),
            ("<think>OpenAI reasoning</think>", False),
            (None, True),
        )

    def test_extract_stream_chunk_unified_dispatcher(self) -> None:
        """Verify _extract_stream_chunk routes properly to provider parser."""
        line_claude = "data: " + json.dumps(
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}}
        )
        line_openai = "data: " + json.dumps({"choices": [{"delta": {"content": "Hey"}}]})
        line_ollama = json.dumps({"message": {"content": "Yo"}})

        assert (
            _extract_stream_chunk(line_claude, "claude"),
            _extract_stream_chunk(line_openai, "openai"),
            _extract_stream_chunk(line_ollama, "ollama"),
        ) == (("Hi", False), ("Hey", False), ("Yo", False))


class TestConsumeStreamingLines:
    """Test suite for bounded line consumption and reconnection handling."""

    def test_consume_streaming_lines_success(self) -> None:
        """Verify _consume_streaming_lines yields parsed lines within size limit."""
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = ["line1", "line2"]

        def extractor(line: str) -> tuple[str, bool]:
            return (f"{line}_parsed", False)

        tokens = list(_consume_streaming_lines(mock_resp, extractor, "TestProvider"))

        assert tokens == ["line1_parsed", "line2_parsed"]

    def test_consume_streaming_lines_size_exceeded(self) -> None:
        """Verify _consume_streaming_lines raises when max_stream_bytes exceeded."""
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = ["very_long_line" * 10]

        def extractor(line: str) -> tuple[str, bool]:
            return (line, False)

        with pytest.raises(AIClientError, match="maximum stream size"):
            list(
                _consume_streaming_lines(mock_resp, extractor, "TestProvider", max_stream_bytes=20)
            )

    def test_read_response_lines_break_on_done(self) -> None:
        """Verify _read_response_lines terminates on is_done."""
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = ["chunk", "done_signal", "should_not_reach"]

        def extractor(line: str) -> tuple[str | None, bool]:
            if line == "done_signal":
                return (None, True)
            return (line, False)

        results = list(_read_response_lines(mock_resp, extractor, "Provider", 1000, 0))
        assert len(results) == 1 and results[0][0] == "chunk"

    def test_stream_reconnect_success(self) -> None:
        """Verify transient network error triggers reconnect factory and resumes stream."""
        mock_resp1 = MagicMock()
        mock_resp1.iter_lines.side_effect = httpx2.RemoteProtocolError("Connection reset")

        mock_resp2 = MagicMock()
        mock_resp2.iter_lines.return_value = ["recovered_line"]

        reconnect_called = False

        def _reconnect() -> httpx2.Response:
            nonlocal reconnect_called
            reconnect_called = True
            return mock_resp2

        def extractor(line: str) -> tuple[str, bool]:
            return (line, False)

        tokens = list(
            _consume_streaming_lines(
                mock_resp1,
                extractor,
                "TestProvider",
                reconnect_factory=_reconnect,
            )
        )

        assert (reconnect_called, tokens) == (True, ["recovered_line"])

    def test_stream_reconnect_failure_raises(self) -> None:
        """Verify failed reconnection raises AIClientError."""
        exc = httpx2.TransportError("Dead connection")
        with pytest.raises(AIClientError, match="streaming connection terminated unexpectedly"):
            _attempt_stream_reconnect("TestProvider", None, 0, 2, exc)

        def bad_factory() -> httpx2.Response:
            raise RuntimeError("DNS failure")

        with pytest.raises(AIClientError, match="SSE stream reconnect failed"):
            _attempt_stream_reconnect("TestProvider", bad_factory, 0, 2, exc)


class TestZeroLeakageDownstream:
    """Test suite verifying zero leakage of <think> tokens into reports and review markdown."""

    def test_review_to_markdown_strips_thinking_tags(self) -> None:
        """Verify _review_to_markdown cleans raw unparsed text with thinking tags."""
        raw_review = (
            "<think>\nFinding vulnerabilities in lines 10-15.\n</think>\n"
            "## Summary\nCode adheres to all standards."
        )
        md = _review_to_markdown(raw_review)

        assert "<think>" not in md and "Finding vulnerabilities" not in md
        assert "## Summary\nCode adheres to all standards." in md

    def test_thinking_stream_processor_reasoning_scratchpad_property(self) -> None:
        """Verify ThinkingStreamProcessor exposes standardized reasoning_scratchpad."""
        proc = ThinkingStreamProcessor(show_thinking=False)
        proc.feed("<think>Internal reasoning step</think>Clean message")
        proc.flush()

        assert (proc.clean_content, proc.reasoning_scratchpad) == (
            "Clean message",
            "Internal reasoning step",
        )

    def test_extract_stream_chunk_edge_cases(self) -> None:
        """Verify stream chunk extraction handles malformed lines, invalid JSON, and unknown providers."""
        assert (
            _extract_ollama_stream_chunk("{not valid json"),
            _extract_ollama_stream_chunk(json.dumps({"message": {}})),
            _extract_claude_stream_chunk("not-data-prefix"),
            _extract_claude_stream_chunk("data: {invalid json"),
            _extract_openai_stream_chunk("not-data-prefix"),
            _extract_openai_stream_chunk("data: {invalid json"),
            _extract_stream_chunk("data: [DONE]", "claude"),
            _extract_stream_chunk("data: [DONE]", "openai"),
            _extract_stream_chunk("data: [DONE]", "unknown_provider"),
        ) == (
            None,
            None,
            (None, False),
            (None, False),
            (None, False),
            (None, False),
            (None, True),
            (None, True),
            (None, False),
        )

    def test_streaming_token_processor_empty_feed_and_flush(self) -> None:
        """Verify feeding empty string or flushing clean processor behaves deterministically."""
        proc = StreamingTokenProcessor()
        res_empty = proc.feed("")
        res_normal = proc.feed("Content")
        res_flush = proc.flush()

        assert (res_empty, res_normal, res_flush, proc.clean_content) == (
            [],
            ["Content"],
            [],
            "Content",
        )

    def test_reconnect_max_retries_exceeded(self) -> None:
        """Verify _attempt_stream_reconnect raises AIClientError when max_reconnects is reached."""
        exc = httpx2.TransportError("Socket dropped")
        factory = MagicMock()
        with pytest.raises(AIClientError, match="streaming connection terminated unexpectedly"):
            _attempt_stream_reconnect("TestProvider", factory, 2, 2, exc)
        assert not factory.called

    def test_llm_client_chat_stream_with_sanitization(self) -> None:
        """Verify LLMClient chat_stream with sanitize=True strips think tags."""
        from unittest.mock import patch

        from devops_cli.ai.client import LLMClient
        from devops_cli.config.settings import AIConfig

        client = LLMClient(config=AIConfig(provider="ollama", model="test-model"))
        mock_chunks = ["<think>pondering problem</think>", "Clean", " response"]
        with patch.object(client, "_dispatch_stream", return_value=iter(mock_chunks)):
            raw_tokens = list(client.chat_stream("sys", "usr", sanitize=False))
        with patch.object(client, "_dispatch_stream", return_value=iter(mock_chunks)):
            clean_tokens = list(client.chat_stream("sys", "usr", sanitize=True))

        assert ("".join(raw_tokens), "".join(clean_tokens)) == (
            "<think>pondering problem</think>Clean response",
            "Clean response",
        )

    @pytest.mark.asyncio
    async def test_streaming_token_processor_async_sanitize_stream(self) -> None:
        """Verify async_sanitize_stream sanitizes an async token stream."""
        proc = StreamingTokenProcessor()

        async def _mock_stream():
            for tok in ["<th", "ink>thought</th", "ink>final ", "res"]:
                yield tok

        tokens = [t async for t in proc.async_sanitize_stream(_mock_stream())]
        assert ("".join(tokens), proc.reasoning_scratchpad, proc.total_bytes > 0) == (
            "final res",
            "thought",
            True,
        )

    def test_streaming_token_processor_callbacks_and_unclosed_flush(self) -> None:
        """Verify on_reasoning callback and flush with unclosed think block."""
        reasoning_chunks: list[str] = []
        tokens: list[str] = []
        proc = StreamingTokenProcessor(
            on_reasoning=lambda c: reasoning_chunks.append(c),
            on_token=lambda t: tokens.append(t),
        )
        proc.feed("<think>unclosed thought")
        proc.flush()

        assert (
            "".join(reasoning_chunks),
            "".join(tokens),
            proc.reasoning_scratchpad,
            proc.clean_content,
        ) == ("unclosed thought", "", "unclosed thought", "")

    def test_extract_stream_chunk_fallback_and_none_lines(self) -> None:
        """Verify chunk extraction handles empty deltas and non-content choices."""
        claude_empty_delta = json.dumps({"type": "content_block_delta", "delta": {"type": "other"}})
        claude_empty_think = json.dumps(
            {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": ""}}
        )
        openai_empty_delta = json.dumps({"choices": [{"delta": {}}]})

        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = ["empty", "data: [DONE]"]
        read_lines = list(
            _read_response_lines(
                mock_resp, lambda line: (None, line == "data: [DONE]"), "test", 1000, 0
            )
        )

        assert (
            _extract_claude_stream_chunk(f"data: {claude_empty_delta}"),
            _extract_claude_stream_chunk(f"data: {claude_empty_think}"),
            _extract_openai_stream_chunk(f"data: {openai_empty_delta}"),
            _extract_ollama_stream_tuple("not json"),
            read_lines,
        ) == (
            (None, False),
            (None, False),
            (None, False),
            (None, False),
            [],
        )
