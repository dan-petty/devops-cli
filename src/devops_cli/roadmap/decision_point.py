"""Decision points (ADR 0020): a named place of a workflow that picks one band of a closed set.

A `DecisionPoint` holds the name of the point (`<area>.<what>`), its fixed questions, the evidence
builder that makes the digest from the input of the point, what each band does, the path of its
cuts file, its rule when a rule is proven, and whether it asks the decision model. A point is
defined beside its workflow, and `decision_registry.REGISTRY` lists every point.

A `ResolverChain` resolves a point in this order and stops at the first resolver that answers:

1. the rule of the point, a deterministic function of the digest;
2. the decision model that `ai.decision_model` names, with all questions in one request, and the
   cuts of the point (`decision_step.band_of`) for the band;
3. the fallback: no band, and the workflow does what it did before the point. An error of the
   request, a missing answer or cut, or a digest that holds a secret gives the fallback, and the
   log names the cause.

`ResolverChain.decide` sends the request on the one blocking portal of the process, so a caller
that runs an event loop may call it. `ResolverChain.adecide` awaits the same request on the loop of
its caller and uses no portal. Both write the same record and the same count.

The mode of a point (`roadmap.decisions`) says what the band does: with `shadow` the chain runs and
the workflow acts as with `off`, and with `on` the band acts. `chain_of` gives no chain for the
mode `off`, nor for a point with no rule while no decision model is configured: then the point
sends no request, writes no record and counts nothing.

Each decision writes one decision record, a log line, and one count of
`devops_cli_decision_point_total`. The workflow writes one outcome record with the identifier of
the decision when it knows the real result. `join` makes the labelled cases of the next fit
(`decision_fit.FitCase`) from the two lists of records. A point returns a band and never a text.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_ai.models.decision import DecisionQuestion, DecisionRequest, DecisionResponse

from devops_cli.config.constants import CONST_ROADMAP_DECISION_POINT_MAX_SERIES
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.decision_fit import FitCase
from devops_cli.roadmap.decision_step import (
    FAILED,
    Band,
    DecisionStepError,
    Thresholds,
    adecide_all,
    band_of,
    decide_all,
    probabilities_of,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.instruments import DECISION_POINT_TOTAL, emit

if TYPE_CHECKING:
    from pydantic_ai.models.decision import DecisionModel

    from devops_cli.config.settings import Settings

logger = logging.getLogger(__name__)

# The band label of a decision that no resolver answered.
NO_BAND: Final[str] = "none"
# The start of the log line of a decision record and of an outcome record.
DECISION_PREFIX: Final[str] = "decision "
OUTCOME_PREFIX: Final[str] = "decision outcome "
_NAME: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")
_ERROR_CHARS: Final[int] = 300


class Mode(StrEnum):
    """The mode of a point in `roadmap.decisions`. The value is a label of the metric."""

    OFF = "off"
    SHADOW = "shadow"
    ON = "on"


class Resolver(StrEnum):
    """The resolver that gave a decision. The value is a label of the metric."""

    RULE = "rule"
    MODEL = "model"
    FALLBACK = "fallback"


type Rule = Callable[[Mapping[str, Any]], Band | None]


@dataclass(frozen=True)
class DecisionPoint[T]:
    """One decision point: `evidence` makes the digest from the input `T` of the point, `cuts` is
    the path of the data file of its fit (`Thresholds`), `rule` gives a band or None from the
    digest, and `asks_model` is false for a point whose rule meets its bar. `counts_only` says that
    the digest holds counts only, so its record may hold it. `timeout` bounds the request."""

    name: str
    questions: Mapping[str, DecisionQuestion]
    evidence: Callable[[T], dict[str, Any]]
    bands: Mapping[Band, str]
    cuts: Path
    rule: Rule | None = None
    asks_model: bool = True
    counts_only: bool = False
    timeout: float = 30.0

    def __post_init__(self) -> None:
        texts = MESSAGES.roadmap
        if not _NAME.fullmatch(self.name):
            raise ValueError(texts.decision_point_name.format(name=self.name))
        if set(self.bands) != set(Band):
            raise ValueError(texts.decision_point_bands.format(point=self.name))
        if not self.resolvers:
            raise ValueError(texts.decision_point_no_resolver.format(point=self.name))

    @property
    def resolvers(self) -> tuple[Resolver, ...]:
        """The resolvers of the point besides the fallback, in the order of the chain."""
        return (
            *((Resolver.RULE,) if self.rule else ()),
            *((Resolver.MODEL,) if self.asks_model else ()),
        )

    def series(self) -> frozenset[tuple[str, str, str, str]]:
        """The label sets (point, resolver, band, mode) that the point can count: each band for
        each of its resolvers, and `none` for the fallback, in the modes `shadow` and `on`."""
        modes = (Mode.SHADOW.value, Mode.ON.value)
        answered = {
            (self.name, resolver.value, band.value, mode)
            for resolver in self.resolvers
            for band in Band
            for mode in modes
        }
        return frozenset(
            answered | {(self.name, Resolver.FALLBACK.value, NO_BAND, mode) for mode in modes}
        )

    def thresholds(self) -> Thresholds:
        """The fitted cuts of the point, from its data file."""
        return Thresholds.load(self.cuts)

    def request(self, state: dict[str, Any]) -> DecisionRequest:
        """The one request of the point: the digest `state` and the questions. A digest that holds
        a secret raises `DecisionStepError`, because the request leaves the cluster for the hosted
        model (SECURITY.md)."""
        text = json.dumps(state, ensure_ascii=False, default=str)
        if mask_secrets(text) != text:
            raise DecisionStepError(MESSAGES.roadmap.decision_point_secret.format(point=self.name))
        return DecisionRequest(state=state, questions=dict(self.questions))


class DecisionRecord(BaseModel):
    """The record of one decision: the identifier (point, subject and a time-ordered UUID), the
    mode, the resolver, the band (None for the fallback), the model that answered, the day of the
    fit of the cuts, the answers, the questions at their flag cut, and the digest. A digest of text
    is in the record as a SHA-256 hash only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    point: str
    subject: str
    mode: Mode
    resolver: Resolver
    band: Band | None
    model: str = ""
    cuts: str = ""
    answers: dict[str, float] = Field(default_factory=dict)
    flagged: list[str] = Field(default_factory=list)
    digest: dict[str, Any] | None = None
    digest_sha256: str = ""

    @property
    def acts(self) -> bool:
        """Whether the band acts: the mode is `on` and a resolver gave a band."""
        return self.mode is Mode.ON and self.band is not None

    def line(self) -> str:
        """The log line of the record."""
        return DECISION_PREFIX + self.model_dump_json()


