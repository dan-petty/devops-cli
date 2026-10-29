"""A scripted pydantic-ai model for the tests of an agent run (#2664).

`ModelScript` answers the nth model request with the nth scripted reply, and the last reply for
every request after that. A reply is a `ModelResponse`, or an exception that the request raises.
The model streams, as the harness's `Coder` and the jobs' runs ask for it. The script keeps the
messages of each request and the names of the function tools each request offered.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel


def tool_calls(*calls: tuple[str, dict[str, Any]]) -> ModelResponse:
    """A reply that calls each tool `(name, arguments)` of `calls`."""
    return ModelResponse(parts=[ToolCallPart(tool_name=n, args=a) for n, a in calls])


def tool_call(tool: str, **args: Any) -> ModelResponse:
    """A reply that calls one tool."""
    return tool_calls((tool, args))


def say(text: str) -> ModelResponse:
    """A reply that ends the run with `text`."""
    return ModelResponse(parts=[TextPart(text)])


class ModelScript:
    """The scripted replies of a model, and what the model was asked."""

    def __init__(self, *replies: ModelResponse | Exception) -> None:
        self.replies = replies
        self.seen: list[list[ModelMessage]] = []
        self.tools_offered: list[list[str]] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.seen.append(list(messages))
        self.tools_offered.append(sorted(tool.name for tool in info.function_tools))
        reply = self.replies[min(len(self.seen), len(self.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def stream(
        self, messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        """The same reply as a stream."""
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

    def tool_answers(self) -> list[str]:
        """The text of each tool return or refusal that the model saw, in order."""
        return [
            str(part.content)
            for message in self.seen[-1]
            for part in getattr(message, "parts", ())
            if isinstance(part, ToolReturnPart | RetryPromptPart)
        ]
