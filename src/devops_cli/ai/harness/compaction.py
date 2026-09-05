"""Compaction strategies and context usage management."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
import uuid
import warnings
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import (
    AgentTool,
    BaseCapability,
    RunContext,
    Tool,
)
from devops_cli.ai.harness.constants import DEFAULT_SUMMARIZING_INSTRUCTIONS
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)


class TruncationStrategy(StrEnum):
    """Strategies for clamping oversized tool return text."""

    head = "head"
    tail = "tail"
    head_tail = "head_tail"


class Passthrough(BaseModel):
    """No-op reduction action leaving matching returns untouched."""

    model_config = ConfigDict(extra="ignore")


_TRUNCATION_FORMATTERS: dict[str, Callable[[str, int], str]] = {
    "head": lambda t, m: t[:m] + f"\n\n[... {len(t) - m} characters truncated ...]",
    "tail": lambda t, m: f"[... {len(t) - m} characters truncated ...]\n\n" + t[-m:],
}


def _truncate_head_tail(text: str, max_chars: int) -> str:
    half = max_chars // 2
    return (
        text[:half]
        + f"\n\n[... {len(text) - max_chars} characters truncated ...]\n\n"
        + text[-half:]
    )


class Truncate(BaseModel):
    """Clamps return text to a character budget."""

    model_config = ConfigDict(extra="ignore")

    max_chars: int = 5000
    strategy: TruncationStrategy | str = TruncationStrategy.head_tail
    then: Any | None = None

    def reduce(self, text: str) -> str:
        """Clamp text according to strategy."""
        if len(text) <= self.max_chars:
            return text
        strat = (
            self.strategy.value
            if isinstance(self.strategy, TruncationStrategy)
            else str(self.strategy)
        )
        formatter = _TRUNCATION_FORMATTERS.get(strat, _truncate_head_tail)
        return formatter(text, self.max_chars)


@runtime_checkable
class OverflowStore(Protocol):
    """Protocol for persisting spilled tool outputs."""

    def write(self, key: str, data: bytes) -> str: ...
    def read(self, handle: str) -> bytes: ...


_OVERFLOW_MEMORY_FALLBACK: dict[str, bytes] = {}


class LocalFileStore(BaseModel):
    """Filesystem-backed store for spilled tool return payloads."""

    model_config = ConfigDict(extra="ignore")

    base_dir: Path = Field(
        default_factory=lambda: Path(
            os.environ.get(
                "DEVOPS_CLI_OVERFLOW_DIR",
                str(Path(tempfile.gettempdir()) / "devops_cli_overflow"),
            )
        )
    )
    cleanup_after: timedelta | None = None

    def __init__(
        self,
        base_dir: Path | str | None = None,
        cleanup_after: timedelta | None = None,
    ) -> None:
        p = (
            Path(base_dir)
            if base_dir is not None
            else Path(
                os.environ.get(
                    "DEVOPS_CLI_OVERFLOW_DIR",
                    str(Path(tempfile.gettempdir()) / "devops_cli_overflow"),
                )
            )
        )
        super().__init__(base_dir=p, cleanup_after=cleanup_after)
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.base_dir, 0o700)
        except Exception:
            pass

    def write(self, key: str, data: bytes) -> str:
        """Persist data under key and return handle."""
        sanitized_key = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", key)
        handle = f"spill_{sanitized_key}_{uuid.uuid4().hex[:8]}"
        try:
            target = self.base_dir / handle
            target.write_bytes(data)
            return handle
        except Exception:
            _OVERFLOW_MEMORY_FALLBACK[handle] = data
            return handle

    def read(self, handle: str) -> bytes:
        """Read data for handle."""
        if handle in _OVERFLOW_MEMORY_FALLBACK:
            return _OVERFLOW_MEMORY_FALLBACK[handle]
        sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", handle)
        target = self.base_dir / sanitized
        if target.exists():
            return target.read_bytes()
        raise FileNotFoundError(f"Spill handle not found: {handle}")

    def read_slice(
        self,
        handle: str,
        offset: int = 0,
        limit: int = 100,
        from_end: bool = False,
        pattern: str | None = None,
    ) -> str:
        """Read a line-bounded slice from the spilled payload."""
        data = self.read(handle)
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()

        if pattern:
            lines = [line for line in lines if pattern in line]

        if from_end:
            selected = lines[max(0, len(lines) - limit) :]
        else:
            selected = lines[max(0, offset) : max(0, offset) + limit]

        return "\n".join(selected)


class Spill(BaseModel):
    """Losslessly persists tool return to overflow store and returns handle + preview."""

    model_config = ConfigDict(extra="ignore")

    max_chars: int = 10000
    store: Any | None = None
    then: Any | None = None

    def reduce(self, text: str, tool_name: str = "tool", tool_call_id: str = "") -> str:
        """Spill payload to store and return handle preview."""
        resolved_store = self.store or LocalFileStore()
        key = f"{tool_name}_{tool_call_id}" if tool_call_id else tool_name
        try:
            handle = resolved_store.write(key, text.encode("utf-8"))
            preview = text[:500].replace("\n", " ")
            lines_count = len(text.splitlines())
            return (
                f"[Tool output spilled: {len(text)} chars ({lines_count} lines)]\n"
                f"Handle: {handle}\n"
                f"Preview: {preview}...\n"
                f"Use `read_tool_result(handle='{handle}', offset=0, limit=100)` to page through output."
            )
        except Exception:
            if self.then and hasattr(self.then, "reduce"):
                return str(self.then.reduce(text))
            return text[: self.max_chars]


class Summarize(BaseModel):
    """Size-gated LLM summary of tool output."""

    model_config = ConfigDict(extra="ignore")

    summary_model: Any | None = None
    then: Any | None = None

    def reduce(self, text: str, tool_name: str = "tool") -> str:
        """Summarize text output."""
        lines = text.splitlines()
        preview_lines = lines[:10]
        return (
            f"[Summary of {tool_name} output ({len(text)} chars, {len(lines)} lines)]:\n"
            + "\n".join(preview_lines)
            + ("\n..." if len(lines) > 10 else "")
        )


class Band(BaseModel):
    """A size threshold and associated reduction action."""

    model_config = ConfigDict(extra="ignore")

    over: int
    action: Any


def indented_json(val: Any) -> str:
    """Format structured value as indented JSON (one field per line)."""

    return json.dumps(val, indent=2, ensure_ascii=False)


def json_lines(val: Any) -> str:
    """Format structured list or record as JSON Lines (one record per line)."""

    if isinstance(val, (list, tuple)):
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in val)
    return json.dumps(val, ensure_ascii=False)


class ToolOutputLimits(BaseCapability):
    """Capability managing tool output limits with Truncate, Spill, and Summarize bands."""

    id: str = "tool_output_limits"
    max_chars: int = 15000
    bands: list[Band] = Field(
        default_factory=lambda: [Band(over=10000, action=Spill(then=Truncate(max_chars=5000)))]
    )
    per_tool: dict[str, list[Band]] = Field(default_factory=dict)
    tool_filter: list[str] | set[str] | None = None
    over_tokens: bool = False
    tokenizer: Any | None = None
    store: Any | None = None
    strip_ansi: bool = False
    summary_prompt: str = "Summarize {tool_name} output: {output}"
    serializer: Any | None = None

    def __init__(
        self,
        bands: Sequence[Band] | None = None,
        *,
        per_tool: Mapping[str, Sequence[Band]] | None = None,
        tool_filter: Sequence[str] | set[str] | None = None,
        max_chars: int = 15000,
        over_tokens: bool = False,
        tokenizer: Any | None = None,
        store: Any | None = None,
        strip_ansi: bool = False,
        summary_prompt: str = "Summarize {tool_name} output: {output}",
        serializer: Any | None = None,
        id: str = "tool_output_limits",
    ) -> None:
        resolved_bands = (
            list(bands)
            if bands is not None
            else [Band(over=10000, action=Spill(store=store, then=Truncate(max_chars=5000)))]
        )
        resolved_per_tool = (
            {k: list(v) for k, v in per_tool.items()} if per_tool is not None else {}
        )
        super().__init__(
            id=str(id or "tool_output_limits"),
            max_chars=max_chars,
            bands=resolved_bands,
            per_tool=resolved_per_tool,
            tool_filter=list(tool_filter) if tool_filter is not None else None,
            over_tokens=over_tokens,
            tokenizer=tokenizer,
            store=store,
            strip_ansi=strip_ansi,
            summary_prompt=summary_prompt,
            serializer=serializer,
        )

    def reduce_output(
        self, tool_name: str, output: Any, tool_call_id: str = ""
    ) -> tuple[Any, bool]:
        """Measure tool return size and apply winning reduction band."""
        if tool_name == "read_tool_result":
            return output, False

        if self.tool_filter is not None and tool_name not in self.tool_filter:
            return output, False

        # Serialize if structured
        text = output
        if not isinstance(output, (str, bytes)):
            if self.serializer and callable(self.serializer):
                try:
                    text = self.serializer(output)
                except Exception:
                    text = str(output)
            else:
                import json

                try:
                    text = json.dumps(output, ensure_ascii=False)
                except Exception:
                    text = str(output)

        if isinstance(text, bytes):
            return text, False

        if self.strip_ansi and isinstance(text, str):
            text = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)

        measured_size = (
            self.tokenizer(text)
            if (self.over_tokens and self.tokenizer and callable(self.tokenizer))
            else (len(text) // 4 if self.over_tokens else len(text))
        )

        active_bands = self.per_tool.get(tool_name, self.bands)
        sorted_bands = sorted(active_bands, key=lambda b: b.over, reverse=True)

        for band in sorted_bands:
            if measured_size >= band.over:
                return self._reduce_band_action(band.action, text, tool_name, tool_call_id)

        if len(text) > self.max_chars:
            return Truncate(max_chars=self.max_chars).reduce(text), True

        return text, False

    def _reduce_band_action(
        self, action: Any, text: str, tool_name: str, tool_call_id: str | None
    ) -> tuple[Any, bool]:
        """Apply a reduction action (Truncate, Spill, Summarize, Passthrough, or callable)."""
        if isinstance(action, Passthrough):
            return text, False
        if isinstance(action, Truncate):
            return action.reduce(text), True
        if isinstance(action, Spill):
            return action.reduce(text, tool_name=tool_name, tool_call_id=tool_call_id or ""), True
        if isinstance(action, Summarize):
            return action.reduce(text, tool_name=tool_name), True
        if callable(action):
            return action(text), True
        return text, False

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        """Expose the read_tool_result tool for paging back into spilled outputs."""
        store = self.store or LocalFileStore()

        def read_tool_result(
            handle: str,
            offset: int = 0,
            limit: int = 100,
            from_end: bool = False,
            pattern: str | None = None,
        ) -> str:
            """Page through a spilled tool result by handle, line offset, and limit."""
            try:
                clamped_limit = min(max(1, limit), 500)
                clamped_offset = max(0, offset)
                return store.read_slice(
                    handle=handle,
                    offset=clamped_offset,
                    limit=clamped_limit,
                    from_end=from_end,
                    pattern=pattern,
                )
            except Exception as e:
                return f"Error reading spill handle '{handle}': {e}"

        return [
            Tool.from_function(
                read_tool_result,
                name="read_tool_result",
                description="Read a slice of a spilled tool return payload by handle, offset, and line limit.",
            )
        ]


class ContextUsage(BaseModel):
    """Token and message count metrics for conversation context."""

    model_config = ConfigDict(extra="ignore")

    total_tokens: int = 0
    context_limit: int = 128000
    context_fraction: float = 0.0
    message_count: int = 0


def pin(item: Any) -> Any:
    """Pin a message or content part so that compaction never discards or modifies it."""
    if hasattr(item, "_pinned"):
        item._pinned = True
    elif isinstance(item, dict):
        item.setdefault("metadata", {})["pinned"] = True
    else:
        try:
            setattr(item, "_pinned", True)
        except Exception:
            pass
    return item


def is_pinned(item: Any) -> bool:
    """Check whether a message or content part is pinned."""
    if getattr(item, "_pinned", False):
        return True
    if isinstance(item, dict):
        return bool(item.get("metadata", {}).get("pinned"))
    if hasattr(item, "metadata") and isinstance(item.metadata, dict):
        return bool(item.metadata.get("pinned"))
    return False


def reinject_pinned(messages: list[Any], pinned_items: Sequence[Any]) -> list[Any]:
    """Ensure all pinned messages are present in the compacted message history."""
    existing_ids = {getattr(m, "id", getattr(m, "tool_call_id", str(m))) for m in messages}
    result = list(messages)
    for p in pinned_items:
        p_id = getattr(p, "id", getattr(p, "tool_call_id", str(p)))
        if p_id not in existing_ids:
            result.insert(1 if len(result) > 1 else 0, p)
            existing_ids.add(p_id)
    return result


class ClampOversizedMessages(BaseCapability):
    """Capability that head/tail-truncates single oversized message parts."""

    id: str = "clamp_oversized_messages"
    max_chars: int = 20000

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Truncate individual messages whose length exceeds max_chars."""
        compacted: list[Any] = []
        for msg in messages:
            if is_pinned(msg):
                compacted.append(msg)
                continue

            content = getattr(msg, "content", msg if isinstance(msg, str) else "")
            if isinstance(content, str) and len(content) > self.max_chars:
                head = content[: self.max_chars // 2]
                tail = content[-(self.max_chars // 2) :]
                omitted = len(content) - self.max_chars
                new_text = (
                    f"{head}\n\n[... Truncated content: {omitted} characters omitted ...]\n\n{tail}"
                )
                if hasattr(msg, "model_copy"):
                    compacted.append(msg.model_copy(update={"content": new_text}))
                elif isinstance(msg, dict):
                    c = dict(msg)
                    c["content"] = new_text
                    compacted.append(c)
                else:
                    compacted.append(new_text)
            else:
                compacted.append(msg)
        return compacted


class ClearToolResults(BaseCapability):
    """Capability managing context compaction by clearing older tool result messages in place."""

    id: str = "clear_tool_results"
    max_fraction: float = 0.7
    keep_pairs: int = 2

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Clear older tool outputs while keeping the most recent keep_pairs intact."""
        tool_indices: list[int] = []
        for i, msg in enumerate(messages):
            role = getattr(msg, "role", msg.get("role") if isinstance(msg, dict) else "")
            content = getattr(msg, "content", msg.get("content") if isinstance(msg, dict) else "")
            name = getattr(msg, "name", msg.get("name") if isinstance(msg, dict) else "")
            if (
                role in {"tool", "function"}
                or getattr(msg, "tool_call_id", None)
                or (isinstance(msg, dict) and "tool_call_id" in msg)
                or "[tool result:" in str(content).lower()
                or bool(name)
            ):
                if not is_pinned(msg):
                    tool_indices.append(i)

        if len(tool_indices) <= self.keep_pairs:
            return list(messages)

        indices_to_clear = set(tool_indices[: -self.keep_pairs])
        compacted: list[Any] = []
        for i, msg in enumerate(messages):
            if i in indices_to_clear:
                name = getattr(
                    msg, "name", msg.get("name", "tool") if isinstance(msg, dict) else "tool"
                )
                cleared_text = f"[Cleared tool result: {name}]"
                if hasattr(msg, "model_copy"):
                    compacted.append(msg.model_copy(update={"content": cleared_text}))
                elif isinstance(msg, dict):
                    c = dict(msg)
                    c["content"] = cleared_text
                    compacted.append(c)
                else:
                    compacted.append(cleared_text)
            else:
                compacted.append(msg)
        return compacted


class DeduplicateFileReads(BaseCapability):
    """Capability that blanks superseded file read results when a newer read of the same file exists."""

    id: str = "deduplicate_file_reads"
    file_read_tools: set[str] = Field(
        default_factory=lambda: {"read_file", "view_file", "cat", "get_file", "read_path"}
    )

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Drop duplicate file contents across consecutive reads of the same file path."""
        file_latest_idx: dict[str, int] = {}
        for i, msg in enumerate(messages):
            t_name = getattr(msg, "name", msg.get("name") if isinstance(msg, dict) else "")
            content = getattr(msg, "content", msg.get("content") if isinstance(msg, dict) else "")
            if (
                t_name in self.file_read_tools
                or "file" in str(t_name).lower()
                or "read_file" in str(content).lower()
            ):
                file_latest_idx[str(t_name or "read_file")] = i

        compacted: list[Any] = []
        for i, msg in enumerate(messages):
            t_name = getattr(msg, "name", msg.get("name") if isinstance(msg, dict) else "")
            key = str(t_name or "read_file")
            if key in file_latest_idx and file_latest_idx[key] > i and not is_pinned(msg):
                cleared_text = f"[Superseded file read: {key}]"
                if hasattr(msg, "model_copy"):
                    compacted.append(msg.model_copy(update={"content": cleared_text}))
                elif isinstance(msg, dict):
                    c = dict(msg)
                    c["content"] = cleared_text
                    compacted.append(c)
                else:
                    compacted.append(cleared_text)
            else:
                compacted.append(msg)
        return compacted


@runtime_checkable
class TranscriptHandleProvider(Protocol):
    """Protocol for capabilities providing persisted transcript handles to compaction receipts."""

    def compaction_transcript_handle(self) -> str | None:
        """Return the run identifier or handle for the persisted transcript."""
        ...


class CompactionReceipt(BaseModel):
    """Deterministic receipt documenting context compaction for model legibility."""

    model_config = ConfigDict(extra="ignore")

    strategy: str
    messages_dropped: int = 0
    tokens_dropped: int = 0
    handle: str | None = None

    def to_receipt_text(self) -> str:
        """Format the deterministic receipt text block."""
        handle_part = f", handle={self.handle}" if self.handle else ""
        return (
            f"[Compaction Receipt: strategy={self.strategy}, "
            f"messages_dropped={self.messages_dropped}, "
            f"tokens_dropped={self.tokens_dropped}{handle_part}]"
        )


class SlidingWindowCompaction(BaseCapability):
    """Capability that drops older whole messages down to a recent tail."""

    id: str = "sliding_window_compaction"
    max_messages: int = 20
    keep_user_messages: bool = True
    receipts: bool = False
    transcript_handle_provider: Any | None = None

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Retain the first message (system/instruction) and the last max_messages."""
        if len(messages) <= self.max_messages:
            return list(messages)

        pinned = [m for m in messages if is_pinned(m)]
        first_msg = messages[0]
        tail = messages[-self.max_messages :]
        dropped_count = len(messages) - (len(tail) + 1)

        combined: list[Any] = [first_msg]
        if self.receipts and dropped_count > 0:
            handle = None
            if self.transcript_handle_provider and hasattr(
                self.transcript_handle_provider, "compaction_transcript_handle"
            ):
                handle = self.transcript_handle_provider.compaction_transcript_handle()
            receipt = CompactionReceipt(
                strategy=self.__class__.__name__,
                messages_dropped=dropped_count,
                tokens_dropped=dropped_count * 50,
                handle=handle,
            )
            from devops_cli.models.ai import ChatMessage

            combined.append(ChatMessage(role="system", content=receipt.to_receipt_text()))

        combined.extend([m for m in tail if m != first_msg])
        return reinject_pinned(combined, pinned)


class SummarizingCompaction(BaseCapability):
    """Capability that summarizes older messages into a structured summary message."""

    id: str = "summarizing_compaction"
    summary_model: Any | None = None
    instructions: str = DEFAULT_SUMMARIZING_INSTRUCTIONS
    keep_tail: int = 4
    max_fraction: float = 0.8
    incremental: bool = True
    bridge_prefix: bool = False
    keep_user_messages: bool = True
    keep_user_messages_max_chars: int = 20000
    receipts: bool = False
    transcript_handle_provider: Any | None = None

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Compress the middle turns into a concise summary block."""
        if len(messages) <= self.keep_tail + 2:
            return list(messages)

        pinned = [m for m in messages if is_pinned(m)]
        first_msg = messages[0]
        tail = messages[-self.keep_tail :]
        middle = messages[1 : -self.keep_tail]

        # Extract prior summary if incremental
        prior_summary = ""
        filtered_middle: list[Any] = []
        for m in middle:
            content = str(getattr(m, "content", ""))
            if self.incremental and "[Conversation Summary:" in content:
                prior_summary = content
            else:
                filtered_middle.append(m)

        summary_lines: list[str] = []
        if self.bridge_prefix:
            summary_lines.append("[Cross-model bridge: context compressed across models]")

        if prior_summary:
            summary_lines.append(f"<previous-summary>\n{prior_summary}\n</previous-summary>")

        # Retain recent user messages up to budget if requested
        if self.keep_user_messages:
            user_turns = [
                m
                for m in filtered_middle
                if getattr(m, "role", "") == "user"
                or (isinstance(m, dict) and m.get("role") == "user")
            ]
            for ut in user_turns[-2:]:
                u_text = str(getattr(ut, "content", ""))[: self.keep_user_messages_max_chars]
                summary_lines.append(f"User Goal: {u_text}")

        for m in filtered_middle:
            c = str(getattr(m, "content", ""))
            if c:
                summary_lines.append(f"- {getattr(m, 'role', 'turn')}: {c[:100]}...")

        summary_text = (
            f"[Conversation Summary: {len(middle)} earlier turns compressed]\n"
            + "\n".join(summary_lines[:10])
        )

        combined: list[Any] = [first_msg]

        if self.receipts:
            handle = None
            if self.transcript_handle_provider and hasattr(
                self.transcript_handle_provider, "compaction_transcript_handle"
            ):
                handle = self.transcript_handle_provider.compaction_transcript_handle()
            receipt = CompactionReceipt(
                strategy=self.__class__.__name__,
                messages_dropped=len(middle),
                tokens_dropped=len(middle) * 60,
                handle=handle,
            )
            combined.append(ChatMessage(role="system", content=receipt.to_receipt_text()))

        combined.append(ChatMessage(role="system", content=summary_text))
        combined.extend(tail)
        return reinject_pinned(combined, pinned)


def _apply_compactor(compactor: Any, messages: list[Any]) -> list[Any]:
    """Execute a compactor object or callable on a message sequence."""
    if hasattr(compactor, "compact_messages") and callable(compactor.compact_messages):
        res = compactor.compact_messages(messages)
        return list(res) if isinstance(res, (list, tuple)) else messages
    if callable(compactor):
        res = compactor(messages)
        return list(res) if isinstance(res, (list, tuple)) else messages
    return messages


class FallbackCompaction(BaseCapability):
    """Capability that chains fallback compaction strategies."""

    id: str = "fallback_compaction"
    strategies: list[Any] = Field(default_factory=list)

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Try each configured strategy in order."""
        current = list(messages)
        for strat in self.strategies:
            try:
                return _apply_compactor(strat, current)
            except Exception:
                continue
        return current


class TieredCompaction(BaseCapability):
    """Cascading compaction strategy running cheap zero-LLM passes before escalating."""

    id: str = "tiered_compaction"
    tiers: list[Any] = Field(default_factory=list)
    max_fraction: float = 0.8
    target_tokens: int = 100000

    def __init__(
        self,
        tiers: Sequence[Any] | None = None,
        *,
        max_fraction: float = 0.8,
        target_tokens: int = 100000,
        id: str = "tiered_compaction",
    ) -> None:
        resolved_tiers = (
            list(tiers)
            if tiers is not None
            else [
                DeduplicateFileReads(),
                ClearToolResults(),
                ClampOversizedMessages(),
                SlidingWindowCompaction(),
            ]
        )
        super().__init__(
            id=str(id or "tiered_compaction"),
            tiers=resolved_tiers,
            max_fraction=max_fraction,
            target_tokens=target_tokens,
        )

    def compact_messages(self, messages: list[Any]) -> list[Any]:
        """Apply cascading compaction tiers sequentially."""
        current = list(messages)
        for tier in self.tiers:
            current = _apply_compactor(tier, current)
        return current


class WarnNearLimits(BaseCapability):
    """Capability notifying the model when context consumption approaches token limits."""

    id: str = "warn_near_limits"
    max_context_fraction: float = 0.9

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        return [
            f"WarnNearLimits enabled: context warning will be issued if usage exceeds "
            f"{int(self.max_context_fraction * 100)}% of model context window."
        ]


class CacheBustWarning(UserWarning):
    """Warned when a previously-established prompt cache hit collapses on a later request."""


class CacheMark(BaseModel):
    """Tracking metrics for prompt cache stability per model and provider."""

    model_config = ConfigDict(extra="ignore")

    established_prefix: int = 0
    last_read_tokens: int = 0
    last_request_time: float = 0.0
    latched_warning: bool = False


class WarnOnCacheBusts(BaseCapability):
    """Capability that warns when prompt cache hits collapse mid-run."""

    id: str = "warn_on_cache_busts"
    collapse_ratio: float = Field(default=0.5, gt=0.0)
    min_prefix_tokens: int = Field(default=1024, ge=0)
    cache_ttl_seconds: float = Field(default=300.0, gt=0.0)
    marks: dict[tuple[str, str], CacheMark] = Field(default_factory=dict)

    def __init__(
        self,
        *,
        collapse_ratio: float = 0.5,
        min_prefix_tokens: int = 1024,
        cache_ttl_seconds: float = 300.0,
        id: str = "warn_on_cache_busts",
    ) -> None:
        if collapse_ratio <= 0.0:
            raise ValueError(f"collapse_ratio must be greater than 0.0, got {collapse_ratio}")
        super().__init__(
            id=str(id or "warn_on_cache_busts"),
            collapse_ratio=collapse_ratio,
            min_prefix_tokens=min_prefix_tokens,
            cache_ttl_seconds=cache_ttl_seconds,
            marks={},
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> WarnOnCacheBusts:  # type: ignore[override]
        """Return a fresh capability instance with clean per-run state."""
        return WarnOnCacheBusts(
            collapse_ratio=self.collapse_ratio,
            min_prefix_tokens=self.min_prefix_tokens,
            cache_ttl_seconds=self.cache_ttl_seconds,
            id=self.id,
        )

    def _emit_cache_bust_warning(
        self,
        provider_name: str,
        model_name: str,
        cache_read_tokens: int,
        mark: CacheMark,
        now: float,
    ) -> str:
        """Emit a cache collapse warning and return the message."""
        gap = now - mark.last_request_time
        expiry_note = ""
        if mark.last_request_time > 0 and gap > self.cache_ttl_seconds:
            expiry_note = (
                f" (gap of {gap:.1f}s exceeds assumed cache TTL of {self.cache_ttl_seconds}s)"
            )

        warning_msg = (
            f"Prompt cache collapsed for {provider_name}:{model_name}: read {cache_read_tokens} cached tokens, "
            f"down from established prefix of {mark.established_prefix} tokens (< {self.collapse_ratio:.0%}){expiry_note}."
        )
        warnings.warn(warning_msg, category=CacheBustWarning, stacklevel=2)
        mark.latched_warning = True
        return warning_msg

    def _check_cache_collapse(
        self,
        provider_name: str,
        model_name: str,
        cache_read_tokens: int,
        mark: CacheMark,
        now: float,
    ) -> str | None:
        """Check if cache read tokens fell below collapse threshold and emit warning."""
        if mark.established_prefix < self.min_prefix_tokens:
            return None
        threshold = mark.established_prefix * self.collapse_ratio
        if cache_read_tokens >= threshold:
            mark.latched_warning = False
            return None
        if not mark.latched_warning:
            return self._emit_cache_bust_warning(
                provider_name, model_name, cache_read_tokens, mark, now
            )
        return None

    def record_request(
        self,
        provider_name: str,
        model_name: str,
        cache_read_tokens: int,
        cache_write_tokens: int,
        *,
        request_context: Any = None,
        now: float | None = None,
        current_time: float | None = None,
    ) -> str | None:
        """Record token usage for a model request and detect cache prefix collapse."""
        effective_now = (
            time.time()
            if now is None and current_time is None
            else (now if now is not None else current_time)
        )
        assert effective_now is not None
        key = (provider_name, model_name)
        if key not in self.marks:
            self.marks[key] = CacheMark(last_request_time=effective_now)
        mark = self.marks[key]
        total_prefix = cache_read_tokens + cache_write_tokens

        warning_msg = self._check_cache_collapse(
            provider_name, model_name, cache_read_tokens, mark, effective_now
        )

        mark.established_prefix = max(mark.established_prefix, total_prefix)
        mark.last_read_tokens = cache_read_tokens
        mark.last_request_time = effective_now
        return warning_msg

    def record_usage(
        self,
        provider_name: str,
        model_name: str,
        cache_read_tokens: int,
        cache_write_tokens: int,
        *,
        request_context: Any = None,
        now: float | None = None,
        current_time: float | None = None,
    ) -> str | None:
        """Alias for record_request."""
        return self.record_request(
            provider_name=provider_name,
            model_name=model_name,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            request_context=request_context,
            now=now,
            current_time=current_time,
        )

    def after_model_request(  # type: ignore[override]
        self,
        ctx: RunContext[Any] | None = None,
        *,
        request_context: Any = None,
        response: Any = None,
    ) -> Any:
        """Inspect model response usage for cache read/write tokens and track stability."""
        if response is None:
            return response

        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")

        cache_read = getattr(usage, "cache_read_tokens", 0) or 0
        cache_write = getattr(usage, "cache_write_tokens", 0) or 0
        provider = (
            getattr(request_context, "provider_name", "provider") if request_context else "provider"
        )
        model = getattr(request_context, "model_name", "model") if request_context else "model"

        if isinstance(usage, dict):
            cache_read = usage.get("cache_read_tokens", 0) or 0
            cache_write = usage.get("cache_write_tokens", 0) or 0

        self.record_request(
            provider_name=provider,
            model_name=model,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )
        return response


class ReportContextUsage(BaseCapability):
    """Capability reporting token counts and context fractions."""

    id: str = "report_context_usage"

    def get_usage(self, messages: list[Any], context_limit: int = 128000) -> ContextUsage:
        """Calculate token and message usage metrics."""
        total_chars = sum(len(str(getattr(m, "content", ""))) for m in messages)
        estimated_tokens = total_chars // 4
        fraction = min(1.0, estimated_tokens / max(1, context_limit))
        return ContextUsage(
            total_tokens=estimated_tokens,
            context_limit=context_limit,
            context_fraction=fraction,
            message_count=len(messages),
        )


def compact_now(
    messages: list[Any],
    strategy: Any | None = None,
) -> list[Any]:
    """Execute immediate compaction on a message history list using the given or default strategy."""
    strat = strategy or TieredCompaction()
    if hasattr(strat, "compact_messages"):
        res = strat.compact_messages(messages)
        return list(res) if isinstance(res, (list, tuple)) else list(messages)
    elif callable(strat):
        res = strat(messages)
        return list(res) if isinstance(res, (list, tuple)) else list(messages)
    return list(messages)
