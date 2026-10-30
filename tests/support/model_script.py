"""A scripted pydantic-ai model for the tests of an agent run (#2664).

`ModelScript` answers the nth model request with the nth scripted reply, and the last reply for
every request after that. A reply is a `ModelResponse`, an exception that the request raises, or
an `InStream` error, which the request raises after its stream has begun. The model streams, as the
harness's `Coder` and the jobs' runs ask for it. The script keeps the messages of each request and
the names of the function tools each request offered.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class InStream:
    """A reply that fails after the stream has begun: the model streams the start of a tool call
    that ends early, as in #2656, then `error` is raised. A request that does not stream raises `error` at once."""

    error: Exception


class ModelScript:
    """The scripted replies of a model, and what the model was asked."""

    def __init__(
        self,
        *replies: ModelResponse | Exception | InStream,
        effects: Mapping[int, Callable[[], None]] | None = None,
    ) -> None:
        """`effects` maps the number of a request to what the agent's shell would have done by
        then, such as a commit. It runs before that request is answered."""
        self.replies = replies
        self.effects = dict(effects or {})
        self.seen: list[list[ModelMessage]] = []
        self.tools_offered: list[list[str]] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.seen.append(list(messages))
        effect = self.effects.get(len(self.seen))
        if effect is not None:
            effect()
        self.tools_offered.append(sorted(tool.name for tool in info.function_tools))
        reply = self.replies[min(len(self.seen), len(self.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, InStream):
            raise reply.error
        return reply

    async def stream(
        self, messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        """The same reply as a stream."""
        try:
            reply = self(messages, info)
        except Exception as error:
            if self._in_stream(len(self.seen)):
                yield {
                    0: DeltaToolCall(name="write_file", json_args='{"path": "a.py", "content": ')
                }
            raise error
        for index, part in enumerate(reply.parts):
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

    def _in_stream(self, number: int) -> bool:
        """Whether the nth request fails after its stream has begun."""
        return isinstance(self.replies[min(number, len(self.replies)) - 1], InStream)

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
