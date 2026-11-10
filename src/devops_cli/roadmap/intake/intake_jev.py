"""Jev decides the proposal fields of intake (#4298).

TypeSafe Jev (`typesafe/jev-1.14`) is a System One decision model: it answers pick-one, rubric and
yes/no questions with a probability and a confidence, and writes no text. One request carries a
question for each field that has a fixed list:

- `type`: a `ChoiceQuestion` over the `type/*` labels, asked only when the title gives none;
- `priority`: a `ChoiceQuestion` over the priorities a model may propose;
- `value` and `effort`: a `ScoreQuestion` of three levels each;
- `duplicate_of_<number>`: a `NoulQuestion` for each nearest item.

The answers become the same `ModelProposal` that the triage model returns, so the checks of
intake decide which values stand. A neighbour whose probability reaches the threshold is a
possible original, and intake only flags it: the candidate is still placed. Jev gives no
evidence for a P0 and no related item.

With `roadmap.intake.jev` set to `shadow`, `intake_jev_shadow` uses the questions and the answers of
this module for an observation, and the triage model decides.

Jev fails open. An error, a timeout or a confidence below the least leaves the whole proposal to
the triage model, and a counter records which fields came from which model. The evaluation
(`devops roadmap eval jev`) builds the model with `fall_back=False`, so a Jev failure shows as a
skipped candidate and the report compares Jev alone.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, cast

import httpx2
from pydantic import JsonValue
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior, UserError
from pydantic_ai.models.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionModel,
    DecisionModelSettings,
    DecisionQuestion,
    DecisionRequest,
    DecisionResponse,
    NoulAnswer,
    NoulCriteria,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

from devops_cli.config.constants import (
    CONST_ROADMAP_JEV_DATA_NOTE,
    CONST_ROADMAP_JEV_DUPLICATE_NO,
    CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD,
    CONST_ROADMAP_JEV_DUPLICATE_YES,
    CONST_ROADMAP_JEV_EFFORT_LEVELS,
    CONST_ROADMAP_JEV_INSTRUCTIONS,
    CONST_ROADMAP_JEV_MIN_CONFIDENCE,
    CONST_ROADMAP_JEV_PRIORITY_CRITERIA,
    CONST_ROADMAP_JEV_TIMEOUT_SECONDS,
    CONST_ROADMAP_JEV_VALUE_LEVELS,
)
from devops_cli.config.settings import Settings
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake.intake_model import (
    IntakeModel,
    ModelProposal,
    Neighbour,
    ProposalRequest,
    UnusableProposalError,
)
from devops_cli.telemetry.instruments import ROADMAP_INTAKE_JEV_FIELDS_TOTAL, emit

logger = logging.getLogger(__name__)

_DUPLICATE_PREFIX = "duplicate_of_"
_Levels = tuple[tuple[str, str], ...]


class JevField(StrEnum):
    """A proposal field that intake asks Jev for: a label of the counter."""

    TYPE = "type"
    PRIORITY = "priority"
    VALUE = "value"
    EFFORT = "effort"
    DUPLICATE = "duplicate"


class JevOutcome(StrEnum):
    """Which model gave a field: a label of the counter."""

    JEV = "jev"
    FALLBACK = "fallback"


class JevUnusableError(ValueError):
    """Jev answered, but not with a confidence that intake takes."""


# A failed call of Jev: the library raises `ModelAPIError` for HTTP and connection errors,
# `UnexpectedModelBehavior` for a body it can't read, `UserError` for a request it can't send;
# the model comes from the gateway settings, whose errors are `DevOpsCLIError`s.
FAILED = (ModelAPIError, UnexpectedModelBehavior, UserError, DevOpsCLIError, OSError)


def _instruction(field: JevField, **named: object) -> str:
    return CONST_ROADMAP_JEV_INSTRUCTIONS[field.value].format(**named) + CONST_ROADMAP_JEV_DATA_NOTE


def _rubric(levels: _Levels) -> list[JsonValue]:
    return [f"{name}: {meaning}" for name, meaning in levels]


def _type_criteria(request: ProposalRequest) -> dict[str, JsonValue]:
    meanings = dict(request.type_notes)
    return {label: meanings.get(label) or label for label in request.types}


def _questions(request: ProposalRequest) -> dict[str, DecisionQuestion]:
    """The questions of one request: a choice, two rubrics and a noul for each nearest item."""
    questions: dict[str, DecisionQuestion] = {}
    if request.needs_type:
        questions[JevField.TYPE] = ChoiceQuestion(
            instructions=_instruction(JevField.TYPE), criteria=_type_criteria(request)
        )
    questions[JevField.PRIORITY] = ChoiceQuestion(
        instructions=_instruction(JevField.PRIORITY),
        criteria=dict(CONST_ROADMAP_JEV_PRIORITY_CRITERIA),
    )
    questions[JevField.VALUE] = ScoreQuestion(
        instructions=_instruction(JevField.VALUE), criteria=_rubric(CONST_ROADMAP_JEV_VALUE_LEVELS)
    )
    questions[JevField.EFFORT] = ScoreQuestion(
        instructions=_instruction(JevField.EFFORT),
        criteria=_rubric(CONST_ROADMAP_JEV_EFFORT_LEVELS),
    )
    for near in request.shortlist:
        questions[f"{_DUPLICATE_PREFIX}{near.number}"] = NoulQuestion(
            instructions=_instruction(JevField.DUPLICATE, number=near.number),
            criteria=NoulCriteria(
                true=CONST_ROADMAP_JEV_DUPLICATE_YES, false=CONST_ROADMAP_JEV_DUPLICATE_NO
            ),
        )
    return questions


def _state(request: ProposalRequest) -> JsonValue:
    return {
        "title": request.title,
        "body": request.body,
        "shortlist": [
            {"number": n.number, "title": n.title, "state": n.state, "excerpt": n.excerpt}
            for n in request.shortlist
        ],
    }


def _confident(name: str, answer: ChoiceAnswer | ScoreAnswer, least: float) -> None:
    if answer.confidence < least:
        raise JevUnusableError(
            MESSAGES.roadmap.intake_jev_low_confidence.format(
                field=name, confidence=answer.confidence, least=least
            )
        )


def _choice(name: str, response: DecisionResponse, least: float) -> tuple[str, str]:
    """The option a choice answer picked, and the reason line for it."""
    answer = cast(ChoiceAnswer, response.answers[name])
    _confident(name, answer, least)
    reason = MESSAGES.roadmap.intake_jev_choice_reason.format(
        choice=answer.choice, probability=answer.probabilities.get(answer.choice, 0.0)
    )
    return answer.choice, reason


def level_name(answer: ScoreAnswer, levels: _Levels) -> str:
    """The name of the level that a score answer rounds to."""
    return levels[min(max(round(answer.score), 0), len(levels) - 1)][0]


def _level(name: str, levels: _Levels, response: DecisionResponse, least: float) -> tuple[str, str]:
    """The level a score answer rounds to, and the reason line for it."""
    answer = cast(ScoreAnswer, response.answers[name])
    _confident(name, answer, least)
    picked = level_name(answer, levels)
    reason = MESSAGES.roadmap.intake_jev_score_reason.format(
        level=picked, confidence=answer.confidence
    )
    return picked, reason


def best_neighbour(
    request: ProposalRequest, response: DecisionResponse
) -> tuple[Neighbour | None, float]:
    """The nearest item with the highest yes/no probability, and that probability: none and 0 for
    a request with no nearest item."""
    best_near, best = None, 0.0
    for near in request.shortlist:
        probability = cast(NoulAnswer, response.answers[f"{_DUPLICATE_PREFIX}{near.number}"]).noul
        if probability > best:
            best_near, best = near, probability
    return best_near, best


def _original(request: ProposalRequest, response: DecisionResponse) -> dict[str, Any]:
    """The fields of the nearest item that Jev is sure asks for the same change, or none."""
    near, best = best_neighbour(request, response)
    if near is None or best < CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD:
        return {}
    return {
        "duplicate_of": near.number,
        "shared_change": near.title,
        "duplicate_reason": MESSAGES.roadmap.intake_jev_duplicate_reason.format(probability=best),
    }


def proposal_from(
    request: ProposalRequest,
    response: DecisionResponse,
    least: float = CONST_ROADMAP_JEV_MIN_CONFIDENCE,
) -> ModelProposal:
    """The `ModelProposal` that the answers of Jev make. Raises `JevUnusableError` when a choice
    or score answer has a confidence below `least`."""
    fields: dict[str, Any] = {}
    if request.needs_type:
        fields["type"], fields["type_reason"] = _choice(JevField.TYPE, response, least)
    fields["priority"], fields["priority_reason"] = _choice(JevField.PRIORITY, response, least)
    fields["value"], fields["value_reason"] = _level(
        JevField.VALUE, CONST_ROADMAP_JEV_VALUE_LEVELS, response, least
    )
    fields["effort"], fields["effort_reason"] = _level(
        JevField.EFFORT, CONST_ROADMAP_JEV_EFFORT_LEVELS, response, least
    )
    return ModelProposal.model_validate(fields | _original(request, response))


def asked_fields(request: ProposalRequest) -> list[JevField]:
    """The fields that a request asks Jev for."""
    fields = [JevField.TYPE] if request.needs_type else []
    fields += [JevField.PRIORITY, JevField.VALUE, JevField.EFFORT]
    return fields + ([JevField.DUPLICATE] if request.shortlist else [])


async def _decide_in_context(
    decider: DecisionModel[Any], request: DecisionRequest, settings: DecisionModelSettings
) -> DecisionResponse:
    """One request inside the context of the model. Each request runs on its own event loop,
    and the context makes a provider that owns its client replace one that a closed loop left."""
    async with decider:
        return await decider.decide(request, settings)


async def _decide_and_close(
    decider: DecisionModel[Any], request: DecisionRequest, settings: DecisionModelSettings
) -> DecisionResponse:
    """One request with a model that only this request uses. The client of a model that the
    gateway settings build is not the provider's own: it belongs to the caller, who closes it
    on the loop that used it, or its connections outlive that loop and the next request fails
    with `Event loop is closed`."""
    try:
        return await _decide_in_context(decider, request, settings)
    finally:
        client = getattr(decider, "client", None)
        if isinstance(client, httpx2.AsyncClient):
            await client.aclose()


class JevIntakeModel:
    """Intake's model calls with Jev for the proposal and `base` for the embeddings and the
    fallback. `decider` is the Jev decision model; with none, the first request builds it from
    `settings` through the gateway. With `fall_back` false, a request that Jev can't decide
    raises `UnusableProposalError` and no counter is sent: the evaluation compares Jev alone.
    `min_confidence` is the least confidence of a choice or score answer that is taken.
    """

    def __init__(
        self,
        base: IntakeModel,
        decider: DecisionModel[Any] | None = None,
        *,
        settings: Settings | None = None,
        fall_back: bool = True,
        min_confidence: float = CONST_ROADMAP_JEV_MIN_CONFIDENCE,
    ) -> None:
        self._base = base
        self._given = decider
        self._settings = settings
        self._fall_back = fall_back
        self._least = min_confidence

    def _fresh_decider(self) -> DecisionModel[Any]:
        """A model for one request, built from the settings through the gateway."""
        from devops_cli.ai.jev import create_jev_model

        return create_jev_model(settings=self._settings)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """The embeddings of the base model."""
        return self._base.embed(texts)

    def _decide(self, request: DecisionRequest) -> DecisionResponse:
        decider = self._given or self._fresh_decider()
        options = {"timeout": CONST_ROADMAP_JEV_TIMEOUT_SECONDS}
        merged = cast(
            DecisionModelSettings, {**(getattr(decider, "settings", None) or {}), **options}
        )
        run = _decide_in_context if self._given else _decide_and_close
        return asyncio.run(run(decider, request, merged))

    def answers(self, request: ProposalRequest) -> DecisionResponse:
        """The raw answers of Jev to the questions of `request`. A failed request raises one of
        the errors in `FAILED`."""
        return self._decide(DecisionRequest(state=_state(request), questions=_questions(request)))

    def _count(self, fields: Sequence[JevField], outcome: JevOutcome) -> None:
        if not self._fall_back:
            return
        for field in fields:
            emit(
                ROADMAP_INTAKE_JEV_FIELDS_TOTAL,
                1,
                {"field": field.value, "outcome": outcome.value},
            )

    def propose(self, request: ProposalRequest) -> ModelProposal:
        """The proposal that Jev's answers make, or the base model's when Jev fails."""
        fields = asked_fields(request)
        try:
            response = self.answers(request)
            proposal = proposal_from(request, response, self._least)
        except (*FAILED, JevUnusableError) as exc:
            reason = str(exc)[:300]
            if not self._fall_back:
                raise UnusableProposalError(reason) from exc
            logger.warning(MESSAGES.roadmap.intake_jev_fallback.format(error=reason))
            self._count(fields, JevOutcome.FALLBACK)
            return self._base.propose(request)
        self._count(fields, JevOutcome.JEV)
        return proposal


__all__ = [
    "FAILED",
    "JevField",
    "JevIntakeModel",
    "JevOutcome",
    "JevUnusableError",
    "asked_fields",
    "best_neighbour",
    "level_name",
    "proposal_from",
]
