"""The one-retry rebuild of a refused pull request body (#3599).

A pull request body that breaks form rules is sent to the model once with the list of problems.
A second refusal stops the item with the `refused_reply` failure class. The stage job asks the
same prompt, with `BodyReply`, for a shorter text of a plan body over its room (#6319).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.ai import ModelGatewayUnreachableError
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.roadmap import RefusedPullReply
from devops_cli.exceptions.validation import ValidationError
from devops_cli.roadmap.intake.intake_model import gateway_address

# The prompt of the rewrite: the implement job and the stage job (#6319) ask it for a shorter or a
# fixed body text.
BODY_TASK: Final[str] = "roadmap_implement_body.md"


class BodyReply(BaseModel):
    """The reply of the model for a rewritten pull request body."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""


class PullBodyClient(Protocol):
    """What the retry step needs of `LLMClient`."""

    def chat_structured(self, system: str, prompt: str, schema: type[BodyReply]) -> BodyReply: ...


class GatewayPullBody:
    """The call through the `analysis` task's client. A test passes its own `client`."""

    def __init__(
        self,
        ai: AIConfig | None = None,
        *,
        api_key: str | None = None,
        client: PullBodyClient | None = None,
    ) -> None:
        self._ai = ai
        self._api_key = api_key
        self._client = client

    def rewrite(self, text: str, problems: Sequence[str]) -> str:
        """Ask the model to rewrite the refused body."""
        from devops_cli.ai.client.models import StructuredOutputValidationError

        request = json.dumps({"text": text, "problems": list(problems)})
        try:
            reply = self._built().chat_structured(load_task_prompt(BODY_TASK), request, BodyReply)
            return reply.text
        except StructuredOutputValidationError:
            return ""
        except (DevOpsCLIError, OSError) as exc:
            address = gateway_address(self._ai) if self._ai else "gateway"
            raise ModelGatewayUnreachableError(
                address, exc, consequence="body rewrite wrote nothing"
            ) from exc

    def _built(self) -> PullBodyClient:
        if self._client is None:
            from devops_cli.ai.client import get_llm_client

            config = self._ai.for_task("analysis") if self._ai else None
            self._client = get_llm_client(task="analysis", config=config, api_key=self._api_key)
        return self._client


def _extract_problems(exc: ValidationError) -> list[str]:
    if hasattr(exc, "problems") and exc.problems:
        return list(exc.problems)
    msg = str(exc)
    lines = [line.removeprefix("- ").strip() for line in msg.splitlines() if line.strip()]
    return lines or [msg]


def retried_body(
    *,
    text: str,
    build: Callable[[str], str],
    rewrite: Callable[[str, Sequence[str]], str] | None = None,
) -> str:
    """Build the body once, and retry once through rewrite on ValidationError."""
    try:
        return build(text)
    except ValidationError as exc:
        problems = _extract_problems(exc)
        if rewrite is None:
            raise RefusedPullReply(problems) from exc
        rebuilt = rewrite(text, problems)
        try:
            return build(rebuilt)
        except ValidationError as second_exc:
            second_problems = _extract_problems(second_exc)
            raise RefusedPullReply(second_problems) from second_exc


__all__ = [
    "BODY_TASK",
    "BodyReply",
    "GatewayPullBody",
    "PullBodyClient",
    "RefusedPullReply",
    "retried_body",
]
