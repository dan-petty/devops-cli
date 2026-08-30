"""Structured response and execution output models for Pydantic agents."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, Field

from devops_cli.ai.agents.context import AgentUsage
from devops_cli.ai.agents.tools import ToolCall
from devops_cli.models.ai import ChatMessage

T = TypeVar("T")


class AgentResponse[T](BaseModel):
    """Structured response returned by a PydanticAgent run."""

    content: str
    data: T | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    thoughts: list[str] = Field(default_factory=list)
    turns: int = 1
    backend_info: str | None = None
    usage: AgentUsage = Field(default_factory=AgentUsage)
    messages: list[ChatMessage] = Field(default_factory=list)
    new_messages_list: list[ChatMessage] = Field(default_factory=list)

    def all_messages(self) -> list[ChatMessage]:
        """Return the complete message history including prior turns and tool exchanges."""
        return list(self.messages)

    def new_messages(self) -> list[ChatMessage]:
        """Return messages generated in this specific agent run."""
        return list(self.new_messages_list)
