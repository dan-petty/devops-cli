"""What `devops roadmap intake` asks a model (#742): embeddings for the duplicate check, and one
structured proposal per candidate.

The model holds no tool. It sees the candidate and its nearest items as JSON data in the user
message and answers with a `ModelProposal`, whose fields are plain text so that whatever it
says reaches intake's own checks: code, not the schema, decides which values stand. Both calls
go through the existing clients, the embedder (`ai.tasks.embedding`) and the LLM client
(`ai.tasks.analysis`), and so through the gateway when one is configured. A call that can't
reach its model raises `ModelGatewayUnreachableError`, which names the gateway (the error masks
any password in it), so a run writes nothing. A model that answers, but never in the schema, raises
`UnusableProposalError` for that one candidate, which intake skips.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from functools import cached_property
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_AI_GATEWAY_PROVIDER
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.ai import ModelGatewayUnreachableError
from devops_cli.exceptions.base import DevOpsCLIError

# The prompt in `ai/tasks/` that tells the model what to return.
_SYSTEM_PROMPT = "roadmap_intake_system.md"
_NOTHING_WRITTEN = "intake wrote nothing"


class ModelEvidence(BaseModel):
    """The one piece of evidence the model may point at, as it wrote it."""

    model_config = ConfigDict(extra="ignore")

    kind: str = ""
    value: str = ""


class ModelProposal(BaseModel):
    """The model's answer for one candidate, unchecked. Each field has a one-line reason."""

    model_config = ConfigDict(extra="ignore")

    # A number, or text such as "#740": code reads it against the shortlist.
    duplicate_of: int | str | None = None
    duplicate_reason: str = ""
    type: str = ""
    type_reason: str = ""
    priority: str = ""
    priority_reason: str = ""
    value: str = ""
    value_reason: str = ""
    effort: str = ""
    effort_reason: str = ""
    evidence: ModelEvidence | None = None
    evidence_reason: str = ""


@dataclass(frozen=True)
class Neighbour:
    """One of the candidate's nearest items, as the model sees it."""

    number: int
    title: str
    state: str
    excerpt: str


@dataclass(frozen=True)
class ProposalRequest:
    """What the model is shown for one candidate: its text, its nearest items (none when the
    duplicate check is skipped), and the `type/*` labels it may pick from."""

    title: str
    body: str
    shortlist: tuple[Neighbour, ...]
    types: tuple[str, ...]

    def as_json(self) -> str:
        """The request as the JSON the user message carries."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=1)


class UnusableProposalError(ValueError):
    """The model answered, but no answer for this candidate fit `ModelProposal`."""


class IntakeModel(Protocol):
    """The two model calls intake makes."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in order."""

    def propose(self, request: ProposalRequest) -> ModelProposal:
        """The model's proposal for one candidate; `UnusableProposalError` when it has none."""


class Embedder(Protocol):
    """What intake needs of `EmbeddingsEngine`."""

    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]: ...


class ProposalClient(Protocol):
    """What intake needs of `LLMClient`."""

    def chat_structured(
        self, system: str, prompt: str, schema: type[ModelProposal]
    ) -> ModelProposal: ...


# A model call that fails: the embedder's `EmbeddingsError` and the client's `LLMInferenceError`
# are both `DevOpsCLIError`s, and a connection the clients don't wrap is an `OSError`.
_FAILED_CALL = (DevOpsCLIError, OSError)


def gateway_address(ai: AIConfig) -> str:
    """Where the model calls go: the gateway when one is configured, else the provider's endpoint."""
    if ai.gateway_enabled or ai.provider == CONST_AI_GATEWAY_PROVIDER:
        return ai.gateway_url
    return ai.api_base_url or ", ".join(ai.get_ollama_urls)


class GatewayIntakeModel:
    """Intake's model calls through the configured embedder and LLM client.

    Each client is built on first use, so a run with no candidate opens no connection. A test
    passes its own `embedder` and `client`.
    """

    def __init__(
        self,
        ai: AIConfig,
        *,
        api_key: str | None = None,
        embedder: Embedder | None = None,
        client: ProposalClient | None = None,
    ) -> None:
        self._ai = ai
        self._api_key = api_key
        self._given_embedder = embedder
        self._given_client = client

    @property
    def gateway(self) -> str:
        """The address a failure names."""
        return gateway_address(self._ai)

    @cached_property
    def _embedder(self) -> Embedder:
        if self._given_embedder is not None:
            return self._given_embedder
        from devops_cli.ai.rag.embeddings import EmbeddingsEngine

        return EmbeddingsEngine(self._ai, api_key=self._api_key)

    @cached_property
    def _client(self) -> ProposalClient:
        if self._given_client is not None:
            return self._given_client
        from devops_cli.ai.client import LLMClient

        return LLMClient(self._ai.for_task("analysis"), api_key=self._api_key)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed `texts` with the `embedding` task's model."""
        try:
            return self._embedder.embed_texts(list(texts))
        except _FAILED_CALL as exc:
            raise ModelGatewayUnreachableError(
                self.gateway, exc, consequence=_NOTHING_WRITTEN
            ) from exc

    def propose(self, request: ProposalRequest) -> ModelProposal:
        """Ask the `analysis` task's model for its proposal."""
        from devops_cli.ai.client.models import StructuredOutputValidationError

        try:
            return self._client.chat_structured(
                load_task_prompt(_SYSTEM_PROMPT), request.as_json(), ModelProposal
            )
        except StructuredOutputValidationError as exc:
            raise UnusableProposalError(str(exc)[:300]) from exc
        except _FAILED_CALL as exc:
            raise ModelGatewayUnreachableError(
                self.gateway, exc, consequence=_NOTHING_WRITTEN
            ) from exc


def build_intake_model() -> GatewayIntakeModel:
    """Intake's model calls with this checkout's AI settings and API key."""
    from devops_cli.config.settings import get_ai_api_key, load_settings

    settings = load_settings()
    return GatewayIntakeModel(settings.ai, api_key=get_ai_api_key(settings))


__all__ = [
    "Embedder",
    "GatewayIntakeModel",
    "IntakeModel",
    "ModelEvidence",
    "ModelProposal",
    "Neighbour",
    "ProposalClient",
    "ProposalRequest",
    "UnusableProposalError",
    "build_intake_model",
    "gateway_address",
]
