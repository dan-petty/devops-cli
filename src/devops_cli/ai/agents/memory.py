"""AI Agent memory system with automatic size-triggered summarization.

Example:
    >>> from devops_cli.ai.agents.memory import AgentMemory
    >>> from devops_cli.ai.client import LLMClient
    >>>
    >>> memory = AgentMemory(session_id="chat-1", max_entries=6, max_chars=2000)
    >>> memory.add_interaction("user", "Configure deployment for AWS EKS")
    >>> memory.add_interaction("assistant", "Configured deployment manifests.")
    >>> memory.auto_summarize_if_needed(llm_client=client)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ENTRIES = 8
_DEFAULT_MAX_CHARS = 4000
_DEFAULT_KEEP_RECENT = 3

_SUMMARY_SYSTEM_PROMPT = load_task_prompt("summarize_memory_system.md")
_SUMMARY_PROMPT = load_task_prompt("summarize_memory.md")


class MemoryEntry(BaseModel):
    """An individual record in an agent interaction memory."""

    role: Literal["user", "assistant", "system", "tool"] = "user"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("role", mode="before")
    @classmethod
    def _normalize_role(cls, v: object) -> str:
        s = str(v).lower().strip()
        if s in {"user", "assistant", "system", "tool"}:
            return s
        return "assistant"

    @property
    def char_count(self) -> int:
        return len(self.content)


class AgentMemory(BaseModel):
    """Multi-turn interaction memory buffer with automatic size-triggered summarization."""

    session_id: str = "default-session"
    max_entries: int = _DEFAULT_MAX_ENTRIES
    max_chars: int = _DEFAULT_MAX_CHARS
    keep_recent: int = _DEFAULT_KEEP_RECENT
    summary: str = ""
    entries: list[MemoryEntry] = Field(default_factory=list)

    def add_interaction(
        self,
        role: Literal["user", "assistant", "system", "tool"],
        content: str,
        **metadata: Any,
    ) -> MemoryEntry:
        """Record an interaction turn into memory."""
        entry = MemoryEntry(
            role=role,
            content=content,
            metadata=metadata,
        )
        self.entries.append(entry)
        return entry

    @property
    def total_chars(self) -> int:
        """Total character length of all raw entries in memory."""
        return sum(e.char_count for e in self.entries)

    def should_summarize(self) -> bool:
        """Check if memory size exceeds entry count or character thresholds."""
        return len(self.entries) > self.max_entries or self.total_chars > self.max_chars

    def auto_summarize_if_needed(self, llm_client: Any | None = None) -> bool:
        """Condense older memory entries into a summary if size thresholds are exceeded."""
        if not self.should_summarize() or len(self.entries) <= self.keep_recent:
            return False

        # Split entries into items to summarize and recent items to keep intact
        cutoff = len(self.entries) - self.keep_recent
        to_summarize = self.entries[:cutoff]
        to_keep = self.entries[cutoff:]

        from devops_cli.ai.review.sanitization import (
            _mask_secrets_in_content,
            _sanitize_prompt_boundary_tags,
        )

        rendered_interactions = "\n".join(
            f"[{e.role.upper()}]: "
            f"{_sanitize_prompt_boundary_tags(_mask_secrets_in_content(e.content))}"
            for e in to_summarize
        )

        new_summary = ""
        if llm_client is not None and hasattr(llm_client, "chat"):
            try:
                prompt = _SUMMARY_PROMPT.format(
                    existing_summary=self.summary or "(None)",
                    interactions=rendered_interactions,
                )
                res = llm_client.chat(
                    system=_SUMMARY_SYSTEM_PROMPT,
                    user=prompt,
                    enable_thinking=False,
                )
                res_str = str(res).strip()
                if res_str:
                    new_summary = res_str
            except Exception as exc:
                logger.debug(f"LLM memory summarization failed, falling back to extractive: {exc}")

        if not new_summary:
            # Fallback deterministic extractive summarization
            bullets: list[str] = []
            if self.summary:
                bullets.append(self.summary)
            for e in to_summarize:
                snippet = e.content.strip().replace("\n", " ")
                if len(snippet) > 120:
                    snippet = snippet[:117] + "..."
                bullets.append(f"[{e.role.upper()}]: {snippet}")
            new_summary = " | ".join(bullets)
            if len(new_summary) > self.max_chars // 2:
                new_summary = new_summary[: (self.max_chars // 2) - 3] + "..."

        self.summary = new_summary
        self.entries = to_keep
        return True

    def render_memory_context(self) -> str:
        """Render consolidated summary and recent turns as markdown context for agent prompts."""
        parts: list[str] = []
        if self.summary:
            parts.append(f"## Prior Interaction Context & Summary\n{self.summary}")
        if self.entries:
            recent_str = "\n".join(f"- **{e.role.upper()}**: {e.content}" for e in self.entries)
            parts.append(f"## Recent Interactions\n{recent_str}")
        return "\n\n".join(parts)

    def to_chat_messages(self, system_instruction: str = "") -> list[ChatMessage]:
        """Convert memory state (summary + recent entries) into ChatMessage list for LLMs."""
        messages: list[ChatMessage] = []
        if system_instruction or self.summary:
            sys_content = system_instruction
            if self.summary:
                summary_block = f"## Context from Earlier Conversation:\n{self.summary}"
                sys_content = f"{sys_content}\n\n{summary_block}".strip()
            if sys_content:
                messages.append(ChatMessage(role="system", content=sys_content))

        for entry in self.entries:
            role_norm = entry.role.lower()
            if role_norm not in ("system", "user", "assistant"):
                role_norm = "user"
            messages.append(ChatMessage(role=role_norm, content=entry.content))  # type: ignore[arg-type]

        return messages

    def clear(self) -> None:
        """Reset memory buffer and summary."""
        self.summary = ""
        self.entries.clear()
