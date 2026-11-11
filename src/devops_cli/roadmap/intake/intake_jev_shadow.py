"""The shadow mode of the Jev intake labels (#4395, ADR 0019 rule 6).

With `roadmap.intake.jev` set to `shadow`, the triage model gives every label and every flag, as it
does with the setting `off`. After intake checks the reply of the triage model, `ShadowIntakeModel`
asks Jev the same fields in one request (the questions of `intake_jev`) and compares the answers:

- `type`, `priority`, `value` and `effort`: the option that Jev picks and its probability, beside
  the answer of the triage model;
- `duplicate`: the nearest item with the highest probability, and that probability, beside the
  possible original that intake took from the triage reply. Jev flags an item only at the
  threshold of `intake_jev`. The flag is a record and never an action: nothing is closed or
  dropped.

The result is a `ShadowObservation`. Intake writes it as the mark `intake.jev_shadow` in the job
record of the issue, in the same write as the Priority, so a later analysis finds it with the
issue number and joins it with the final labels (`devops roadmap eval jev --from-shadow`). The mark
holds the time, the answers and probabilities, and no text of the issue. A Jev error or timeout
changes nothing: the fields count `jev_error` and the issue gets no mark. The counts go to the
counter of mode `on`, `devops_cli_roadmap_intake_jev_fields_total`, with the outcomes of shadow:
`agree`, `differ` and `jev_error`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any, NamedTuple, Self, cast

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.models.decision import (
    ChoiceAnswer,
    DecisionModel,
    DecisionResponse,
    ScoreAnswer,
)

from devops_cli.config.constants import (
    CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD,
    CONST_ROADMAP_JEV_EFFORT_LEVELS,
    CONST_ROADMAP_JEV_VALUE_LEVELS,
)
from devops_cli.config.settings import Settings
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake.intake_jev import (
    FAILED,
    JevField,
    JevIntakeModel,
    JevOutcome,
    asked_fields,
    best_neighbour,
    count_field,
    level_name,
)
from devops_cli.roadmap.intake.intake_model import (
    IntakeModel,
    ModelProposal,
    ProposalRequest,
)

logger = logging.getLogger(__name__)

_PRECISION = 2


class ShadowError(ValueError):
    """The answers of Jev miss a question or hold a wrong kind of answer."""


class ShadowAnswer(NamedTuple):
    """One field of an observation: the answer of Jev, its probability (from 0 to 1), and the
    answer of the triage model. An empty text is no answer: for the duplicate, no item reaches the threshold."""

    jev: str
    probability: Annotated[float, Field(ge=0, le=1)]
    triage: str

    @property
    def agrees(self) -> bool:
        return self.jev == self.triage


class ShadowObservation(BaseModel):
    """What Jev answered for one candidate beside the triage model: the time of the proposal and
    a `ShadowAnswer` for each asked field, by field name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    answers: Mapping[str, ShadowAnswer]

    def to_mark(self) -> str:
        """The compact JSON that the job record holds."""
        return self.model_dump_json()

    @classmethod
    def from_mark(cls, mark: str) -> Self:
        """The observation that `to_mark` wrote; a mark that is not one raises `ValueError`."""
        return cls.model_validate_json(mark)


def _answer_of(response: DecisionResponse, name: str, kind: type[Any]) -> Any:
    answer = response.answers.get(name)
    if not isinstance(answer, kind):
        raise ShadowError(MESSAGES.roadmap.intake_jev_shadow_no_answer.format(name=name))
    return answer


def _choice(response: DecisionResponse, field: JevField, triage: str) -> ShadowAnswer:
    answer = cast(ChoiceAnswer, _answer_of(response, field.value, ChoiceAnswer))
    probability = answer.probabilities.get(answer.choice, answer.confidence)
    return ShadowAnswer(answer.choice, round(probability, _PRECISION), triage)


