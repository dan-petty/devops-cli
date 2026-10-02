"""Streaming utilities for token chunks, and readers for providers' event and NDJSON streams."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterable, Callable, Generator, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import httpx2

from devops_cli.ai.client.models import MAX_STREAM_BYTES, AIClientError, provider_finish_reason
from devops_cli.ai.client.network import stream_finish_reason
from devops_cli.config.constants import (
    CONST_ANTHROPIC_STOP_REASONS,
    CONST_OLLAMA_DONE_REASONS,
    CONST_OPENAI_FINISH_REASONS,
)
from devops_cli.config.defaults import DEFAULT_AI_STREAM_MAX_EVENT_BYTES
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason


def _find_suffix_overlap(text: str, target: str) -> int:
    """Find the length of the longest suffix of text that matches a prefix of target."""
    max_check = min(len(text), len(target) - 1)
    for length in range(max_check, 0, -1):
        if target.startswith(text[-length:]):
            return length
    return 0


class StreamingTokenProcessor:
    """Standardized streaming token processor and reasoning scratchpad extractor.

    Parses streaming SSE tokens in real-time, extracts <think>...</think> reasoning
    blocks into an isolated reasoning scratchpad, yields sanitized markdown content,
    and enforces strict MAX_STREAM_BYTES (50MB) boundary limits.
    """

    def __init__(
        self,
        *,
        max_stream_bytes: int = MAX_STREAM_BYTES,
        thinking_tags: tuple[str, str] = ("<think>", "</think>"),
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
        on_reasoning_start: Callable[[], None] | None = None,
        on_reasoning_end: Callable[[], None] | None = None,
    ) -> None:
        if len(thinking_tags) != 2 or not thinking_tags[0] or not thinking_tags[1]:
            raise ValueError(
                "thinking_tags must be a tuple of two non-empty strings (open_tag, close_tag)."
            )
        self.max_stream_bytes = max_stream_bytes
        self.thinking_tags = thinking_tags
        self.open_tag = thinking_tags[0]
        self.close_tag = thinking_tags[1]
        self.on_token = on_token
        self.on_reasoning = on_reasoning
        self.on_reasoning_start = on_reasoning_start
        self.on_reasoning_end = on_reasoning_end

        self._buffer: str = ""
        self._total_bytes: int = 0
        self._clean_chunks: list[str] = []
        self._reasoning_chunks: list[str] = []
        self.in_think: bool = False
        self.thinking_detected: bool = False
        self._explicit_thinking_active: bool = False
        self._reasoning_started: bool = False
        self._reasoning_ended: bool = False

    def _record_bytes(self, chunk: str) -> None:
        self._total_bytes += len(chunk.encode("utf-8"))
        if self._total_bytes > self.max_stream_bytes:
            raise AIClientError(
                f"Stream exceeded maximum size limit of {self.max_stream_bytes // (1024 * 1024)}MB."
            )

    def _trigger_reasoning_start(self) -> None:
        if not self._reasoning_started:
            self._reasoning_started = True
            self._reasoning_ended = False
            if self.on_reasoning_start:
                self.on_reasoning_start()

    def _trigger_reasoning_end(self) -> None:
        if self._reasoning_started and not self._reasoning_ended:
            self._reasoning_ended = True
            self._reasoning_started = False
            if self.on_reasoning_end:
                self.on_reasoning_end()

    def _handle_explicit_thinking(self, chunk: str) -> list[str]:
        self.thinking_detected = True
        self._explicit_thinking_active = True
        self._trigger_reasoning_start()
        self._reasoning_chunks.append(chunk)
        if self.on_reasoning:
            self.on_reasoning(chunk)
        return []

    def _emit_safe_tokens(self, text: str) -> list[str]:
        if not text:
            return []
        self._clean_chunks.append(text)
        if self.on_token:
            self.on_token(text)
        return [text]

    def _append_reasoning(self, text: str) -> None:
        if not text:
            return
        self._reasoning_chunks.append(text)
        if self.on_reasoning:
            self.on_reasoning(text)

    def _process_outside_think(self) -> tuple[bool, list[str]]:
        pos = self._buffer.find(self.open_tag)
        if pos != -1:
            content = self._buffer[:pos]
            self.in_think = True
            self.thinking_detected = True
            self._trigger_reasoning_start()
            self._buffer = self._buffer[pos + len(self.open_tag) :]
            tokens = self._emit_safe_tokens(content) if content else []
            return True, tokens

        match_len = _find_suffix_overlap(self._buffer, self.open_tag)
        if match_len > 0:
            safe = self._buffer[:-match_len]
            self._buffer = self._buffer[-match_len:]
            tokens = self._emit_safe_tokens(safe) if safe else []
            return False, tokens

        tokens = self._emit_safe_tokens(self._buffer)
        self._buffer = ""
        return True, tokens

    def _process_inside_think(self) -> tuple[bool, list[str]]:
        pos = self._buffer.find(self.close_tag)
        if pos != -1:
            reasoning = self._buffer[:pos]
            self.in_think = False
            self._buffer = self._buffer[pos + len(self.close_tag) :]
            self._append_reasoning(reasoning)
            self._trigger_reasoning_end()
            return True, []

        match_len = _find_suffix_overlap(self._buffer, self.close_tag)
        if match_len > 0:
            safe_think = self._buffer[:-match_len]
            self._buffer = self._buffer[-match_len:]
            self._append_reasoning(safe_think)
            return False, []

        self._append_reasoning(self._buffer)
        self._buffer = ""
        return True, []

    def _process_buffer(self) -> list[str]:
        emitted: list[str] = []
        while self._buffer:
            advanced, tokens = (
                self._process_inside_think() if self.in_think else self._process_outside_think()
            )
            emitted.extend(tokens)
            if not advanced:
                break
        return emitted

    def feed(self, chunk: str, *, is_thinking: bool = False) -> list[str]:
        """Feed a streaming chunk into the processor and return newly safe clean tokens."""
        if not chunk:
            return []
        self._record_bytes(chunk)
        if is_thinking:
            return self._handle_explicit_thinking(chunk)
        if self._explicit_thinking_active:
            self._explicit_thinking_active = False
            self._trigger_reasoning_end()
        self._buffer += chunk
        return self._process_buffer()

    def flush(self) -> list[str]:
        """Flush remaining buffered tokens and finalize reasoning states."""
        emitted: list[str] = []
        if self._explicit_thinking_active:
            self._explicit_thinking_active = False
            self._trigger_reasoning_end()
        if self.in_think:
            if self._buffer:
                self._append_reasoning(self._buffer)
            self.in_think = False
            self._trigger_reasoning_end()
        elif self._buffer:
            emitted = self._emit_safe_tokens(self._buffer)

        self._buffer = ""
        return emitted

    def sanitize_stream(self, stream: Iterable[str]) -> Generator[str]:
        """Consume an input stream and yield only clean markdown content tokens."""
        for chunk in stream:
            yield from self.feed(chunk)
        yield from self.flush()

    async def async_sanitize_stream(self, stream: AsyncIterable[str]) -> AsyncGenerator[str]:
        """Asynchronously consume an input stream and yield only clean markdown content tokens."""
        async for chunk in stream:
            for safe_token in self.feed(chunk):
                yield safe_token
        for final_token in self.flush():
            yield final_token

    @property
    def clean_content(self) -> str:
        """Return the accumulated clean content without reasoning tags."""
        return "".join(self._clean_chunks)

    @property
    def reasoning_scratchpad(self) -> str:
        """Return the accumulated reasoning scratchpad."""
        return "".join(self._reasoning_chunks)

    @property
    def total_bytes(self) -> int:
        """Return total bytes processed across all chunks."""
        return self._total_bytes

    @property
    def has_reasoning(self) -> bool:
        """Return True if any reasoning content or think block was encountered."""
        return bool(self._reasoning_chunks or self.thinking_detected)

    def to_dict(self) -> dict[str, Any]:
        """Return structured summary dictionary of processed stream."""
        return {
            "clean_content": self.clean_content,
            "reasoning_scratchpad": self.reasoning_scratchpad,
            "has_reasoning": self.has_reasoning,
            "total_bytes": self._total_bytes,
        }


StreamingReasoningSanitizer = StreamingTokenProcessor


@dataclass(frozen=True, slots=True)
class StreamFrame:
    """What one provider frame means: text to yield, and whether and why the reply ended."""

    chunk: str | None = None
    # The provider's final word arrived: the stream is complete, even if reading goes on.
    complete: bool = False
    # Nothing after this frame is read.
    last: bool = False
    finish_reason: FinishReason | None = None
    # The provider's own error message, which the reader raises.
    error: str | None = None


def _json_object(text: str) -> dict[str, Any]:
    """A frame's JSON object; an empty one for anything else, which carries nothing to read."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _error_text(error: object) -> str:
    """The message of an error frame's `error` value: a string, or an object with a message."""
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error)


