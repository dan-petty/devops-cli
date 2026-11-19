"""The judge of the consolidation job (#3740): what a model says of one shortlist.

The job of `consolidate.py` gives each shortlist to a judge, one function: `ShortlistJudge.judge`
takes a `ShortlistCase` (the anchor, the members, their texts and the evidence that tools found)
and returns a `Judgement` (the group, and one `MemberVerdict` for each member). The rules in code
never ask how a judge made its verdicts, so another judge can replace this one.

`GatewayShortlistJudge` makes two tool-less `chat_structured` calls with the client of
`ai.for_task("consolidate")`: a proposal, then a refutation that sees the proposal and the member
bodies and returns kept, weakened (link-only) or dropped, with reasons. The texts of the items are
data in the user message and never an instruction. A reply is a proposal and nothing more: code
checks it, and a verdict only flags a group. A call that cannot reach its model raises
`ModelGatewayUnreachableError`, which names the gateway.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Protocol, Self, TypeVar

import httpx2
from pydantic import BaseModel, ConfigDict, Field, model_validator

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_CONSOLIDATE_MARGIN_SECONDS,
    CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.ai import ModelGatewayUnreachableError
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.intake.intake_model import Embedder, gateway_address

_PROPOSE_PROMPT = "roadmap_consolidate_propose.md"
_REFUTE_PROMPT = "roadmap_consolidate_refute.md"
_NOTHING_WRITTEN = "consolidate wrote no plan"
_T = TypeVar("_T", bound=BaseModel)
# A model call that fails: the clients raise a `DevOpsCLIError`, and a connection that they do not
# wrap is an `OSError`.
_FAILED_CALL = (DevOpsCLIError, OSError)


def _is_timeout(exc: BaseException) -> bool:
    """Whether `exc` represents a request timeout (#4856)."""
    if isinstance(exc, (TimeoutError, httpx2.TimeoutException)):
        return True
    if getattr(exc, "timed_out", False):
        return True
    msg = str(exc).lower()
    if "time" in msg and "out" in msg:
        return True
    if exc.__cause__ is not None and _is_timeout(exc.__cause__):
        return True
    return False


class Shape(StrEnum):
    """How a group is consolidated."""

    MERGE = "merge-into-anchor"
    PARENT = "parent-task-with-children"
    CLOSE = "close-as-duplicate"
    LINK_ONLY = "link-only"


class Action(StrEnum):
    """What a later apply does with one member."""

    MERGE = "merge"
    CHILD = "child"
    LINK = "link"
    CLOSE_WHEN_ANCHOR_MERGES = "close-when-anchor-merges"


class Refutation(StrEnum):
    """What the refutation says of a proposal: it holds, it holds as a link only, or it fails."""

    KEPT = "kept"
    WEAKENED = "weakened"
    DROPPED = "dropped"


class Citation(BaseModel):
    """What a verdict cites: an issue, or a line of a file. Code checks that it exists."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue: int | None = Field(default=None, ge=1, description="The number of a cited issue.")
    path: str | None = Field(default=None, description="The path of a cited file.")
    line: int | None = Field(default=None, ge=1, description="The line of the cited file.")
    note: str = ""

    @model_validator(mode="after")
    def _names_one_thing(self) -> Self:
        by_issue = self.issue is not None and self.path is None and self.line is None
        by_line = self.issue is None and bool(self.path) and self.line is not None
        if not (by_issue or by_line):
            raise ValueError("A citation names an issue, or a path with a line.")
        return self

    @property
    def text(self) -> str:
        """The citation as `#12` or `src/a.py:3`."""
        return f"#{self.issue}" if self.issue is not None else f"{self.path}:{self.line}"


class CaseItem(BaseModel):
    """An item as the judge sees it: the number, the title and the text of a person."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    text: str


class CaseMember(CaseItem):
    """A member of a shortlist, with the evidence that tools found for it. `protected` says that
    the item has a milestone, so a merge cannot take it."""

    evidence: tuple[str, ...] = ()
    protected: bool = False


class ShortlistCase(BaseModel):
    """What a judge reads: an anchor and the members that may share its cause. `anchor_started`
    says that work on the anchor has begun, so only a link can name it."""

    model_config = ConfigDict(frozen=True)

    anchor: CaseItem
    members: tuple[CaseMember, ...]
    anchor_started: bool = False

    @property
    def digest(self) -> str:
        """The hash of the case and of the prompts: a case with the same digest has the same
        judgement, so a rerun makes no model call for it."""
        prompts = load_task_prompt(_PROPOSE_PROMPT) + load_task_prompt(_REFUTE_PROMPT)
        return hash_text(self.model_dump_json() + prompts)


class MemberVerdict(BaseModel):
    """The verdict for one member: the action, the reason and what the verdict cites."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int
    action: Action
    reason: str
    citations: tuple[Citation, ...] = ()


class Judgement(BaseModel):
    """What a judge says of a shortlist: the group and the verdict for each member. `verdict` is
    that of the refutation; a judge with no refutation says `kept`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    anchor: int
    shape: Shape
    theme: str
    root_cause: str
    consistency_gained: str
    risks: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)
    verdict: Refutation
    reasons: tuple[str, ...] = ()
    members: tuple[MemberVerdict, ...] = ()


