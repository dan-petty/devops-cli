"""Unit tests for streaming token processing, reasoning extraction, and stream bounds."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterable, Iterator
from typing import Any

import httpx2
import pytest

from devops_cli.ai import context_budget
from devops_cli.ai.client import LLMClient
from devops_cli.ai.client.models import AIClientError
from devops_cli.ai.client.network import stream_finish_reason
from devops_cli.ai.client.streaming import (
    StreamFrame,
    StreamingReasoningSanitizer,
    StreamingTokenProcessor,
    _claude_stream_frame,
    _find_suffix_overlap,
    _ollama_stream_frame,
    _openai_stream_frame,
    _read_event_stream,
    _read_ndjson_stream,
)
from devops_cli.ai.review.runner import _review_to_markdown
from devops_cli.ai.thinking_stream import ThinkingStreamProcessor
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import (
    NDJSON,
    OPENAI_DONE,
    SSE,
    RecordedBody,
    anthropic_event,
    anthropic_text,
    ollama_line,
    openai_chunk,
    reply,
    route_client,
    sse_data,
    streamed,
)


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

    def test_invalid_thinking_tags_raises_value_error(self) -> None:
        """Verify empty or malformed thinking_tags raise ValueError."""
        with pytest.raises(ValueError, match="thinking_tags must be a tuple"):
            StreamingTokenProcessor(thinking_tags=("", "</think>"))  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="thinking_tags must be a tuple"):
            StreamingTokenProcessor(thinking_tags=("<think>", ""))  # type: ignore[arg-type]

    def test_explicit_thinking_lifecycle_callbacks(self) -> None:
        """Verify explicit thinking chunks trigger on_reasoning_start and on_reasoning_end on transition or flush."""
        lifecycle_events: list[str] = []
        proc = StreamingTokenProcessor(
            on_reasoning_start=lambda: lifecycle_events.append("start"),
            on_reasoning_end=lambda: lifecycle_events.append("end"),
        )
        proc.feed("step1", is_thinking=True)
        assert lifecycle_events == ["start"]
        proc.feed("clean content", is_thinking=False)
        assert lifecycle_events == ["start", "end"]
        proc.flush()
        assert (proc.clean_content, proc.reasoning_scratchpad) == (
            "clean content",
            "step1",
        )


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


def _event(data: object, event: str = "message") -> httpx2.ServerSentEvent:
    """A parsed server-sent event, as httpx2's EventSource yields it."""
    return httpx2.ServerSentEvent(
        event=event, data=data if isinstance(data, str) else json.dumps(data)
    )


