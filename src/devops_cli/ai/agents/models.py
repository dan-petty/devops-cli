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

    @property
    def run_usage(self) -> Any:
        """Return native pydantic_ai.result.RunUsage tracking instance."""
        from pydantic_ai.usage import RunUsage

        return RunUsage(
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
            requests=self.turns,
            tool_calls=len(self.tool_calls),
        )

    def to_final_result(self) -> Any:
        """Wrap output into a native pydantic_ai.result.FinalResult marker container."""
        from pydantic_ai.result import FinalResult

        return FinalResult(output=self.output)

    def all_messages(self) -> list[ChatMessage]:
        """Return the complete message history including prior turns and tool exchanges."""
        return list(self.messages)

    def new_messages(self) -> list[ChatMessage]:
        """Return messages generated in this specific agent run."""
        return list(self.new_messages_list)

    @classmethod
    def from_run_result(cls, run_res: Any) -> AgentResponse[Any]:
        """Create AgentResponse from a native pydantic_ai.run.AgentRunResult or StreamedRunResult."""
        raw_output = getattr(run_res, "output", None)
        if raw_output is None and hasattr(run_res, "get_output") and callable(run_res.get_output):
            try:
                raw_output = run_res.get_output()
            except Exception:
                raw_output = None

        if isinstance(raw_output, str):
            content = raw_output
            data = None
        elif raw_output is not None:
            content = str(raw_output)
            data = raw_output
        else:
            content = ""
            data = None

        run_usage = getattr(run_res, "usage", None)
        if callable(run_usage) and not hasattr(run_usage, "input_tokens"):
            try:
                run_usage = run_usage()
            except Exception:
                pass
        in_tok = int(getattr(run_usage, "input_tokens", 0) or 0) if run_usage else 0
        out_tok = int(getattr(run_usage, "output_tokens", 0) or 0) if run_usage else 0
        usage = AgentUsage(
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
        )

        resp = getattr(run_res, "response", None)
        backend_info = getattr(resp, "model_name", None) if resp else None

        return cls(
            content=content,
            data=data,
            usage=usage,
            backend_info=backend_info,
        )

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

    @classmethod
    def from_model_response(cls, resp: Any) -> AgentResponse[Any]:
        """Create AgentResponse from a pydantic_ai.messages.ModelResponse."""
        from pydantic_ai.messages import ModelResponse, ThinkingPart

        from devops_cli.ai.response_repair import extract_model_response_parts

        if not isinstance(resp, ModelResponse):
            return cls(content=str(resp))

        content, thinking, tool_parts = extract_model_response_parts(resp)
        tool_calls = [
            ToolCall(
                tool_name=p.tool_name,
                arguments=p.args if isinstance(p.args, dict) else {},
            )
            for p in tool_parts
        ]
        thoughts = [
            p.content for p in resp.parts if isinstance(p, ThinkingPart) and p.has_content()
        ]
        in_tok = resp.usage.input_tokens if resp.usage else 0
        out_tok = resp.usage.output_tokens if resp.usage else 0
        usage = AgentUsage(
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
        )
        return cls(
            content=content,
            tool_calls=tool_calls,
            thoughts=thoughts,
            usage=usage,
            backend_info=resp.model_name,
        )


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