class OutcomeRecord(BaseModel):
    """The real result of a decision: whether the costly path had to run (`must_run`), how much a
    skip of the case loses (`weight`), and a short label of the result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    point: str
    must_run: bool
    weight: int = Field(ge=0)
    result: str

    def line(self) -> str:
        """The log line of the record."""
        return OUTCOME_PREFIX + self.model_dump_json()


@dataclass(frozen=True)
class _Resolved:
    """What a resolver gave: the resolver, the band, the day of the cuts and the flagged questions."""

    resolver: Resolver
    band: Band | None = None
    cuts: str = ""
    flagged: tuple[str, ...] = ()


class ResolverChain[T]:
    """The chain of one point in one mode. `model_name` is the decision model, empty for none; a
    test gives `model`, which then answers in place of a model built from `settings`."""

    def __init__(
        self,
        point: DecisionPoint[T],
        mode: Mode,
        *,
        model_name: str = "",
        model: DecisionModel[Any] | None = None,
        settings: Settings | None = None,
    ) -> None:
        if mode is Mode.OFF:
            raise ValueError(MESSAGES.roadmap.decision_point_off.format(point=point.name))
        self.point = point
        self.mode = mode
        self._model_name = model_name if point.asks_model else ""
        self._model = model
        self._settings = settings
        if point.rule is None and not self._model_name:
            raise ValueError(MESSAGES.roadmap.decision_point_no_resolver.format(point=point.name))

    @cached_property
    def _thresholds(self) -> Thresholds:
        return self.point.thresholds()

    def decide(self, given: T, *, subject: object) -> DecisionRecord:
        """The decision for `given`, the input of the point for `subject` (the item or the run). It
        sends the request on the blocking portal of the process, so it may run in a thread that
        runs an event loop. It writes the decision record and the count, and it never raises an
        error of the model."""
        state: dict[str, Any] = {}
        answers: dict[str, float] = {}
        try:
            state = self.point.evidence(given)
            resolved = self._resolve(state, answers)
        except FAILED as exc:
            resolved = self._failed(subject, exc)
        return self._counted(subject, state, resolved, answers)

    async def adecide(self, given: T, *, subject: object) -> DecisionRecord:
        """The decision for `given`, awaited on the event loop of the caller, which uses no
        blocking portal. It writes the decision record and the count, and it never raises an error
        of the model."""
        state: dict[str, Any] = {}
        answers: dict[str, float] = {}
        try:
            state = self.point.evidence(given)
            resolved = await self._aresolve(state, answers)
        except FAILED as exc:
            resolved = self._failed(subject, exc)
        return self._counted(subject, state, resolved, answers)

    def _failed(self, subject: object, exc: BaseException) -> _Resolved:
        """The fallback of an error of the chain, with its cause in the log."""
        logger.warning(
            MESSAGES.roadmap.decision_point_failed.format(
                point=self.point.name,
                subject=subject,
                error=f"{type(exc).__name__}: {exc}"[:_ERROR_CHARS],
            )
        )
        return _Resolved(Resolver.FALLBACK)

    def _counted(
        self, subject: object, state: dict[str, Any], resolved: _Resolved, answers: dict[str, float]
    ) -> DecisionRecord:
        """The record of the decision, its log line and its one count."""
        record = self._record(
            f"{self.point.name}/{subject}/{uuid.uuid7()}", subject, state, resolved, answers
        )
        logger.info(record.line())
        emit(
            DECISION_POINT_TOTAL,
            1,
            {
                "point": self.point.name,
                "resolver": record.resolver.value,
                "band": record.band.value if record.band else NO_BAND,
                "mode": self.mode.value,
            },
        )
        return record

    def _resolve(self, state: dict[str, Any], answers: dict[str, float]) -> _Resolved:
        """The first resolver that answers, with the request sent on the blocking portal. The model
        puts its answers in `answers` before the cuts give the band, so a record of a fallback keeps
        them."""
        if (started := self._started(state)) is not None:
            return started
        (response,) = decide_all(
            [self.point.request(state)],
            model=self._model,
            model_name=self._model_name,
            settings=self._settings,
            timeout=self.point.timeout,
        )
        return self._banded(response, answers)

    async def _aresolve(self, state: dict[str, Any], answers: dict[str, float]) -> _Resolved:
        """The first resolver that answers, with the request awaited on the event loop of the
        caller. The model puts its answers in `answers` before the cuts give the band, so a record
        of a fallback keeps them."""
        if (started := self._started(state)) is not None:
            return started
        (response,) = await adecide_all(
            [self.point.request(state)],
            model=self._model,
            model_name=self._model_name,
            settings=self._settings,
            timeout=self.point.timeout,
        )
        return self._banded(response, answers)

    def _started(self, state: dict[str, Any]) -> _Resolved | None:
        """The decision that the rule or the fallback gives, or None when the model answers."""
        if self.point.rule is not None and (band := self.point.rule(state)) is not None:
            return _Resolved(Resolver.RULE, band)
        return None if self._model_name else _Resolved(Resolver.FALLBACK)

    def _banded(self, response: DecisionResponse, answers: dict[str, float]) -> _Resolved:
        """The decision of the model: its answers go into `answers`, and the cuts of the point give
        the band and the flagged questions."""
        answers.update(probabilities_of(response))
        fitted = self._thresholds
        band = band_of(answers, fitted.cuts)
        flagged = tuple(name for name, cut in fitted.cuts.items() if answers[name] >= cut.flag_at)
        return _Resolved(Resolver.MODEL, band, fitted.fitted, flagged)

    def _record(
        self,
        identifier: str,
        subject: object,
        state: dict[str, Any],
        resolved: _Resolved,
        answers: dict[str, float],
    ) -> DecisionRecord:
        text = json.dumps(state, ensure_ascii=False, sort_keys=True, default=str)
        return DecisionRecord(
            id=identifier,
            point=self.point.name,
            subject=str(subject),
            mode=self.mode,
            resolver=resolved.resolver,
            band=resolved.band,
            model=self._model_name if answers or resolved.resolver is Resolver.MODEL else "",
            cuts=resolved.cuts,
            answers=answers,
            flagged=list(resolved.flagged),
            digest=state if self.point.counts_only and mask_secrets(text) == text else None,
            digest_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )


def chain_of[T](
    point: DecisionPoint[T], settings: Settings, *, model: DecisionModel[Any] | None = None
) -> ResolverChain[T] | None:
    """The chain of `point` under `settings`, or None when the point does not run: its mode in
    `roadmap.decisions` is `off`, or it has no rule while no decision model can answer it."""
    mode = Mode(settings.roadmap.decisions.get(point.name, Mode.OFF))
    model_name = settings.ai.decision_model if point.asks_model else ""
    if mode is Mode.OFF or (point.rule is None and not model_name):
        return None
    return ResolverChain(point, mode, model_name=model_name, model=model, settings=settings)


def record_outcome(
    decision: DecisionRecord, *, must_run: bool, weight: int, result: str
) -> OutcomeRecord:
    """Write the outcome record of `decision` and return it."""
    outcome = OutcomeRecord(
        id=decision.id, point=decision.point, must_run=must_run, weight=weight, result=result
    )
    logger.info(outcome.line())
    return outcome


def parse_record(line: str) -> DecisionRecord | OutcomeRecord | None:
    """The record that the log line `line` holds, or None for any other line."""
    kinds: tuple[tuple[str, type[DecisionRecord] | type[OutcomeRecord]], ...] = (
        (OUTCOME_PREFIX, OutcomeRecord),
        (DECISION_PREFIX, DecisionRecord),
    )
    for prefix, kind in kinds:
        if line.startswith(prefix):
            try:
                return kind.model_validate_json(line.removeprefix(prefix))
            except ValidationError:
                return None
    return None


@dataclass(frozen=True)
class LabelledCase:
    """A decision with its real outcome."""

    decision: DecisionRecord
    outcome: OutcomeRecord

    def fit_case(self) -> FitCase:
        """The case for the fit of the cuts: the answers and the label of the outcome."""
        return FitCase(
            self.decision.id,
            dict(self.decision.answers),
            must_run=self.outcome.must_run,
            weight=self.outcome.weight,
        )


@dataclass(frozen=True)
class Join:
    """The decisions with an outcome, and the decisions with none."""

    cases: tuple[LabelledCase, ...]
    unmatched: tuple[DecisionRecord, ...]

    def fit_cases(self) -> list[FitCase]:
        """The labelled cases that hold answers of the model, for the next fit."""
        return [case.fit_case() for case in self.cases if case.decision.answers]


def join(decisions: Iterable[DecisionRecord], outcomes: Iterable[OutcomeRecord]) -> Join:
    """Join each decision with the outcome of its identifier. A decision with no outcome stays out
    of the cases."""
    by_id = {outcome.id: outcome for outcome in outcomes}
    cases: list[LabelledCase] = []
    unmatched: list[DecisionRecord] = []
    for decision in decisions:
        outcome = by_id.get(decision.id)
        if outcome is None:
            unmatched.append(decision)
        else:
            cases.append(LabelledCase(decision, outcome))
    return Join(tuple(cases), tuple(unmatched))


class Registry:
    """The decision points by name. It refuses a name given two times and a catalogue whose label
    sets are more than `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`."""

    def __init__(self, points: Iterable[DecisionPoint[Any]]) -> None:
        self._points: dict[str, DecisionPoint[Any]] = {}
        for point in points:
            if point.name in self._points:
                raise ValueError(MESSAGES.roadmap.decision_point_twice.format(point=point.name))
            self._points[point.name] = point
        count = self.series_count
        if count > CONST_ROADMAP_DECISION_POINT_MAX_SERIES:
            raise ValueError(
                MESSAGES.roadmap.decision_point_series.format(
                    count=count, bound=CONST_ROADMAP_DECISION_POINT_MAX_SERIES
                )
            )

    @property
    def names(self) -> tuple[str, ...]:
        """The names of the points, sorted."""
        return tuple(sorted(self._points))

    @property
    def series_count(self) -> int:
        """The label sets that all points together can count."""
        return sum(len(point.series()) for point in self._points.values())

    def point(self, name: str) -> DecisionPoint[Any]:
        """The point of `name`."""
        return self._points[name]


__all__ = [
    "DECISION_PREFIX",
    "NO_BAND",
    "OUTCOME_PREFIX",
    "DecisionPoint",
    "DecisionRecord",
    "Join",
    "LabelledCase",
    "Mode",
    "OutcomeRecord",
    "Registry",
    "Resolver",
    "ResolverChain",
    "Rule",
    "chain_of",
    "join",
    "parse_record",
    "record_outcome",
]