class TestProviderStreamFrames:
    """Each provider's frames: the text they carry, and whether and why the reply ended."""

    def test_ollama_frames(self) -> None:
        """Verify an Ollama line yields its content or thinking; `done: true` ends the stream."""
        lines = [
            {"message": {"content": "Hello Ollama"}},
            {"message": {"thinking": "Deep Ollama thoughts"}},
            {"message": {"content": "!"}, "done": True, "done_reason": "length"},
            {"message": {}},
            {"error": "model 'llama3' not found"},
        ]

        assert [_ollama_stream_frame(json.dumps(line)) for line in lines] + [
            _ollama_stream_frame(""),
            _ollama_stream_frame("{not valid json"),
        ] == [
            StreamFrame(chunk="Hello Ollama"),
            StreamFrame(chunk="<think>Deep Ollama thoughts</think>"),
            StreamFrame(chunk="!", complete=True, last=True, finish_reason="length"),
            StreamFrame(),
            StreamFrame(error="model 'llama3' not found"),
            StreamFrame(),
            StreamFrame(),
        ]

    def test_claude_frames(self) -> None:
        """Verify Claude events yield text and thinking, `message_stop` ends, `[DONE]` does not."""
        events = [
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Claude text"}},
            {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "Hm"}},
            {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": ""}},
            {"type": "content_block_delta", "delta": {"type": "other"}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
            {"type": "message_stop"},
            {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
            {"type": "ping"},
        ]

        assert [_claude_stream_frame(_event(e)) for e in events] + [
            _claude_stream_frame(_event("[DONE]")),
            _claude_stream_frame(_event("{invalid json", event="message_stop")),
        ] == [
            StreamFrame(chunk="Claude text"),
            StreamFrame(chunk="<think>Hm</think>"),
            StreamFrame(),
            StreamFrame(),
            StreamFrame(finish_reason="stop"),
            StreamFrame(complete=True, last=True),
            StreamFrame(error="Overloaded"),
            StreamFrame(),
            StreamFrame(),
            StreamFrame(complete=True, last=True),
        ]

    def test_openai_frames(self) -> None:
        """Verify OpenAI chunks yield content and reasoning; a finish reason or `[DONE]` ends."""
        chunks = [
            {"choices": [{"delta": {"content": "OpenAI answer"}}]},
            {"choices": [{"delta": {"reasoning_content": "OpenAI reasoning"}}]},
            {"choices": [{"delta": {"reasoning": "More reasoning"}}]},
            {"choices": [{"delta": {}}]},
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
            {"choices": [{"delta": {}, "finish_reason": "unheard_of"}]},
            {"choices": [], "usage": {"completion_tokens": 3}},
            {"error": {"message": "upstream timed out"}},
        ]

        assert [_openai_stream_frame(_event(c)) for c in chunks] + [
            _openai_stream_frame(_event("[DONE]")),
            _openai_stream_frame(_event("{invalid json")),
        ] == [
            StreamFrame(chunk="OpenAI answer"),
            StreamFrame(chunk="<think>OpenAI reasoning</think>"),
            StreamFrame(chunk="<think>More reasoning</think>"),
            StreamFrame(),
            StreamFrame(complete=True, finish_reason="tool_call"),
            StreamFrame(complete=True),
            StreamFrame(),
            StreamFrame(error="upstream timed out"),
            StreamFrame(complete=True, last=True),
            StreamFrame(),
        ]


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


# ── Stream readers, fed by an httpx2 MockTransport (no socket is opened) ──────────────────────

_PROTOCOLS: dict[str, tuple[Any, Any, str]] = {
    "openai": (_read_event_stream, _openai_stream_frame, SSE),
    "anthropic": (_read_event_stream, _claude_stream_frame, SSE),
    "ollama": (_read_ndjson_stream, _ollama_stream_frame, NDJSON),
}
_GITHUB_TOKEN = "ghp_" + "A" * 36


@pytest.fixture(autouse=True)
def _no_stream_finish_reason() -> Iterator[None]:
    """Start each test with no stream's finish reason, and leave none behind."""
    token = stream_finish_reason.set(None)
    yield
    stream_finish_reason.reset(token)


def _read(
    protocol: str, frames: Iterable[bytes], content_type: str | None = None, **limits: int
) -> tuple[list[str], str | None, str | None]:
    """Read a stream: the text it yielded, its finish reason, and the error that ended it."""
    reader, parse_frame, default_type = _PROTOCOLS[protocol]
    chunks: list[str] = []
    with streamed(frames, content_type or default_type) as response:
        try:
            for chunk in reader(response, parse_frame, "Provider", **limits):
                chunks.append(chunk)
        except AIClientError as exc:
            return chunks, stream_finish_reason.get(), str(exc)
    return chunks, stream_finish_reason.get(), None


_ENDED_EARLY = "Provider stream ended before its final frame."
_NOT_UTF8 = "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"


@pytest.mark.parametrize(
    ("protocol", "frames", "expected"),
    [
        (
            "openai",
            [openai_chunk("Hel"), openai_chunk("lo", "length"), OPENAI_DONE],
            (["Hel", "lo"], "length", None),
        ),
        (
            "openai",
            [openai_chunk("Hi"), openai_chunk(finish_reason="stop")],
            (["Hi"], "stop", None),
        ),
        ("openai", [openai_chunk("Hi"), OPENAI_DONE], (["Hi"], None, None)),
        ("openai", [openai_chunk("Hel"), openai_chunk("lo")], (["Hel", "lo"], None, _ENDED_EARLY)),
        (
            "anthropic",
            [
                anthropic_event("message_start", message={"id": "msg_1", "content": []}),
                anthropic_text("Hi"),
                anthropic_event("message_delta", delta={"stop_reason": "max_tokens"}),
                anthropic_event("message_stop"),
            ],
            (["Hi"], "length", None),
        ),
        ("anthropic", [anthropic_text("Hi"), OPENAI_DONE], (["Hi"], None, _ENDED_EARLY)),
        (
            "anthropic",
            [
                anthropic_text("Hi"),
                anthropic_event(
                    "error", error={"type": "overloaded_error", "message": "Overloaded"}
                ),
            ],
            (["Hi"], None, "Provider stream reported an error: Overloaded"),
        ),
        (
            "ollama",
            [ollama_line("Hi"), ollama_line(done=True, done_reason="length")],
            (["Hi"], "length", None),
        ),
        ("ollama", [ollama_line("Hi"), ollama_line("lo")[:-9]], (["Hi"], None, _ENDED_EARLY)),
        (
            "ollama",
            [ollama_line("Hi"), b'{"error": "model requires more system memory"}\n'],
            (["Hi"], None, "Provider stream reported an error: model requires more system memory"),
        ),
        (
            "openai",
            [openai_chunk("Hi"), sse_data({"error": {"message": "upstream timed out"}})],
            (["Hi"], None, "Provider stream reported an error: upstream timed out"),
        ),
        (
            "ollama",
            [ollama_line("Hi"), b"\xff\n"],
            (["Hi"], None, f"Provider stream line is not UTF-8: {_NOT_UTF8}"),
        ),
    ],
    ids=[
        "openai-length-then-done",
        "openai-reason-then-eof",
        "openai-done-alone",
        "openai-eof-without-either",
        "anthropic-max-tokens-then-message-stop",
        "anthropic-eof-before-message-stop",
        "anthropic-error-event",
        "ollama-done-length",
        "ollama-eof-mid-line",
        "ollama-error-line",
        "openai-error-object",
        "ollama-line-not-utf8",
    ],
)
def test_a_stream_is_complete_only_at_its_final_frame(
    protocol: str, frames: list[bytes], expected: tuple[list[str], str | None, str | None]
) -> None:
    """Verify each stream yields its text, ends on its provider's final frame, and raises else."""
    assert _read(protocol, frames) == expected


def test_reading_goes_on_past_the_finish_reason_to_done() -> None:
    """Verify a usage chunk after the finish reason is still read, through to `[DONE]`."""
    usage = sse_data({"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}})
    body = RecordedBody(
        [openai_chunk("Hi"), openai_chunk(finish_reason="stop"), usage, OPENAI_DONE]
    )

    assert (_read("openai", body), body.read) == ((["Hi"], "stop", None), 4)


@pytest.mark.parametrize(
    ("protocol", "frames", "reason"),
    [
        ("openai", [openai_chunk("Hi", "stop"), OPENAI_DONE, openai_chunk("late")], "stop"),
        (
            "anthropic",
            [anthropic_text("Hi"), anthropic_event("message_stop"), anthropic_text("late")],
            None,
        ),
        ("ollama", [ollama_line("Hi", done=True, done_reason="stop"), ollama_line("late")], "stop"),
    ],
    ids=["openai-done", "anthropic-message-stop", "ollama-done"],
)
def test_reading_stops_at_the_final_frame(
    protocol: str, frames: list[bytes], reason: str | None
) -> None:
    """Verify nothing after `[DONE]`, `message_stop` or `done: true` is read or yielded."""
    body = RecordedBody(frames)

    assert (_read(protocol, body), body.read) == ((["Hi"], reason, None), len(frames) - 1)


@pytest.mark.parametrize("protocol", ["openai", "ollama"])
def test_an_error_frame_is_masked_and_cut(protocol: str) -> None:
    """Verify a token in a provider's error message never reaches the raised error."""
    message = f"bad credentials {_GITHUB_TOKEN} " + "x" * 400
    error_frames = {
        "openai": sse_data({"error": {"message": message}}),
        "ollama": (json.dumps({"error": message}) + "\n").encode(),
    }

    _, _, error = _read(protocol, [error_frames[protocol]])

    prefix = "Provider stream reported an error: bad credentials "
    assert (str(error).startswith(prefix), _GITHUB_TOKEN in str(error), len(str(error))) == (
        True,
        False,
        len("Provider stream reported an error: ") + 256,
    )


@pytest.mark.parametrize("protocol", ["openai", "ollama"])
def test_a_frame_split_across_chunks_reads_as_whole(protocol: str) -> None:
    """Verify frames split mid-line and mid-code-point, and a raw U+2028, read intact."""
    text = "naïve € \u2028 end"
    frames = {
        "openai": [openai_chunk(text, "stop"), OPENAI_DONE],
        "ollama": [ollama_line(text, done=True, done_reason="stop")],
    }[protocol]
    whole = b"".join(frames)
    one_byte_chunks = [whole[i : i + 1] for i in range(len(whole))]

    assert (
        "\u2028".encode() in whole,
        _read(protocol, [whole]),
        _read(protocol, one_byte_chunks),
    ) == (True, ([text], "stop", None), ([text], "stop", None))


def test_an_oversized_event_or_line_is_refused() -> None:
    """Verify one event, or one line whether whole or unterminated, past the limit raises."""
    endless_line = RecordedBody([b'{"message": {"content": "'] + [b"x" * 32] * 50)
    line_limit = "Provider stream line exceeded the 64 bytes limit."

    assert (
        _read("openai", [openai_chunk("x" * 200), OPENAI_DONE], max_event_bytes=64),
        _read("ollama", endless_line, max_line_bytes=64)[2],
        endless_line.read < len(endless_line.frames),
        _read("ollama", [ollama_line("x" * 200, done=True)], max_line_bytes=64),
    ) == (
        (
            [],
            None,
            "Provider stream could not be read: Server-sent event exceeded the 64 byte limit.",
        ),
        line_limit,
        True,
        ([], None, line_limit),
    )


@pytest.mark.parametrize(
    ("protocol", "frame"), [("openai", openai_chunk("x" * 10)), ("ollama", ollama_line("x" * 10))]
)
def test_a_stream_past_its_size_limit_is_refused(protocol: str, frame: bytes) -> None:
    """Verify the whole-stream limit counts every frame and raises once it is passed."""
    chunks, _, error = _read(protocol, [frame] * 10, max_stream_bytes=200)

    assert (len(chunks) < 10, error) == (
        True,
        "Provider response exceeded maximum stream size (200 bytes).",
    )


@pytest.mark.parametrize(
    ("protocol", "frames"),
    [
        ("openai", [openai_chunk("Hel"), openai_chunk("lo", "stop"), OPENAI_DONE]),
        ("ollama", [ollama_line("Hel"), ollama_line("lo"), ollama_line(done=True)]),
    ],
)
def test_chunks_reach_the_caller_as_they_arrive(protocol: str, frames: list[bytes]) -> None:
    """Verify the first chunk is yielded before the transport has produced the last frame."""
    reader, parse_frame, content_type = _PROTOCOLS[protocol]
    body = RecordedBody(frames)
    with streamed(body, content_type) as response:
        chunks = reader(response, parse_frame, "Provider")
        first, read_at_first = next(chunks), body.read
        rest = list(chunks)

    assert (first, read_at_first, rest, body.read) == ("Hel", 1, ["lo"], 3)


def test_an_event_stream_of_another_content_type_is_refused() -> None:
    """Verify an SSE reply sent as `application/json` raises, naming the type."""
    _, _, error = _read("openai", [openai_chunk("Hi"), OPENAI_DONE], "application/json")

    assert error == (
        "Provider stream could not be read: Expected response with content type "
        "'text/event-stream', got 'application/json'."
    )


def _openai_client(monkeypatch: pytest.MonkeyPatch) -> LLMClient:
    # The stream's spend estimate counts tokens; loading the tokenizer is not under test.
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)
    config = AIConfig(
        provider="openai",
        model="gpt-test",
        api_base_url="http://example.com/v1",
        allow_private_network=True,
    )
    return LLMClient(config, api_key="sk-test", cache_enabled=False)


def test_each_stream_starts_with_no_finish_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a stream ending on `[DONE]` alone, or cut, does not inherit the last one's reason."""
    client = _openai_client(monkeypatch)
    cut_length = [openai_chunk("Hi", "length"), OPENAI_DONE]
    replies = iter(
        [cut_length, [openai_chunk("Hi")], cut_length, [openai_chunk("Hi"), OPENAI_DONE]]
    )
    route_client(client, monkeypatch, lambda request: reply(next(replies)))
    reasons: list[str | None] = []

    for _ in range(4):
        # The second stream ends before its final frame, so it raises and sets no reason.
        with contextlib.suppress(AIClientError):
            list(client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]))
        reasons.append(stream_finish_reason.get())

    assert reasons == ["length", None, "length", None]


def test_an_ollama_stream_failing_after_output_is_not_replayed_on_another_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a stream cut after it yielded output raises instead of failing over mid-reply."""
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)
    client = LLMClient(
        AIConfig(
            provider="ollama",
            model="llama3",
            ollama_urls=["http://example.com:11434", "http://example.com:11435"],
            allow_private_network=True,
        ),
        cache_enabled=False,
    )

    def cut_body() -> Iterator[bytes]:
        yield ollama_line("Hi")
        raise httpx2.ReadError("connection reset by peer")

    sent = route_client(client, monkeypatch, lambda request: reply(cut_body(), NDJSON))
    chunks: list[str] = []
    with pytest.raises(AIClientError, match="connection terminated unexpectedly") as raised:
        for chunk in client.chat_messages_stream("sys", [ChatMessage(role="user", content="hi")]):
            chunks.append(chunk)

    assert (chunks, len(sent), type(raised.value)) == (["Hi"], 1, AIClientError)