class ShortlistJudge(Protocol):
    """The one function that makes verdicts for a shortlist."""

    def judge(
        self,
        case: ShortlistCase,
        *,
        deadline: float | None = None,
        clock: Callable[[], float] = ...,
    ) -> Judgement | None:
        """The group of `case` and a verdict for each member that belongs to it."""


# ── The replies ──


class ProposedMember(BaseModel):
    """A member of the proposal, as the model wrote it."""

    model_config = ConfigDict(extra="forbid")

    number: int
    action: Action
    reason: str
    citations: list[Citation] = Field(default_factory=list)


class Proposal(BaseModel):
    """The reply of the proposal call. A shape or an action outside the lists fails the schema."""

    model_config = ConfigDict(extra="forbid")

    anchor: int
    shape: Shape
    theme: str
    root_cause: str
    consistency_gained: str
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    members: list[ProposedMember] = Field(default_factory=list)


class Rebuttal(BaseModel):
    """The reply of the refutation call."""

    model_config = ConfigDict(extra="forbid")

    verdict: Refutation
    reasons: list[str] = Field(default_factory=list)


class JudgeClient(Protocol):
    """What the judge needs of `LLMClient`."""

    def chat_structured[T: BaseModel](
        self, system: str, prompt: str, schema: type[T], *, timeout: float | None = None
    ) -> T: ...


def _items(case: ShortlistCase) -> dict[str, object]:
    return {
        "anchor": case.anchor.model_dump(),
        "anchor_started": case.anchor_started,
        "members": [member.model_dump() for member in case.members],
    }


def proposal_request(case: ShortlistCase) -> str:
    """The JSON the proposal call reads."""
    return json.dumps({"stage": "proposal", **_items(case)}, ensure_ascii=False, indent=1)


def refutation_request(case: ShortlistCase, proposal: Proposal) -> str:
    """The JSON the refutation call reads: the proposal and the member bodies."""
    body = {"stage": "refutation", "proposal": proposal.model_dump(mode="json"), **_items(case)}
    return json.dumps(body, ensure_ascii=False, indent=1)


