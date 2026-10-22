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

    @property
    def output(self) -> T | str:
        """Return structured data output if present, otherwise raw text content."""
        return self.data if self.data is not None else self.content

    @property
    def thinking(self) -> str | None:
        """Accumulated thinking/reasoning text."""
        if not self.thoughts:
            return None
        from devops_cli.ai.review_schema import unique_lines

        return unique_lines("\n\n".join(self.thoughts))

    def all_messages(self) -> list[ChatMessage]:
        """Return the complete message history including prior turns and tool exchanges."""
        return list(self.messages)

    def new_messages(self) -> list[ChatMessage]:
        """Return messages generated in this specific agent run."""
        return list(self.new_messages_list)

    def to_model_response(self, model_name: str | None = None) -> Any:
        """Convert AgentResponse to standard pydantic_ai.messages.ModelResponse."""
        from pydantic_ai.messages import (
            ModelResponse,
            TextPart,
            ThinkingPart,
            ToolCallPart,
        )
        from pydantic_ai.usage import RequestUsage

        parts: list[Any] = []
        if self.thinking:
            parts.append(ThinkingPart(content=self.thinking))
        for tc in self.tool_calls:
            parts.append(ToolCallPart(tool_name=tc.tool_name, args=tc.arguments))
        if self.content:
            parts.append(TextPart(content=self.content))
        usage = RequestUsage(
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
        )
        return ModelResponse(parts=parts, model_name=model_name or self.backend_info, usage=usage)
