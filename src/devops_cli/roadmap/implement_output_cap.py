"""A reply of an implement step that the output cap ends stops the run at once (#2869).

The agent of a step sends `max_tokens`, which the gateway turns into the `num_predict` of Ollama.
A reply that reaches it ends with the finish reason `length`. Pydantic AI does not stop on that:
it runs a tool call that the cap cut, and the shell and file tools of the harness accept the
broken arguments of such a call (`write_file` wrote them as the content of the file). So the run
would go on, and each next request could reach the cap again. `output_cap_hooks` is a pydantic-ai
`Hooks` capability that raises `OutputCapReached` after the first such reply. It reads the finish
reason that the library reports, and no text.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import ModelRequestContext

from devops_cli.lang import MESSAGES


class OutputCapReached(UnexpectedModelBehavior):
    """A model reply ended with the finish reason `length`: the model did not stop, and the cap
    ended the call. The message names the cap, and it is the reason of the stopped step. The run
    drops a reply that a hook rejects, so the error holds it in `response`, for the spend."""

    response: ModelResponse

    def __init__(self, response: ModelResponse, cap: int) -> None:
        super().__init__(MESSAGES.roadmap.implement_stop_capped.format(tokens=cap))
        self.response = response


def output_cap_hooks(cap: int) -> Hooks[None]:
    """The capability for the agent of a step whose replies the cap of `cap` tokens ends."""

    async def stop_at_cap(
        _ctx: RunContext[Any], /, *, request_context: ModelRequestContext, response: ModelResponse
    ) -> ModelResponse:
        """Pass on a reply, or raise `OutputCapReached` when the cap ended it."""
        if response.finish_reason == "length":
            raise OutputCapReached(response, cap)
        return response

    return Hooks(after_model_request=stop_at_cap)