class GatewayShortlistJudge:
    """The judge that asks the model of the `consolidate` task twice. The client is built on first
    use. A test passes its own `client`."""

    def __init__(
        self, ai: AIConfig, *, api_key: str | None = None, client: JudgeClient | None = None
    ) -> None:
        self._ai = ai
        self._api_key = api_key
        self._client = client

    def _call_judge_step(
        self,
        client: JudgeClient,
        prompt_file: str,
        request_body: str,
        schema_cls: type[_T],
        deadline: float | None,
        clock: Callable[[], float],
    ) -> _T | None:
        from devops_cli.ai.client.models import StructuredOutputValidationError

        req_timeout = self._budget_timeout(deadline, clock)
        if req_timeout is None:
            return None

        try:
            return self._call_structured(
                client,
                load_task_prompt(prompt_file),
                request_body,
                schema_cls,
                timeout=req_timeout,
            )
        except StructuredOutputValidationError:
            raise
        except TimeoutError, httpx2.TimeoutException:
            return None
        except _FAILED_CALL as exc:
            if _is_timeout(exc):
                return None
            raise ModelGatewayUnreachableError(
                gateway_address(self._ai), exc, consequence=_NOTHING_WRITTEN
            ) from exc

    def judge(
        self,
        case: ShortlistCase,
        *,
        deadline: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> Judgement | None:
        """A proposal, then its refutation. A schema failure raises
        `StructuredOutputValidationError` for this shortlist; a gateway that does not answer
        raises `ModelGatewayUnreachableError`. A request timeout returns None (#4856)."""
        actual_clock = clock or time.monotonic
        client = self._built()
        proposal = self._call_judge_step(
            client,
            _PROPOSE_PROMPT,
            proposal_request(case),
            Proposal,
            deadline,
            actual_clock,
        )
        if proposal is None:
            return None

        rebuttal = self._call_judge_step(
            client,
            _REFUTE_PROMPT,
            refutation_request(case, proposal),
            Rebuttal,
            deadline,
            actual_clock,
        )
        if rebuttal is None:
            return None

        return Judgement(
            anchor=proposal.anchor,
            shape=proposal.shape,
            theme=proposal.theme,
            root_cause=proposal.root_cause,
            consistency_gained=proposal.consistency_gained,
            risks=tuple(proposal.risks),
            confidence=proposal.confidence,
            verdict=rebuttal.verdict,
            reasons=tuple(rebuttal.reasons),
            members=tuple(
                MemberVerdict(
                    number=m.number,
                    action=m.action,
                    reason=m.reason,
                    citations=tuple(m.citations),
                )
                for m in proposal.members
            ),
        )

    def _budget_timeout(self, deadline: float | None, clock: Callable[[], float]) -> float | None:
        """The per-request timeout: at most 300 s, or remaining budget minus 60 s (#4856)."""
        if deadline is None:
            return CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS
        remaining = deadline - clock()
        margin = CONST_ROADMAP_CONSOLIDATE_MARGIN_SECONDS
        if remaining - margin <= 0:
            return None
        return min(CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS, remaining - margin)

    def _call_structured[T: BaseModel](
        self,
        client: JudgeClient,
        system: str,
        prompt: str,
        schema: type[T],
        *,
        timeout: float,
    ) -> T:
        try:
            return client.chat_structured(system, prompt, schema, timeout=timeout)
        except TypeError:
            return client.chat_structured(system, prompt, schema)

    def _built(self) -> JudgeClient:
        if self._client is None:
            from devops_cli.ai.client import get_llm_client

            self._client = get_llm_client(
                task="consolidate",
                config=self._ai.for_task("consolidate"),
                api_key=self._api_key,
                request_timeout_seconds=CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS,
            )
        return self._client


class GatewayEmbedder:
    """The embeddings of the `embedding` task, through the memory, Valkey and disk tiers of the
    embedding cache. A call that fails raises `ModelGatewayUnreachableError`. A test passes its
    own `embedder`."""

    def __init__(
        self, ai: AIConfig, *, api_key: str | None = None, embedder: Embedder | None = None
    ) -> None:
        self._ai = ai
        self._api_key = api_key
        self._embedder = embedder

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector for each text."""
        try:
            return self._built().embed_texts(list(texts))
        except _FAILED_CALL as exc:
            raise ModelGatewayUnreachableError(
                gateway_address(self._ai), exc, consequence=_NOTHING_WRITTEN
            ) from exc

    def _built(self) -> Embedder:
        if self._embedder is None:
            from devops_cli.ai.rag.embedding_disk_cache import embedding_disk_cache
            from devops_cli.ai.rag.embeddings import create_embedder

            # The vectors stay in the shared tiers of the cache, memory, Valkey and disk, as the
            # vectors of intake do, so the job keeps no store of its own (#4665).
            self._embedder = create_embedder(
                self._ai, api_key=self._api_key, disk_cache=embedding_disk_cache()
            )
        return self._embedder


def build_consolidate_models() -> tuple[GatewayShortlistJudge, GatewayEmbedder]:
    """The judge and the embedder with this checkout's AI settings and API key."""
    from devops_cli.config.settings import get_ai_api_key, load_settings

    settings = load_settings()
    key = get_ai_api_key(settings)
    return GatewayShortlistJudge(settings.ai, api_key=key), GatewayEmbedder(
        settings.ai, api_key=key
    )


__all__ = [
    "Action",
    "CaseItem",
    "CaseMember",
    "Citation",
    "GatewayEmbedder",
    "GatewayShortlistJudge",
    "Judgement",
    "MemberVerdict",
    "Proposal",
    "Rebuttal",
    "Refutation",
    "Shape",
    "ShortlistCase",
    "ShortlistJudge",
    "build_consolidate_models",
    "proposal_request",
    "refutation_request",
]
