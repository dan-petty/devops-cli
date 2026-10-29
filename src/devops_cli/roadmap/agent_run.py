"""What the roadmap jobs that run a pydantic-ai agent share (#2398, #2664): the stream handler
that keeps a long reply inside the gateway's tunnel, and the spend record of a run."""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any
from urllib.parse import urlsplit

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import AgentStreamEvent, ModelMessage, ModelResponse

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.spend import track_request_spend
from devops_cli.config.constants import CONST_AI_GATEWAY_PROVIDER

# The HTTP statuses of a model reply that refuse the key, which stop the whole run.
_REFUSED_KEY_STATUSES = frozenset({401, 403})


async def drain_events(_ctx: RunContext[None], events: AsyncIterable[AgentStreamEvent]) -> None:
    """Read the run's events. With a handler, pydantic-ai streams each model request, so a long
    reply keeps the gateway's tunnel open past its cut of 125 s, as `LLMClient` streams (#2379)."""
    async for _ in events:
        pass


def model_call_error(exc: ModelAPIError, subject: str) -> AIClientError:
    """The job's class for a failed model call of a run, with no text of the model's reply.
    `subject` names the run, such as `The investigation's`."""
    if isinstance(exc, ModelHTTPError) and exc.status_code in _REFUSED_KEY_STATUSES:
        return AICredentialsError(f"The model refused the key (HTTP {exc.status_code}).")
    return AIClientError(f"{subject} model call failed ({type(exc).__name__}).")


def record_run_spend(
    model: Any, messages: list[ModelMessage], seconds: float, *, stage: str
) -> None:
    """One spend record for the run's model replies, under `stage`; none when the run got no
    reply. A model the bridge sends to a gateway names the gateway's URL in `served_by`, and its
    record names the provider `gateway`, as `LLMClient`'s records do."""
    replies = [message for message in messages if isinstance(message, ModelResponse)]
    if not replies:
        return
    served_by = getattr(model, "served_by", None)
    track_request_spend(
        provider=CONST_AI_GATEWAY_PROVIDER if served_by else str(getattr(model, "system", "")),
        model=str(getattr(model, "model_name", "unknown")),
        server=urlsplit(served_by).netloc if served_by else "unknown",
        prompt_tokens=sum(reply.usage.input_tokens for reply in replies),
        completion_tokens=sum(reply.usage.output_tokens for reply in replies),
        request_type="agent_run",
        duration_seconds=seconds,
        stage=stage,
    )


__all__ = ["drain_events", "model_call_error", "record_run_spend"]
