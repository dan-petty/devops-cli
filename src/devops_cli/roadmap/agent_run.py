"""What the roadmap jobs that run a pydantic-ai agent share (#2398, #2664): the stream handler
that keeps a long reply inside the gateway's tunnel, and the spend record of a run."""

from __future__ import annotations

import re
from collections.abc import AsyncIterable, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from pydantic_ai import RunContext
from pydantic_ai.exceptions import AgentRunError, ModelAPIError, ModelHTTPError, ModelTimeoutError
from pydantic_ai.messages import AgentStreamEvent, ModelMessage, ModelResponse

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.spend import track_request_spend
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_ROADMAP_RUN_ERROR_CHARS,
    CONST_ROADMAP_RUN_ERROR_READ_CHARS,
)
from devops_cli.security.sanitizer import mask_secrets

# The HTTP statuses of a model reply that refuse the key, which stop the whole run.
_REFUSED_KEY_STATUSES = frozenset({401, 403})


async def drain_events(_ctx: RunContext[None], events: AsyncIterable[AgentStreamEvent]) -> None:
    """Read the run's events. With a handler, pydantic-ai streams each model request, so a long
    reply keeps the gateway's tunnel open past its cut of 125 s, as `LLMClient` streams (#2379)."""
    async for _ in events:
        pass


def model_call_error(exc: ModelAPIError, subject: str) -> AIClientError:
    """The job's class for a failed model call of a run, with no text of the model's reply, and
    with the HTTP status or the timeout of the call (#2562). `subject` names the run, such as
    `The investigation's`."""
    if isinstance(exc, ModelHTTPError) and exc.status_code in _REFUSED_KEY_STATUSES:
        return AICredentialsError(f"The model refused the key (HTTP {exc.status_code}).")
    return AIClientError(
        f"{subject} model call failed ({type(exc).__name__}).",
        status=exc.status_code if isinstance(exc, ModelHTTPError) else None,
        timed_out=isinstance(exc, ModelTimeoutError),
    )


def bounded_text(text: str) -> str:
    """`text`, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters. The text is cut to a
    multiple of that limit before the masking, which is slower than linear, and the masked text is
    cut after, so a cut cannot split a secret."""
    masked = mask_secrets(text[:CONST_ROADMAP_RUN_ERROR_READ_CHARS]).strip()
    return masked[:CONST_ROADMAP_RUN_ERROR_CHARS]


# A provider can echo what the model wrote into its error text, as Ollama does in `raw='...'`.
# So the text of a body stops at the first `=` or `;`, where the echo of a value begins (#2794).
# Its quoted words stay: they are the words of the provider's error (#2922), and `mask_secrets`
# hides a secret in them by its form.
_BODY_DATA = re.compile(r"[;=]")


def _body_string(body: object) -> str:
    """The error text in the `body` of a model's error reply: the body when it is a string, else
    its `message`, else its `error`, read the same way. No other value of a body is read, for
    `mask_secrets` finds a secret by its form in a text, and not the value of a key such as
    `api_key` in the repr of a dict."""
    if isinstance(body, str):
        return body
    if isinstance(body, Mapping):
        return next(
            (text for key in ("message", "error") if (text := _body_string(body.get(key)))), ""
        )
    return ""


def body_error_text(body: object) -> str:
    """The error text in the `body` of a model's error reply, safe to show: masked and cut like
    other stop text, then reduced to the part that the provider wrote and not the model."""
    first = (_body_string(body).splitlines() or [""])[0]
    description = _BODY_DATA.split(bounded_text(first), maxsplit=1)[0]
    return "".join(char for char in description if char.isprintable()).strip()


# A part of a message in quotes, such as a tool name, and the characters from which pydantic-ai
# writes data of the reply of the model into a message (#2562).
_QUOTED = re.compile(r"""(['"`]).*?\1""")
_REPLY_DATA = re.compile(r"""[:;='"`]""")


def run_error_message(stopped: AgentRunError) -> str:
    """The fixed description in the `message` of a pydantic-ai error, to log (#2562).

    It is not `str(stopped)`: for `UnexpectedModelBehavior` that adds the `body`, the text of the
    model. The message itself can hold data that the model chose: the id of a tool call, the name
    of a tool, the repr of a part. So it keeps the first line only, hides each quoted part, and
    stops at the first `:`, `;` or `=`. It then drops the characters that cannot print.
    """
    first = (stopped.message.splitlines() or [""])[0]
    hidden = _QUOTED.sub("<text>", bounded_text(first))
    description = _REPLY_DATA.split(hidden, maxsplit=1)[0]
    return "".join(char for char in description if char.isprintable()).strip()


def record_run_spend(
    model: Any, messages: Sequence[ModelMessage], seconds: float, *, stage: str
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


__all__ = [
    "body_error_text",
    "bounded_text",
    "drain_events",
    "model_call_error",
    "record_run_spend",
    "run_error_message",
]
