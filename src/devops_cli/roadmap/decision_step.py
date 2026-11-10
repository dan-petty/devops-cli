"""The shared parts of a decision step (ADR 0019).

A decision step picks one band for a case from the answers of TypeSafe Jev to short closed
questions. The step builds the evidence and the questions. This module holds the rest:

- `Cut` and `Thresholds`: the cuts of each question, fitted on labelled data and stored as a file
  in the repository with the model, the date and the numbers that gave them.
- `band_of`: the band for the probabilities of a case. A probability under `continue_below` for
  every question is *continue*. One at or above `flag_at` is *flag*. Any other case is *review*.
- `decide_all`: one request for each piece of evidence, sent at the same time. Each request uses
  its own model and closes it on the loop that used it, so a second request does not meet a
  closed loop (#4319). Any error raises, and the step then fails open to the existing path.

The module sends no text of an answer anywhere. A Jev answer is evidence and never the only
control of a path.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self, cast

import httpx2
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior, UserError
from pydantic_ai.models.decision import (
    DecisionModelSettings,
    DecisionRequest,
    DecisionResponse,
    NoulAnswer,
)

from devops_cli.config.constants import CONST_ROADMAP_DECISION_STEP_CONCURRENCY
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from pydantic_ai.models.decision import DecisionModel

    from devops_cli.config.settings import Settings


class Band(StrEnum):
    """The outcome of a decision step. The value is a label of the metric."""

    CONTINUE = "continue"
    REVIEW = "review"
    FLAG = "flag"


class DecisionStepError(ValueError):
    """The answers of Jev do not give a band: a question has no answer or no cut."""


# The errors of a Jev request that make a step fail open.
FAILED: Final[tuple[type[BaseException], ...]] = (
    ModelAPIError,
    UnexpectedModelBehavior,
    UserError,
    DevOpsCLIError,
    DecisionStepError,
    OSError,
    TimeoutError,
)


class Cut(BaseModel):
    """The cuts of one question: a probability under `continue_below` is a clear no, and one at
    or above `flag_at` is a flag."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    continue_below: float
    flag_at: float

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not 0.0 <= self.continue_below <= self.flag_at <= 1.0:
            raise ValueError("0 <= continue_below <= flag_at <= 1 must hold: flag_at is too low")
        return self


class Thresholds(BaseModel):
    """The cuts of a step with their provenance: the step, the Jev model, the day of the fit, the
    number of cases it used, and `report`, the numbers that gave the cuts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: str
    model: str
    fitted: str
    cases: int
    cuts: Mapping[str, Cut]
    report: Mapping[str, Any]

    @classmethod
    def load(cls, path: Path) -> Self:
        """The cuts in the JSON file `path`."""
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


def band_of(probabilities: Mapping[str, float], cuts: Mapping[str, Cut]) -> Band:
    """The band for `probabilities`, one for each question of `cuts`. A question with no answer
    or with no cut raises `DecisionStepError`."""
    unknown = sorted(set(probabilities) - set(cuts))
    if unknown:
        raise DecisionStepError(MESSAGES.roadmap.decision_step_no_cut.format(names=unknown))
    missing = sorted(set(cuts) - set(probabilities))
    if missing:
        raise DecisionStepError(MESSAGES.roadmap.decision_step_no_answer.format(names=missing))
    if any(probabilities[name] >= cut.flag_at for name, cut in cuts.items()):
        return Band.FLAG
    if any(probabilities[name] >= cut.continue_below for name, cut in cuts.items()):
        return Band.REVIEW
    return Band.CONTINUE


def probabilities_of(response: DecisionResponse) -> dict[str, float]:
    """The probability of each yes/no answer of `response`, by question name."""
    return {
        name: answer.noul
        for name, answer in response.answers.items()
        if isinstance(answer, NoulAnswer)
    }


async def _decide_closing(
    request: DecisionRequest, decider: DecisionModel[Any], options: DecisionModelSettings, own: bool
) -> DecisionResponse:
    """One request on this loop. A model that this request built closes its client on this loop,
    so the next request does not meet a closed loop (#4319)."""
    try:
        async with decider:
            return await decider.decide(request, options)
    finally:
        client = getattr(decider, "client", None)
        if own and isinstance(client, httpx2.AsyncClient):
            await client.aclose()


def _decide_one(
    request: DecisionRequest,
    model: DecisionModel[Any] | None,
    settings: Settings | None,
    timeout: float,
) -> DecisionResponse:
    """The one place that sends a request to Jev. When `decide_with_jev` of `ai.jev` (#4331) lands,
    its call replaces the body of this function."""
    from devops_cli.ai.jev import create_jev_model

    decider = model or create_jev_model(settings=settings)
    options = cast(
        DecisionModelSettings, {**(getattr(decider, "settings", None) or {}), "timeout": timeout}
    )
    return asyncio.run(_decide_closing(request, decider, options, own=model is None))


def decide_all(
    requests: Sequence[DecisionRequest],
    *,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
    timeout: float = 30.0,
) -> list[DecisionResponse]:
    """The responses of Jev to `requests`, in order, sent at the same time. With no `model`, each
    request builds its own from `settings`. The first error raises."""
    if not requests:
        return []
    with ThreadPoolExecutor(max_workers=CONST_ROADMAP_DECISION_STEP_CONCURRENCY) as pool:
        futures = [
            pool.submit(_decide_one, request, model, settings, timeout) for request in requests
        ]
        return [future.result() for future in futures]


__all__ = [
    "FAILED",
    "Band",
    "Cut",
    "DecisionStepError",
    "Thresholds",
    "band_of",
    "decide_all",
    "probabilities_of",
]