def _score(
    response: DecisionResponse, field: JevField, levels: tuple[tuple[str, str], ...], triage: str
) -> ShadowAnswer:
    answer = cast(ScoreAnswer, _answer_of(response, field.value, ScoreAnswer))
    return ShadowAnswer(level_name(answer, levels), round(answer.confidence, _PRECISION), triage)


def _duplicate(
    request: ProposalRequest, response: DecisionResponse, original: int | None
) -> ShadowAnswer:
    for each in request.shortlist:
        _answer_of(response, f"duplicate_of_{each.number}", object)
    near, probability = best_neighbour(request, response)
    flagged = near is not None and probability >= CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD
    return ShadowAnswer(
        str(near.number) if flagged and near is not None else "",
        round(probability, _PRECISION),
        str(original) if original is not None else "",
    )


def observation_of(
    request: ProposalRequest,
    response: DecisionResponse,
    triage: ModelProposal,
    original: int | None,
    at: datetime,
) -> ShadowObservation:
    """The observation for the `response` of Jev and the `triage` reply, whose checked possible
    original is `original`. A missing answer raises `ShadowError`."""
    answers: dict[str, ShadowAnswer] = {}
    if request.needs_type:
        answers[JevField.TYPE] = _choice(response, JevField.TYPE, triage.type)
    answers[JevField.PRIORITY] = _choice(response, JevField.PRIORITY, triage.priority)
    answers[JevField.VALUE] = _score(
        response, JevField.VALUE, CONST_ROADMAP_JEV_VALUE_LEVELS, triage.value
    )
    answers[JevField.EFFORT] = _score(
        response, JevField.EFFORT, CONST_ROADMAP_JEV_EFFORT_LEVELS, triage.effort
    )
    if request.shortlist:
        answers[JevField.DUPLICATE] = _duplicate(request, response, original)
    return ShadowObservation(at=at, answers=answers)


def _count_observation(observation: ShadowObservation) -> None:
    for name, answer in observation.answers.items():
        count_field(name, JevOutcome.AGREE if answer.agrees else JevOutcome.DIFFER)


class ShadowIntakeModel:
    """Intake's model calls with the triage model (`base`) for the proposal and the embeddings,
    and Jev for the observation. `decider` is the Jev decision model; with none, each request
    builds it from `settings` through the gateway. `now` gives the time of an observation."""

    def __init__(
        self,
        base: IntakeModel,
        decider: DecisionModel[Any] | None = None,
        *,
        settings: Settings | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._base = base
        self._jev = JevIntakeModel(base, decider, settings=settings, fall_back=False)
        self._now = now or (lambda: datetime.now(UTC).replace(microsecond=0))

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """The embeddings of the base model."""
        return self._base.embed(texts)

    def propose(self, request: ProposalRequest) -> ModelProposal:
        """The proposal of the base model. Jev has no part in it."""
        return self._base.propose(request)

    def observation(
        self, request: ProposalRequest, triage: ModelProposal, duplicate: int | None
    ) -> ShadowObservation | None:
        """What Jev answers beside `triage`, or None when Jev fails: the error is logged, and each
        asked field counts `jev_error`. The counters of the fields count the other outcomes."""
        try:
            response = self._jev.answers(request)
            observation = observation_of(request, response, triage, duplicate, self._now())
        except (*FAILED, ShadowError) as exc:
            logger.warning(
                MESSAGES.roadmap.intake_jev_shadow_failed.format(
                    error=f"{type(exc).__name__}: {exc}"[:300]
                )
            )
            for field in asked_fields(request):
                count_field(field.value, JevOutcome.JEV_ERROR)
            return None
        _count_observation(observation)
        return observation

    def observe(
        self, request: ProposalRequest, triage: ModelProposal, duplicate: int | None
    ) -> str | None:
        """The mark for the job record of the issue, or None when Jev failed."""
        observation = self.observation(request, triage, duplicate)
        return observation.to_mark() if observation is not None else None


__all__ = [
    "ShadowAnswer",
    "ShadowError",
    "ShadowIntakeModel",
    "ShadowObservation",
    "observation_of",
]
