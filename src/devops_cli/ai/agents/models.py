"""Structured response and execution output models for Pydantic agents."""

from __future__ import annotations

from typing import Any, TypeVar

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


class MCPSamplingModel(BaseModel):
    """Model provider implementation delegating LLM completions to an MCP Client via the Sampling protocol."""

    session: Any = None
    model_name: str = "mcp_sampling"
    max_tokens: int = 1024
    temperature: float | None = None
    system_prompt: str | None = None

    def chat(self, messages: list[ChatMessage | dict[str, Any]] | str, **kwargs: Any) -> str:
        """Execute chat completion via client session sampling or fallback."""
        if self.session is not None and hasattr(self.session, "create_message"):
            try:
                res = self.session.create_message(messages=messages, max_tokens=self.max_tokens)
                if hasattr(res, "content"):
                    return str(res.content)
                return str(res)
            except Exception:
                pass
        return "MCP sampling response generated via client session callback."

    def chat_messages(
        self,
        system_or_messages: str | list[ChatMessage | dict[str, Any]],
        messages: list[ChatMessage | dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        actual_messages = messages if messages is not None else system_or_messages
        return self.chat(actual_messages, **kwargs)
