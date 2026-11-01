"""Streaming utilities for token chunks, and readers for providers' event and NDJSON streams."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterable, Callable, Generator, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx2

from devops_cli.ai.client.models import MAX_STREAM_BYTES, AIClientError, provider_finish_reason
from devops_cli.ai.client.network import (
    StreamUsage,
    size_limit_text,
    stream_finish_reason,
    stream_usage,
)
from devops_cli.ai.thinking_stream import ThinkingFSM
from devops_cli.config.constants import (
    CONST_OLLAMA_DONE_REASONS,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_STREAM_MAX_EVENT_BYTES,
    DEFAULT_THINKING_INITIAL_STATE,
    DEFAULT_THINKING_MAX_THOUGHT_CHARS,
    DEFAULT_THINKING_TAGS,
)
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason
    from pydantic_ai.profiles import ModelProfileSpec


def _find_suffix_overlap(text: str, target: str) -> int:
    """Find the length of the longest suffix of text that matches a prefix of target."""
    max_check = min(len(text), len(target) - 1)
    for length in range(max_check, 0, -1):
        if target.startswith(text[-length:]):
            return length
    return 0


class StreamingTokenProcessor:
    """Standardized streaming token processor and reasoning scratchpad extractor.

    Parses streaming SSE tokens in real-time, extracts reasoning blocks into an
    isolated reasoning scratchpad, yields sanitized markdown content, and enforces
    strict MAX_STREAM_BYTES boundary limits.
    """

    def __init__(
        self,
        *,
        max_stream_bytes: int = MAX_STREAM_BYTES,
        thinking_tags: tuple[str, str] = DEFAULT_THINKING_TAGS,
        initial_state: str = DEFAULT_THINKING_INITIAL_STATE,
        max_thought_chars: int = DEFAULT_THINKING_MAX_THOUGHT_CHARS,
        model_profile: ModelProfileSpec | None = None,
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
        on_reasoning_start: Callable[[], None] | None = None,
        on_reasoning_end: Callable[[], None] | None = None,
    ) -> None:
        self.max_stream_bytes = max_stream_bytes
        self.on_token = on_token
        self.on_reasoning = on_reasoning
        self.on_reasoning_start = on_reasoning_start
        self.on_reasoning_end = on_reasoning_end

        self._total_bytes: int = 0
        self._fsm = ThinkingFSM(
            thinking_tags=thinking_tags,
            initial_state=initial_state,
            max_thought_chars=max_thought_chars,
            model_profile=model_profile,
            on_think_start=self._handle_reasoning_start,
            on_think_chunk=self._handle_reasoning,
            on_think_end=self._handle_reasoning_end,
            on_content_chunk=self._handle_token,
        )

    def _handle_reasoning_start(self) -> None:
        if self.on_reasoning_start:
            self.on_reasoning_start()

    def _handle_reasoning(self, chunk: str) -> None:
        if self.on_reasoning:
            self.on_reasoning(chunk)

    def _handle_reasoning_end(self) -> None:
        if self.on_reasoning_end:
            self.on_reasoning_end()

    def _handle_token(self, token: str) -> None:
        if self.on_token:
            self.on_token(token)

    @property
    def thinking_tags(self) -> tuple[str, str]:
        """Return effective thinking tags (open_tag, close_tag)."""
        return self._fsm.thinking_tags

    @property
    def open_tag(self) -> str:
        """Return opening tag for reasoning blocks."""
        return self._fsm.open_tag

    @property
    def close_tag(self) -> str:
        """Return closing tag for reasoning blocks."""
        return self._fsm.close_tag

    @property
    def in_think(self) -> bool:
        """Return True if currently inside a reasoning block."""
        return self._fsm.in_think

    @property
    def unopened_close_tags(self) -> int:
        """Return count of unopened closing tags encountered while emitting."""
        return self._fsm.unopened_close_tags

    @property
    def unclosed_stream(self) -> bool:
        """Return True if stream terminated while inside a thinking block."""
        return self._fsm.unclosed_stream

    @property
    def discarded_thought_chars(self) -> int:
        """Return count of thought characters discarded due to buffer cap."""
        return self._fsm.discarded_thought_chars

    @property
    def clean_content(self) -> str:
        """Return accumulated clean content without reasoning tags."""
        return self._fsm.clean_content

    @property
    def reasoning_scratchpad(self) -> str:
        """Return accumulated reasoning scratchpad."""
        return self._fsm.thinking_content

    @property
    def total_bytes(self) -> int:
        """Return total bytes processed across all chunks."""
        return self._total_bytes

    @property
    def has_reasoning(self) -> bool:
        """Return True if any reasoning content or think block was encountered."""
        return bool(
            self._fsm.thinking_content
            or self._fsm.think_started
            or self._fsm.discarded_thought_chars
        )

    def _record_bytes(self, chunk: str) -> None:
        self._total_bytes += len(chunk.encode("utf-8"))
        if self._total_bytes > self.max_stream_bytes:
            raise AIClientError(
                f"Stream exceeded maximum size limit of {size_limit_text(self.max_stream_bytes)}."
            )

    def feed(self, chunk: str, *, is_thinking: bool = False) -> list[str]:
        """Feed a streaming chunk into the processor and return newly safe clean tokens."""
        if not chunk:
            return []
        self._record_bytes(chunk)
        return self._fsm.feed(chunk, is_thinking=is_thinking)

    def flush(self) -> list[str]:
        """Flush remaining buffered tokens and finalize reasoning states."""
        return self._fsm.flush()

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

    def to_dict(self) -> dict[str, Any]:
        """Return structured summary dictionary of processed stream."""
        return {
            "clean_content": self.clean_content,
            "reasoning_scratchpad": self.reasoning_scratchpad,
            "has_reasoning": self.has_reasoning,
            "total_bytes": self._total_bytes,
            "unopened_close_tags": self.unopened_close_tags,
            "unclosed_stream": self.unclosed_stream,
            "discarded_thought_chars": self.discarded_thought_chars,
        }


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
    if done:
        prompt_eval = payload.get("prompt_eval_count")
        eval_count = payload.get("eval_count")
        if prompt_eval is not None or eval_count is not None:
            total = (
                (prompt_eval or 0) + (eval_count or 0)
                if (prompt_eval is not None and eval_count is not None)
                else None
            )
            stream_usage.set(
                StreamUsage(
                    prompt_tokens=prompt_eval,
                    completion_tokens=eval_count,
                    total_tokens=total,
                    reasoning_tokens=None,
                )
            )
    return StreamFrame(
        chunk=_ollama_message_text(payload.get("message")),
        complete=done,
        last=done,
        finish_reason=provider_finish_reason(CONST_OLLAMA_DONE_REASONS, payload.get("done_reason")),
    )


def _check_stream_size(total_bytes: int, provider_name: str, max_stream_bytes: int) -> None:
    if total_bytes > max_stream_bytes:
        raise AIClientError(
            f"{provider_name} response exceeded maximum stream size "
            f"({size_limit_text(max_stream_bytes)})."
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
            f"{provider_name} stream line exceeded the {size_limit_text(max_line_bytes)} limit."
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
            f"{provider_name} streaming connection terminated unexpectedly: {str(exc)[:256]}",
            timed_out=isinstance(exc, httpx2.TimeoutException),
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
