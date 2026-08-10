"""Shared domain models for AI/LLM client messages."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    """A single message in a multi-turn LLM conversation."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to the dict format expected by provider HTTP APIs."""
        return {"role": self.role, "content": self.content}
