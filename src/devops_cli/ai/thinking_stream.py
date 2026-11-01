"""Thinking and reasoning block parser and streaming output processor for AI chat."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from devops_cli.ai.profiles import _apply_profile_spec, get_model_thinking_tags
from devops_cli.ai.text_utils import unique_lines
from devops_cli.config.constants import (
    CONST_THINKING_STATE_THINKING,
)
from devops_cli.config.defaults import (
    DEFAULT_THINKING_INITIAL_STATE,
    DEFAULT_THINKING_MAX_THOUGHT_CHARS,
    DEFAULT_THINKING_TAGS,
)
from devops_cli.output import escape_text, get_console

if TYPE_CHECKING:
    from pydantic_ai.profiles import ModelProfileSpec

DEFAULT_TAGS: tuple[str, str] = DEFAULT_THINKING_TAGS


def _find_suffix_overlap(text: str, target: str) -> int:
    """Find length of longest suffix of text that matches prefix of target."""
    max_check = min(len(text), len(target) - 1)
    for length in range(max_check, 0, -1):
        if target.startswith(text[-length:]):
            return length
    return 0


class ThinkingFSM:
    """State machine core for reasoning block extraction and token sanitization."""

    def __init__(
        self,
        thinking_tags: tuple[str, str] = DEFAULT_THINKING_TAGS,
        initial_state: str = DEFAULT_THINKING_INITIAL_STATE,
        max_thought_chars: int = DEFAULT_THINKING_MAX_THOUGHT_CHARS,
        model_profile: ModelProfileSpec | None = None,
        on_think_start: Callable[[], None] | None = None,
        on_think_chunk: Callable[[str], None] | None = None,
        on_think_end: Callable[[], None] | None = None,
        on_content_chunk: Callable[[str], None] | None = None,
    ) -> None:
        resolved_profile = _apply_profile_spec(model_profile) if model_profile is not None else None
        effective_tags = (
            get_model_thinking_tags(profile=model_profile)
            if (model_profile is not None and thinking_tags == DEFAULT_THINKING_TAGS)
            else thinking_tags
        )
        if len(effective_tags) != 2 or not effective_tags[0] or not effective_tags[1]:
            raise ValueError(
                "thinking_tags must be a tuple of two non-empty strings (open_tag, close_tag)."
            )

        effective_state = (
            str(resolved_profile.get("initial_state", initial_state))
            if (resolved_profile is not None and "initial_state" in resolved_profile)
            else initial_state
        )

        self.thinking_tags = effective_tags
        self.open_tag = effective_tags[0]
        self.close_tag = effective_tags[1]
        self.initial_state = effective_state
        self.max_thought_chars = max_thought_chars

        self.on_think_start = on_think_start
        self.on_think_chunk = on_think_chunk
        self.on_think_end = on_think_end
        self.on_content_chunk = on_content_chunk

        self.in_think: bool = effective_state == CONST_THINKING_STATE_THINKING
        self.think_started: bool = effective_state == CONST_THINKING_STATE_THINKING
        self.think_ended: bool = False
        self.unclosed_stream: bool = False
        self.unopened_close_tags: int = 0
        self.discarded_thought_chars: int = 0

        self._explicit_thinking_active: bool = False
        self._buffer: str = ""
        self._current_block: str = ""
        self.thinking_blocks: list[str] = []
        self.clean_content: str = ""
        self.thinking_content: str = ""

        if self.think_started and self.on_think_start:
            self.on_think_start()

    def _trigger_think_start(self) -> None:
        if not self.think_started:
            self.think_started = True
            self.think_ended = False
            if self.on_think_start:
                self.on_think_start()

    def _trigger_think_end(self) -> None:
        if self.think_started and not self.think_ended:
            self.think_ended = True
            self.think_started = False
            if self._current_block:
                self.thinking_blocks.append(self._current_block)
                self._current_block = ""
            if self.on_think_end:
                self.on_think_end()

    def _finalize_footer(self) -> None:
        self._trigger_think_end()

    def _record_thought(self, chunk: str) -> None:
        if not chunk:
            return
        current_len = len(self.thinking_content)
        if current_len >= self.max_thought_chars:
            self.discarded_thought_chars += len(chunk)
            return

        available = self.max_thought_chars - current_len
        if len(chunk) <= available:
            self.thinking_content += chunk
            self._current_block += chunk
            if self.on_think_chunk:
                self.on_think_chunk(chunk)
            return

        kept = chunk[:available]
        self.thinking_content += kept
        self._current_block += kept
        self.discarded_thought_chars += len(chunk) - available
        if self.on_think_chunk:
            self.on_think_chunk(kept)

    def _emit_content(self, text: str) -> list[str]:
        if not text:
            return []
        self._finalize_footer()
        self.clean_content += text
        if self.on_content_chunk:
            self.on_content_chunk(text)
        return [text]

    def _handle_explicit_thinking(self, chunk: str) -> list[str]:
        self._explicit_thinking_active = True
        self._trigger_think_start()
        self._record_thought(chunk)
        return []

    def _process_inside_think(self) -> tuple[bool, list[str]]:
        close_pos = self._buffer.find(self.close_tag)
        if close_pos != -1:
            thought_chunk = self._buffer[:close_pos]
            self.in_think = False
            self._buffer = self._buffer[close_pos + len(self.close_tag) :]
            self._record_thought(thought_chunk)
            if self._current_block:
                self.thinking_blocks.append(self._current_block)
                self._current_block = ""
            return True, []

        overlap = _find_suffix_overlap(self._buffer, self.close_tag)
        if overlap > 0:
            safe_thought = self._buffer[:-overlap]
            self._buffer = self._buffer[-overlap:]
            self._record_thought(safe_thought)
            return False, []

        self._record_thought(self._buffer)
        self._buffer = ""
        return True, []

    def _process_outside_think(self) -> tuple[bool, list[str]]:
        open_pos = self._buffer.find(self.open_tag)
        close_pos = self._buffer.find(self.close_tag)

        if close_pos != -1 and (open_pos == -1 or close_pos < open_pos):
            prefix = self._buffer[:close_pos]
            self.unopened_close_tags += 1
            self._buffer = self._buffer[close_pos + len(self.close_tag) :]
            tokens = self._emit_content(prefix) if prefix else []
            return True, tokens

        if open_pos != -1:
            prefix = self._buffer[:open_pos]
            self.in_think = True
            self._trigger_think_start()
            self._buffer = self._buffer[open_pos + len(self.open_tag) :]
            tokens = self._emit_content(prefix) if prefix else []
            return True, tokens

        open_overlap = _find_suffix_overlap(self._buffer, self.open_tag)
        close_overlap = _find_suffix_overlap(self._buffer, self.close_tag)
        overlap = max(open_overlap, close_overlap)

        if overlap > 0:
            safe = self._buffer[:-overlap]
            self._buffer = self._buffer[-overlap:]
            tokens = self._emit_content(safe) if safe else []
            return False, tokens

        tokens = self._emit_content(self._buffer)
        self._buffer = ""
        return True, tokens

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
        """Feed a new streaming token chunk into the state machine."""
        if not chunk:
            return []
        if is_thinking:
            return self._handle_explicit_thinking(chunk)
        if self._explicit_thinking_active:
            self._explicit_thinking_active = False
            if self._current_block:
                self.thinking_blocks.append(self._current_block)
                self._current_block = ""
            self._finalize_footer()
        self._buffer += chunk
        return self._process_buffer()

    def flush(self) -> list[str]:
        """Flush remaining buffered tokens at end of stream."""
        emitted: list[str] = []
        if self._explicit_thinking_active:
            self._explicit_thinking_active = False
            if self._current_block:
                self.thinking_blocks.append(self._current_block)
                self._current_block = ""
            self._finalize_footer()

        if self.in_think:
            self.unclosed_stream = True
            if self._buffer:
                self._record_thought(self._buffer)
                self._buffer = ""
        elif self._buffer:
            emitted = self._emit_content(self._buffer)
            self._buffer = ""

        if self._current_block:
            self.thinking_blocks.append(self._current_block)
            self._current_block = ""

        self._finalize_footer()
        return emitted


class ThinkingStreamProcessor:
    """Stateful streaming token parser for rendering or suppressing thinking blocks in CLI chat."""

    def __init__(
        self,
        show_thinking: bool = True,
        console: Any = None,
        thinking_tags: tuple[str, str] = DEFAULT_TAGS,
        initial_state: str = DEFAULT_THINKING_INITIAL_STATE,
        max_thought_chars: int = DEFAULT_THINKING_MAX_THOUGHT_CHARS,
        model_profile: ModelProfileSpec | None = None,
        on_think_start: Callable[[], None] | None = None,
        on_think_chunk: Callable[[str], None] | None = None,
        on_think_end: Callable[[], None] | None = None,
        on_content_chunk: Callable[[str], None] | None = None,
    ) -> None:
        self.show_thinking = show_thinking
        self.console = console
        self._on_think_start = on_think_start
        self._on_think_chunk = on_think_chunk
        self._on_think_end = on_think_end
        self._on_content_chunk = on_content_chunk

        self._fsm = ThinkingFSM(
            thinking_tags=thinking_tags,
            initial_state=initial_state,
            max_thought_chars=max_thought_chars,
            model_profile=model_profile,
            on_think_start=self._handle_think_start,
            on_think_chunk=self._handle_think_chunk,
            on_think_end=self._handle_think_end,
            on_content_chunk=self._handle_content_chunk,
        )

    def _handle_think_start(self) -> None:
        if self._on_think_start:
            self._on_think_start()
        elif self.show_thinking:
            c = self.console or get_console()
            c.print("[dim cyan]💭 Thinking...[/dim cyan]")

    def _handle_think_chunk(self, chunk: str) -> None:
        if self._on_think_chunk:
            self._on_think_chunk(chunk)
        elif self.show_thinking:
            c = self.console or get_console()
            c.print(f"[dim italic]{escape_text(chunk)}[/dim italic]", end="")

    def _handle_think_end(self) -> None:
        if self._on_think_end:
            self._on_think_end()
        elif self.show_thinking:
            c = self.console or get_console()
            c.print("\n[dim cyan]✓ Thought complete[/dim cyan]\n")

    def _handle_content_chunk(self, chunk: str) -> None:
        if self._on_content_chunk:
            self._on_content_chunk(chunk)
        else:
            c = self.console or get_console()
            c.print(escape_text(chunk), end="")

    @property
    def clean_content(self) -> str:
        """Return accumulated clean content without thinking blocks."""
        return self._fsm.clean_content

    @property
    def thinking_content(self) -> str:
        """Return accumulated thinking content."""
        return self._fsm.thinking_content

    @property
    def reasoning_scratchpad(self) -> str:
        """Standardized reasoning scratchpad buffer containing extracted thinking tokens."""
        return self._fsm.thinking_content

    @property
    def in_think(self) -> bool:
        """Return True when parser is currently inside a thinking block."""
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

    def feed(self, chunk: str) -> None:
        """Feed a new streaming token chunk into the processor."""
        self._fsm.feed(chunk)

    def flush(self) -> None:
        """Flush any remaining buffered tokens at end of stream."""
        self._fsm.flush()

    def to_dict(self) -> dict[str, Any]:
        """Return structured summary dictionary of processed stream."""
        return {
            "clean_content": self.clean_content,
            "thinking_content": self.thinking_content,
            "reasoning_scratchpad": self.reasoning_scratchpad,
            "has_reasoning": bool(self.thinking_content or self._fsm.think_started),
            "unopened_close_tags": self.unopened_close_tags,
            "unclosed_stream": self.unclosed_stream,
            "discarded_thought_chars": self.discarded_thought_chars,
        }

    def to_model_response(self, model_name: str | None = None) -> Any:
        """Construct a ModelResponse from accumulated thinking and content."""
        from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart
        from pydantic_ai.usage import RequestUsage

        parts: list[Any] = []
        if self.thinking_content.strip():
            parts.append(ThinkingPart(content=unique_lines(self.thinking_content.strip())))
        if self.clean_content.strip():
            parts.append(TextPart(content=self.clean_content.strip()))
        return ModelResponse(parts=parts, model_name=model_name, usage=RequestUsage())


def strip_think_blocks(
    text: str,
    thinking_tags: tuple[str, str] = DEFAULT_TAGS,
    max_thought_chars: int = DEFAULT_THINKING_MAX_THOUGHT_CHARS,
    initial_state: str = DEFAULT_THINKING_INITIAL_STATE,
    model_profile: ModelProfileSpec | None = None,
) -> str:
    """Remove chain-of-thought blocks from complete text using the shared FSM core."""
    if not text:
        setattr(strip_think_blocks, "unopened_close_tags", 0)
        setattr(strip_think_blocks, "discarded_thought_chars", 0)
        setattr(strip_think_blocks, "unclosed_stream", False)
        setattr(strip_think_blocks, "thinking_content", "")
        return ""
    fsm = ThinkingFSM(
        thinking_tags=thinking_tags,
        max_thought_chars=max_thought_chars,
        initial_state=initial_state,
        model_profile=model_profile,
    )
    fsm.feed(text)
    fsm.flush()
    setattr(strip_think_blocks, "unopened_close_tags", fsm.unopened_close_tags)
    setattr(strip_think_blocks, "discarded_thought_chars", fsm.discarded_thought_chars)
    setattr(strip_think_blocks, "unclosed_stream", fsm.unclosed_stream)
    setattr(strip_think_blocks, "thinking_content", fsm.thinking_content)
    return fsm.clean_content.strip()


setattr(strip_think_blocks, "unopened_close_tags", 0)
setattr(strip_think_blocks, "discarded_thought_chars", 0)
setattr(strip_think_blocks, "unclosed_stream", False)
setattr(strip_think_blocks, "thinking_content", "")


def extract_think_blocks(
    text: str,
    thinking_tags: tuple[str, str] = DEFAULT_TAGS,
    max_thought_chars: int = DEFAULT_THINKING_MAX_THOUGHT_CHARS,
    initial_state: str = DEFAULT_THINKING_INITIAL_STATE,
    model_profile: ModelProfileSpec | None = None,
) -> tuple[list[str], str]:
    """Extract think blocks and return (list_of_think_contents, clean_text) using the shared FSM core."""
    if not text:
        setattr(extract_think_blocks, "unopened_close_tags", 0)
        setattr(extract_think_blocks, "discarded_thought_chars", 0)
        setattr(extract_think_blocks, "unclosed_stream", False)
        setattr(extract_think_blocks, "thinking_content", "")
        return [], ""
    fsm = ThinkingFSM(
        thinking_tags=thinking_tags,
        max_thought_chars=max_thought_chars,
        initial_state=initial_state,
        model_profile=model_profile,
    )
    fsm.feed(text)
    fsm.flush()
    setattr(extract_think_blocks, "unopened_close_tags", fsm.unopened_close_tags)
    setattr(extract_think_blocks, "discarded_thought_chars", fsm.discarded_thought_chars)
    setattr(extract_think_blocks, "unclosed_stream", fsm.unclosed_stream)
    setattr(extract_think_blocks, "thinking_content", fsm.thinking_content)
    blocks = [b.strip() for b in fsm.thinking_blocks if b.strip()]
    if not blocks and fsm.thinking_content.strip():
        blocks = [fsm.thinking_content.strip()]
    return blocks, fsm.clean_content.strip()


setattr(extract_think_blocks, "unopened_close_tags", 0)
setattr(extract_think_blocks, "discarded_thought_chars", 0)
setattr(extract_think_blocks, "unclosed_stream", False)
setattr(extract_think_blocks, "thinking_content", "")


__all__ = [
    "DEFAULT_TAGS",
    "ThinkingFSM",
    "ThinkingStreamProcessor",
    "extract_think_blocks",
    "strip_think_blocks",
]
