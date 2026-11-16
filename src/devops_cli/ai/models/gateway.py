"""The pydantic-ai model of a call to a chat group of the LLM gateway: one retry layer (#5965).

The gateway owns the retries and the fallbacks of a call (`router_settings` of
`k8s/llm/gateway/config.yaml`). The client sends a call again only in two cases that no layer of
the gateway retries:

- The call did not reach the gateway: its connect failed, or the pool had no free connection.
- A streamed reply failed before its first event. LiteLLM writes such a failure into the open
  stream, after its status 200, and raises a failure with a 4xx status other than 429 with no
  fallback (`_handle_stream_fallback_error`). An OpenRouter timeout comes in the stream as code 408.

A status that the gateway answers is not sent again, because the gateway retried the call and
tried its fallbacks already. A failure after the first event fails the call once.

pydantic-ai's `FallbackModel` sends the call: it holds the chat model `ai.max_retries` + 1 times,
and it waits for the first event of a stream before it gives the stream to the caller. The
`WrapperModel` around it keeps the name, the profile and the deadline of the chat model, so the
agent graph starts one `request_timeout` deadline over every send and the read of the stream. The
OpenAI SDK under the chat model makes no retry of its own (`ModelSettings.max_retries` 0).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import Any, Final

from pydantic_ai import RunContext
from pydantic_ai.exceptions import (
    FallbackExceptionGroup,
    ModelAPIError,
    ModelConnectionError,
    ModelTimeoutError,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings, merge_model_settings

# The transport phases of a failure that sent no request: the connect, and the wait for a free
# connection of the pool.
_NOT_SENT: Final = frozenset({"connect", "pool"})


def never_sent(error: Exception) -> bool:
    """Whether `error` ended a call before the call left the client: a failed connect, or no free
    connection in the pool."""
    return isinstance(error, ModelConnectionError) and error.phase in _NOT_SENT


def failed_before_first_event(error: Exception) -> bool:
    """Whether `error`, raised before the first event of a stream, lets the call go again: the
    call never left the client, an error frame came inside the stream, the stream broke, or it
    ended with no content. A status of the gateway, a timeout of the client and the deadline of
    the call do not."""
    if never_sent(error):
        return True
    if isinstance(error, ModelConnectionError):
        return not isinstance(error, ModelTimeoutError)
    if isinstance(error, ModelAPIError):
        return error.in_stream
    return isinstance(error, UnexpectedModelBehavior)


@contextmanager
def _last_error() -> Iterator[None]:
    """Raise the error of the last send in place of the group of errors of a `FallbackModel`, so
    the caller gets the class of the error and its cause, as for one send."""
    try:
        yield
    except FallbackExceptionGroup as group:
        last = group.exceptions[-1]
        raise last from last.__cause__


class GatewayCallModel(WrapperModel):
    """The chat model of a gateway group, sent at most `max_retries` + 1 times for one call, under
    one deadline of `request_timeout` seconds unless the run sets another."""

    def __init__(self, wrapped: Model, *, max_retries: int, request_timeout: float) -> None:
        super().__init__(wrapped)
        sends = [self.wrapped] * (max_retries + 1)
        self._calls = FallbackModel(*sends, fallback_on=never_sent)
        self._streams = FallbackModel(*sends, fallback_on=failed_before_first_event)
        self._defaults = ModelSettings(request_timeout=request_timeout, max_retries=0)

    @property
    def settings(self) -> ModelSettings | None:
        """The settings of the chat model over the deadline of a call and no SDK retries."""
        return merge_model_settings(self._defaults, self.wrapped.settings)

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        with _last_error():
            return await self._calls.request(messages, model_settings, model_request_parameters)

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        async with AsyncExitStack() as stack:
            with _last_error():
                stream = await stack.enter_async_context(
                    self._streams.request_stream(
                        messages, model_settings, model_request_parameters, run_context
                    )
                )
            yield stream


__all__ = ["GatewayCallModel", "failed_before_first_event", "never_sent"]