def _ollama_message_text(message: object) -> str | None:
    """A chat message's thinking, wrapped in think tags, or else its content."""
    if not isinstance(message, dict):
        return None
    if thinking := message.get("thinking"):
        return f"<think>{thinking}</think>"
    content = message.get("content")
    return str(content) if content else None


def _ollama_stream_frame(line: str) -> StreamFrame:
    """One line of an Ollama chat stream; `done: true` is its final frame, with `done_reason`."""
    payload = _json_object(line)
    if payload.get("error") is not None:
        return StreamFrame(error=_error_text(payload["error"]))
    done = payload.get("done") is True
    return StreamFrame(
        chunk=_ollama_message_text(payload.get("message")),
        complete=done,
        last=done,
        finish_reason=provider_finish_reason(CONST_OLLAMA_DONE_REASONS, payload.get("done_reason")),
    )


def _claude_delta_text(delta: object) -> str | None:
    """A content block delta's text, or its thinking wrapped in think tags."""
    if not isinstance(delta, dict):
        return None
    delta_type = delta.get("type")
    if delta_type == "text_delta" and delta.get("text"):
        return str(delta["text"])
    if delta_type == "thinking_delta" and delta.get("thinking"):
        return f"<think>{delta['thinking']}</think>"
    return None


def _claude_message_delta(payload: dict[str, Any]) -> StreamFrame:
    """`message_delta` carries the reply's stop reason, ahead of the final `message_stop`."""
    delta = payload.get("delta")
    stop_reason = delta.get("stop_reason") if isinstance(delta, dict) else None
    return StreamFrame(
        finish_reason=provider_finish_reason(CONST_ANTHROPIC_STOP_REASONS, stop_reason)
    )


