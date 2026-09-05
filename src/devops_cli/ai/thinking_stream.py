"""Thinking / reasoning block parser and streaming output processor for AI chat."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from devops_cli.output import escape_text, get_console


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> chain-of-thought blocks from complete text."""
    if not text:
        return ""
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in clean:
        clean = re.sub(r"<think>[\s\S]*$", "", clean)
    return clean.strip()


def extract_think_blocks(text: str) -> tuple[list[str], str]:
    """Extract think blocks and return (list_of_think_contents, clean_text)."""
    if not text:
        return [], ""
    thinks = re.findall(r"<think>(.*?)(?:</think>|$)", text, flags=re.DOTALL)
    clean = strip_think_blocks(text)
    return [t.strip() for t in thinks if t.strip()], clean


def _find_suffix_overlap(text: str, target: str) -> int:
    """Find the length of the longest suffix of text that matches a prefix of target."""
    max_check = min(len(text), len(target) - 1)
    for length in range(max_check, 0, -1):
        if target.startswith(text[-length:]):
            return length
    return 0


class ThinkingStreamProcessor:
    """Stateful streaming token parser for rendering or suppressing thinking blocks in CLI chat."""

    def __init__(
        self,
        show_thinking: bool = True,
        console: Any = None,
        on_think_start: Callable[[], None] | None = None,
        on_think_chunk: Callable[[str], None] | None = None,
        on_think_end: Callable[[], None] | None = None,
        on_content_chunk: Callable[[str], None] | None = None,
    ) -> None:
        self.show_thinking = show_thinking
        self.console = console
        self.on_think_start = on_think_start
        self.on_think_chunk = on_think_chunk
        self.on_think_end = on_think_end
        self.on_content_chunk = on_content_chunk

        self.in_think = False
        self.think_started = False
        self.think_ended = False
        self._buffer = ""
        self.clean_content = ""
        self.thinking_content = ""

    def _handle_think_start(self) -> None:
        if not self.think_started:
            self.think_started = True
            if self.on_think_start:
                self.on_think_start()
            elif self.show_thinking:
                c = self.console or get_console()
                c.print("[dim cyan]💭 Thinking...[/dim cyan]")

    def _handle_stream_chunk(self, chunk: str, is_thinking: bool = False) -> None:
        """Append stream chunk to appropriate buffer and dispatch to callback or console."""
        if not chunk:
            return
        if is_thinking:
            self.thinking_content += chunk
            callback = self.on_think_chunk
            format_spec = "[dim italic]{}[/dim italic]"
            should_emit = self.show_thinking
        else:
            self._finalize_thinking_footer()
            self.clean_content += chunk
            callback = self.on_content_chunk
            format_spec = "{}"
            should_emit = True

        if callback:
            callback(chunk)
        elif should_emit:
            c = self.console or get_console()
            c.print(format_spec.format(escape_text(chunk)), end="")

    def _handle_think_chunk(self, chunk: str) -> None:
        self._handle_stream_chunk(chunk, is_thinking=True)

    def _handle_think_end(self) -> None:
        self.in_think = False

    def _finalize_thinking_footer(self) -> None:
        if self.think_started and not self.think_ended:
            self.think_ended = True
            if self.on_think_end:
                self.on_think_end()
            elif self.show_thinking:
                c = self.console or get_console()
                c.print("\n[dim cyan]✓ Thought complete[/dim cyan]\n")

    def _handle_content_chunk(self, chunk: str) -> None:
        self._handle_stream_chunk(chunk, is_thinking=False)

    def feed(self, chunk: str) -> None:
        """Feed a new streaming token chunk into the processor."""
        self._buffer += chunk
        self._process_buffer()

    def _process_outside_think(self) -> bool:
        """Process buffer while outside <think> block. Returns False to break loop."""
        pos = self._buffer.find("<think>")
        if pos != -1:
            content = self._buffer[:pos]
            if content:
                self._handle_content_chunk(content)
            self.in_think = True
            self._handle_think_start()
            self._buffer = self._buffer[pos + 7 :]
            return True

        match_len = _find_suffix_overlap(self._buffer, "<think>")
        if match_len > 0:
            safe_content = self._buffer[:-match_len]
            if safe_content:
                self._handle_content_chunk(safe_content)
            self._buffer = self._buffer[-match_len:]
            return False

        self._handle_content_chunk(self._buffer)
        self._buffer = ""
        return True

    def _process_inside_think(self) -> bool:
        """Process buffer while inside <think> block. Returns False to break loop."""
        pos = self._buffer.find("</think>")
        if pos != -1:
            think_chunk = self._buffer[:pos]
            if think_chunk:
                self._handle_think_chunk(think_chunk)
            self._handle_think_end()
            self._buffer = self._buffer[pos + 8 :]
            return True

        match_len = _find_suffix_overlap(self._buffer, "</think>")
        if match_len > 0:
            safe_think = self._buffer[:-match_len]
            if safe_think:
                self._handle_think_chunk(safe_think)
            self._buffer = self._buffer[-match_len:]
            return False

        self._handle_think_chunk(self._buffer)
        self._buffer = ""
        return True

    def _process_buffer(self) -> None:
        while self._buffer:
            cont = self._process_inside_think() if self.in_think else self._process_outside_think()
            if not cont:
                break

    def flush(self) -> None:
        """Flush any remaining buffered tokens at end of stream."""
        if self._buffer:
            if self.in_think:
                self._handle_think_chunk(self._buffer)
                self._handle_think_end()
            else:
                self._handle_content_chunk(self._buffer)
            self._buffer = ""
        self._finalize_thinking_footer()

    @property
    def unique_thinking(self) -> str:
        """Return accumulated thinking content with duplicate lines removed using a set."""
        from devops_cli.ai.review_schema import unique_lines

        return unique_lines(self.thinking_content)

    def to_model_response(self, model_name: str | None = None) -> Any:
        """Construct a ModelResponse from accumulated thinking and content."""
        from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart
        from pydantic_ai.usage import RequestUsage

        from devops_cli.ai.review_schema import unique_lines

        parts: list[Any] = []
        if self.thinking_content.strip():
            parts.append(ThinkingPart(content=unique_lines(self.thinking_content.strip())))
        if self.clean_content.strip():
            parts.append(TextPart(content=self.clean_content.strip()))
        return ModelResponse(parts=parts, model_name=model_name, usage=RequestUsage())
