"""Thinking / reasoning block parser and streaming output processor for AI chat."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable

from rich.console import Console


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> chain-of-thought blocks from complete text."""
    if not text:
        return ""
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if not clean and "<think>" in text:
        inner = re.findall(r"<think>(.*?)(?:</think>|$)", text, flags=re.DOTALL)
        if inner:
            for candidate in reversed(inner):
                cand_strip = str(candidate).strip()
                if "{" in cand_strip and "}" in cand_strip:
                    return str(cand_strip)
            return str(inner[-1]).strip()
    return clean


def extract_think_blocks(text: str) -> tuple[list[str], str]:
    """Extract think blocks and return (list_of_think_contents, clean_text)."""
    if not text:
        return [], ""
    thinks = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL)
    clean = strip_think_blocks(text)
    return [t.strip() for t in thinks], clean


class ThinkingStreamProcessor:
    """Stateful streaming token parser for rendering or suppressing thinking blocks in CLI chat."""

    def __init__(
        self,
        show_thinking: bool = True,
        console: Console | None = None,
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
                out = self.console.print if self.console else print
                out("[dim cyan]💭 Thinking...[/dim cyan]")

    def _handle_think_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        self.thinking_content += chunk
        if self.on_think_chunk:
            self.on_think_chunk(chunk)
        elif self.show_thinking:
            if self.console:
                self.console.print(f"[dim italic]{chunk}[/dim italic]", end="")
            else:
                sys.stdout.write(chunk)
                sys.stdout.flush()

    def _handle_think_end(self) -> None:
        self.in_think = False

    def _finalize_thinking_footer(self) -> None:
        if self.think_started and not self.think_ended:
            self.think_ended = True
            if self.on_think_end:
                self.on_think_end()
            elif self.show_thinking:
                out = self.console.print if self.console else print
                out("\n[dim cyan]✓ Thought complete[/dim cyan]\n")

    def _handle_content_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        self._finalize_thinking_footer()
        self.clean_content += chunk
        if self.on_content_chunk:
            self.on_content_chunk(chunk)
        else:
            if self.console:
                self.console.print(chunk, end="")
            else:
                sys.stdout.write(chunk)
                sys.stdout.flush()

    def feed(self, chunk: str) -> None:
        """Feed a new streaming token chunk into the processor."""
        self._buffer += chunk
        self._process_buffer()

    def _process_buffer(self) -> None:
        while self._buffer:
            if not self.in_think:
                pos = self._buffer.find("<think>")
                if pos != -1:
                    content = self._buffer[:pos]
                    if content:
                        self._handle_content_chunk(content)
                    self.in_think = True
                    self._handle_think_start()
                    self._buffer = self._buffer[pos + 7 :]
                else:
                    buf = self._buffer
                    match_len = 0
                    for i in range(1, min(len(buf), 7) + 1):
                        if "<think>".startswith(buf[-i:]):
                            match_len = i
                    if match_len > 0:
                        safe_content = buf[:-match_len]
                        if safe_content:
                            self._handle_content_chunk(safe_content)
                        self._buffer = buf[-match_len:]
                        break
                    else:
                        self._handle_content_chunk(buf)
                        self._buffer = ""
            else:
                pos = self._buffer.find("</think>")
                if pos != -1:
                    think_chunk = self._buffer[:pos]
                    if think_chunk:
                        self._handle_think_chunk(think_chunk)
                    self._handle_think_end()
                    self._buffer = self._buffer[pos + 8 :]
                else:
                    buf = self._buffer
                    match_len = 0
                    for i in range(1, min(len(buf), 8) + 1):
                        if "</think>".startswith(buf[-i:]):
                            match_len = i
                    if match_len > 0:
                        safe_think = buf[:-match_len]
                        if safe_think:
                            self._handle_think_chunk(safe_think)
                        self._buffer = buf[-match_len:]
                        break
                    else:
                        self._handle_think_chunk(buf)
                        self._buffer = ""

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