# The Anthropic Messages stream events that carry text, the reason, the end or an error. Every
# other event (message_start, content_block_start, content_block_stop, ping) carries none.
_CLAUDE_EVENT_FRAMES: Final[dict[str, Callable[[dict[str, Any]], StreamFrame]]] = {
    "content_block_delta": lambda payload: StreamFrame(
        chunk=_claude_delta_text(payload.get("delta"))
    ),
    "message_delta": _claude_message_delta,
    "message_stop": lambda _payload: StreamFrame(complete=True, last=True),
    "error": lambda payload: StreamFrame(error=_error_text(payload.get("error"))),
}


def _claude_stream_frame(event: httpx2.ServerSentEvent) -> StreamFrame:
    """One event of an Anthropic Messages stream; `message_stop` is its final frame.

    Anthropic never sends `[DONE]`, so it is not read as an end.
    """
    payload = _json_object(event.data)
    frame_for = _CLAUDE_EVENT_FRAMES.get(str(payload.get("type") or event.event))
    return frame_for(payload) if frame_for else StreamFrame()


def _openai_delta_text(delta: object) -> str | None:
    """A chat completion delta's reasoning, wrapped in think tags, or else its content."""
    if not isinstance(delta, dict):
        return None
    if reasoning := delta.get("reasoning_content") or delta.get("reasoning"):
        return f"<think>{reasoning}</think>"
    content = delta.get("content")
    return str(content) if content else None


def _first_choice(payload: dict[str, Any]) -> dict[str, Any]:
    """A completion chunk's first choice; an empty one when it has none, as a usage chunk."""
    choices = payload.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    return first if isinstance(first, dict) else {}


def _openai_stream_frame(event: httpx2.ServerSentEvent) -> StreamFrame:
    """One event of an OpenAI-compatible chat completion stream.

    A chunk with a finish reason completes the stream, and so does `[DONE]`, the server's own end
    marker, with no reason before it. Reading goes on past the reason to `[DONE]` or EOF, so a
    usage chunk sent after it is still read.
    """
    if event.data.strip() == "[DONE]":
        return StreamFrame(complete=True, last=True)
    payload = _json_object(event.data)
    if payload.get("error") is not None:
        return StreamFrame(error=_error_text(payload["error"]))
    choice = _first_choice(payload)
    reason = choice.get("finish_reason")
    return StreamFrame(
        chunk=_openai_delta_text(choice.get("delta")),
        complete=reason is not None,
        finish_reason=provider_finish_reason(CONST_OPENAI_FINISH_REASONS, reason),
    )


def _size_limit_text(limit_bytes: int) -> str:
    return (
        f"{limit_bytes // (1024 * 1024)}MB"
        if limit_bytes >= 1024 * 1024
        else f"{limit_bytes} bytes"
    )


def _check_stream_size(total_bytes: int, provider_name: str, max_stream_bytes: int) -> None:
    if total_bytes > max_stream_bytes:
        raise AIClientError(
            f"{provider_name} response exceeded maximum stream size "
            f"({_size_limit_text(max_stream_bytes)})."
        )


def _error_frame(provider_name: str, message: str) -> AIClientError:
    """The provider's error frame as an error, its message masked and cut to 256 characters."""
    return AIClientError(f"{provider_name} stream reported an error: {mask_secrets(message)[:256]}")


