"""Streaming utilities for token chunks and SSE event streams."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterable, Callable, Generator, Iterable
from typing import Any

import httpx2

from devops_cli.ai.client.models import MAX_STREAM_BYTES, AIClientError


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


def _extract_ollama_stream_chunk(line: str) -> str | None:
    """Extract content or thinking chunk from an Ollama stream line."""
    if not line:
        return None
    try:
        line_data = json.loads(line)
    except json.JSONDecodeError:
        return None
    msg = line_data.get("message", {})
    content = msg.get("content", "")
    thinking = msg.get("thinking", "")
    if thinking:
        return f"<think>{thinking}</think>"
    if content:
        return str(content)
    return None


def _extract_claude_stream_chunk(line: str) -> tuple[str | None, bool]:
    """Extract content chunk from Claude SSE stream line. Returns (chunk, is_done)."""
    if not line or not line.startswith("data:"):
        return (None, False)
    raw_data = line.removeprefix("data:").strip()
    if raw_data == "[DONE]":
        return (None, True)
    try:
        event_json = json.loads(raw_data)
    except json.JSONDecodeError:
        return (None, False)
    if event_json.get("type") == "content_block_delta":
        delta = event_json.get("delta", {})
        delta_type = delta.get("type")
        if delta_type == "text_delta":
            text_val = delta.get("text", "")
            if text_val:
                return (str(text_val), False)
        if delta_type == "thinking_delta":
            think_val = delta.get("thinking", "")
            if think_val:
                return (f"<think>{think_val}</think>", False)
    return (None, False)


def _extract_openai_stream_chunk(line: str) -> tuple[str | None, bool]:
    """Extract content chunk from OpenAI SSE stream line. Returns (chunk, is_done)."""
    if not line or not line.startswith("data:"):
        return (None, False)
    raw_data = line.removeprefix("data:").strip()
    if raw_data == "[DONE]":
        return (None, True)
    try:
        event_json = json.loads(raw_data)
    except json.JSONDecodeError:
        return (None, False)
    choices = event_json.get("choices", [])
    if choices:
        delta = choices[0].get("delta", {})
        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
        if reasoning:
            return (f"<think>{reasoning}</think>", False)
        content = delta.get("content")
        if content:
            return (str(content), False)
    return (None, False)


def _extract_ollama_stream_tuple(line: str) -> tuple[str | None, bool]:
    """Extract content or thinking chunk from Ollama stream line as (chunk, is_done)."""
    return (_extract_ollama_stream_chunk(line), False)


def _extract_stream_chunk(line: str, provider: str) -> tuple[str | None, bool]:
    """Unified chunk extractor dispatching to provider-specific parser."""
    norm_p = provider.lower()
    if norm_p in ("claude", "anthropic"):
        return _extract_claude_stream_chunk(line)
    if norm_p in ("openai", "copilot", "github_copilot"):
        return _extract_openai_stream_chunk(line)
    return _extract_ollama_stream_tuple(line)


def _read_response_lines(
    response: httpx2.Response,
    chunk_extractor: Callable[[str], tuple[str | None, bool]],
    provider_name: str,
    max_bytes: int,
    initial_bytes: int,
) -> Generator[tuple[str, int]]:
    """Iterate response lines and yield (chunk_str, cumulative_bytes)."""
    current_bytes = initial_bytes
    for line in response.iter_lines():
        line_bytes = len(line.encode("utf-8")) if isinstance(line, str) else len(line)
        current_bytes += line_bytes
        if current_bytes > max_bytes:
            limit_str = (
                f"{max_bytes // (1024 * 1024)}MB"
                if max_bytes >= 1024 * 1024
                else f"{max_bytes} bytes"
            )
            raise AIClientError(
                f"{provider_name} response exceeded maximum stream size ({limit_str})."
            )
        chunk_str, is_done = chunk_extractor(line)
        if is_done:
            break
        if chunk_str is None:
            continue
        yield chunk_str, current_bytes


def _consume_streaming_lines(
    response: httpx2.Response,
    chunk_extractor: Callable[[str], tuple[str | None, bool]],
    provider_name: str,
    *,
    max_stream_bytes: int | None = None,
) -> Generator[str]:
    """Yield extracted tokens from an HTTP streaming response with bounded size and error safety."""
    import devops_cli.ai.client as client_pkg
    import devops_cli.ai.client.models as client_models

    effective_max = (
        max_stream_bytes
        if max_stream_bytes is not None
        else getattr(
            client_pkg,
            "MAX_STREAM_BYTES",
            getattr(client_models, "MAX_STREAM_BYTES", MAX_STREAM_BYTES),
        )
    )
    total_bytes = 0
    try:
        for chunk_str, total_bytes in _read_response_lines(
            response, chunk_extractor, provider_name, effective_max, total_bytes
        ):
            yield chunk_str
    except (
        httpx2.RemoteProtocolError,
        httpx2.ReadTimeout,
        httpx2.TransportError,
        httpx2.ReadError,
    ) as exc:
        safe_err = str(exc)[:256]
        raise AIClientError(
            f"{provider_name} streaming connection terminated unexpectedly: {safe_err}"
        ) from exc
