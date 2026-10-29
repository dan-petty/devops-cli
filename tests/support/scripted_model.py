"""A scripted pydantic-ai model for tests of agent runs (#2398, #2650).

`FunctionModel` answers each model request from a `Script`, so no test reaches a model.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel


class Script:
    """A `FunctionModel` callback that answers the nth request with the nth response, and the
    last response after that, or `without_tools` once the request offers no function tool. A
    pydantic model answers as the call of the output tool, and a function answers with the model
    response or pydantic model that it returns for the request's messages. It keeps the messages of each request
    and the names of the function tools each one offered."""

    def __init__(
        self,
        *responses: ModelResponse | BaseModel | Exception | Callable[[list[ModelMessage]], Any],
        without_tools: BaseModel | None = None,
    ) -> None:
        self.responses = responses
        self.without_tools = without_tools
        self.seen: list[list[ModelMessage]] = []
        self.tools_offered: list[list[str]] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.seen.append(list(messages))
        self.tools_offered.append([tool.name for tool in info.function_tools])
        answer = self.responses[min(len(self.seen), len(self.responses)) - 1]
        if self.without_tools is not None and not info.function_tools:
            answer = self.without_tools
        if callable(answer) and not isinstance(answer, BaseModel | ModelResponse):
            answer = answer(messages)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, BaseModel) and not isinstance(answer, ModelResponse):
            output_tool = info.output_tools[0].name
            return ModelResponse(
                parts=[ToolCallPart(tool_name=output_tool, args=answer.model_dump())]
            )
        return answer

    async def stream(
        self, messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        """The same answer as a stream, as the investigation asks for it."""
        for index, part in enumerate(self(messages, info).parts):
            if isinstance(part, ToolCallPart):
                yield {
                    index: DeltaToolCall(
                        name=part.tool_name,
                        json_args=part.args_as_json_str(),
                        tool_call_id=part.tool_call_id,
                    )
                }
            elif isinstance(part, TextPart):
                yield part.content

    def model(self) -> FunctionModel:
        """A `FunctionModel` that answers through this script, streamed or not."""
        return FunctionModel(self, stream_function=self.stream)

    def tool_returns(self) -> list[str]:
        """The text of each tool return the model saw, in order."""
        return [
            str(part.content)
            for message in self.seen[-1]
            for part in getattr(message, "parts", ())
            if isinstance(part, ToolReturnPart)
        ]


def call(tool: str, **args: Any) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=args)])