def _read_frames[FrameT](
    frames: Iterable[tuple[FrameT, int]],
    parse_frame: Callable[[FrameT], StreamFrame],
    provider_name: str,
    max_stream_bytes: int,
) -> Generator[str]:
    """Yield each frame's text as it arrives, until the provider's final frame.

    Every frame counts towards `max_stream_bytes` before it is parsed, including frames that
    carry no text. Once the stream is complete its finish reason is set in
    `stream_finish_reason`. An error frame, and a stream that ends before its final frame,
    raise `AIClientError`.
    """
    total_bytes = 0
    complete = False
    reason: FinishReason | None = None
    for raw_frame, frame_bytes in frames:
        total_bytes += frame_bytes
        _check_stream_size(total_bytes, provider_name, max_stream_bytes)
        frame = parse_frame(raw_frame)
        if frame.error is not None:
            raise _error_frame(provider_name, frame.error)
        if frame.chunk:
            yield frame.chunk
        complete = complete or frame.complete
        reason = frame.finish_reason or reason
        if frame.last:
            break
    if not complete:
        raise AIClientError(f"{provider_name} stream ended before its final frame.")
    stream_finish_reason.set(reason)


def _event_frames(
    response: httpx2.Response, max_event_bytes: int
) -> Iterator[tuple[httpx2.ServerSentEvent, int]]:
    """Each server-sent event with the size of its data.

    httpx2's EventSource splits lines on CR and LF alone, decodes a code point split across
    chunks, and refuses an event over `max_event_bytes` and a body that is not
    `text/event-stream`.
    """
    for event in httpx2.EventSource(response, max_event_size=max_event_bytes):
        yield event, len(event.data.encode("utf-8"))


def _check_line_size(line_bytes: int, provider_name: str, max_line_bytes: int) -> None:
    if line_bytes > max_line_bytes:
        raise AIClientError(
            f"{provider_name} stream line exceeded the {_size_limit_text(max_line_bytes)} limit."
        )


def _ndjson_line(raw: bytearray, provider_name: str, max_line_bytes: int) -> tuple[str, int]:
    _check_line_size(len(raw), provider_name, max_line_bytes)
    try:
        return raw.decode("utf-8"), len(raw)
    except UnicodeDecodeError as exc:
        raise AIClientError(f"{provider_name} stream line is not UTF-8: {exc}") from exc


def _ndjson_lines(
    response: httpx2.Response, provider_name: str, max_line_bytes: int
) -> Iterator[tuple[str, int]]:
    """Each line of a newline-delimited JSON body with its size, split on LF alone.

    A line is decoded once it is whole, so a code point split across chunks decodes intact and
    a U+2028 inside a JSON string stays in its line. A line still unterminated past
    `max_line_bytes` is refused rather than buffered; one unterminated at EOF is read as it is.
    """
    pending = bytearray()
    for data in response.iter_bytes():
        head, *rest = data.split(b"\n")
        pending += head
        for piece in rest:
            yield _ndjson_line(pending, provider_name, max_line_bytes)
            pending = bytearray(piece)
        _check_line_size(len(pending), provider_name, max_line_bytes)
    if pending:
        yield _ndjson_line(pending, provider_name, max_line_bytes)


@contextmanager
def _read_failures(provider_name: str) -> Iterator[None]:
    """Raise a failed read as `AIClientError`, never as an httpx2 request error.

    The Ollama host loop fails over on request and transport errors, so one escaping here would
    replay the request on the next host after output had been yielded. httpx2's SSEError, which
    a refused content type or an oversized event raises, is a TransportError too, and a body
    that fails to decompress raises a DecodingError.
    """
    try:
        yield
    except httpx2.SSEError as exc:
        raise AIClientError(f"{provider_name} stream could not be read: {str(exc)[:256]}") from exc
    except httpx2.RequestError as exc:
        raise AIClientError(
            f"{provider_name} streaming connection terminated unexpectedly: {str(exc)[:256]}"
        ) from exc


def _read_event_stream(
    response: httpx2.Response,
    parse_event: Callable[[httpx2.ServerSentEvent], StreamFrame],
    provider_name: str,
    *,
    max_event_bytes: int = DEFAULT_AI_STREAM_MAX_EVENT_BYTES,
    max_stream_bytes: int = MAX_STREAM_BYTES,
) -> Generator[str]:
    """Yield the text of a server-sent event stream as it arrives, until its final event."""
    with _read_failures(provider_name):
        yield from _read_frames(
            _event_frames(response, max_event_bytes), parse_event, provider_name, max_stream_bytes
        )


def _read_ndjson_stream(
    response: httpx2.Response,
    parse_line: Callable[[str], StreamFrame],
    provider_name: str,
    *,
    max_line_bytes: int = DEFAULT_AI_STREAM_MAX_EVENT_BYTES,
    max_stream_bytes: int = MAX_STREAM_BYTES,
) -> Generator[str]:
    """Yield the text of a newline-delimited JSON stream as it arrives, until its final line."""
    with _read_failures(provider_name):
        yield from _read_frames(
            _ndjson_lines(response, provider_name, max_line_bytes),
            parse_line,
            provider_name,
            max_stream_bytes,
        )
