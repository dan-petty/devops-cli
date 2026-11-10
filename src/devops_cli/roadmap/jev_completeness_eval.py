"""The labelled set and the score of the Jev completeness check (#4308).

`devops roadmap eval completeness` runs the check of `jev_completeness.py` on each case of
`tests/fixtures/roadmap_eval/completeness/` and reports two rates:

- the recall of incomplete drafts: the share of the incomplete cases that the check holds;
- the false holds: the share of the complete cases that the check holds.

A case is a folder with `case.json` (the label, the kind, the criteria of the issue and where the
case came from) and `draft.diff` (the diff that Jev reads). A `complete` case is the diff of a
merged pull request whose issue lists acceptance criteria. An `incomplete` case is either a plan
that the stage golden set labels `criterion_dropped`, or a merged diff from which one hunk is
removed, so that a criterion is no longer delivered (`removed` names the hunk). The label of a
complete plan comes from the absence of a `criterion_dropped` defect in a review that finds 27% of
the defects, so a few complete plans may drop a criterion: the false-hold rate is then an upper
bound, and the recall is exact only for the removed hunks.

The report keeps the probability of each criterion, so a threshold can be chosen again with no
new request. The switch `roadmap.stage.jev_completeness` stays off when the false holds exceed
`CONST_ROADMAP_JEV_EVAL_MAX_FALSE_HOLD_RATE` or the set is too small to say.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict
from pydantic_ai.models.decision import DecisionModel

from devops_cli.config.constants import (
    CONST_AI_JEV_USD_PER_MILLION_INPUT_TOKENS,
    CONST_ROADMAP_JEV_CRITERION_THRESHOLD,
    CONST_ROADMAP_JEV_EVAL_MAX_FALSE_HOLD_RATE,
    CONST_ROADMAP_JEV_EVAL_MIN_CASES,
    CONST_ROADMAP_JEV_EVAL_MIN_CASES_PER_LABEL,
    CONST_ROADMAP_JEV_EVAL_SWEEP,
    CONST_ROADMAP_JEV_MIN_TEST_SCORE,
)
from devops_cli.core.repo import find_repo_root
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.jev_completeness import (
    Completeness,
    CompletenessOutcome,
    DraftSubject,
    assess,
)

CASES_DIRECTORY: Final[Path] = Path("tests/fixtures/roadmap_eval/completeness")
_CASE_FILE: Final[str] = "case.json"
_DIFF_FILE: Final[str] = "draft.diff"


class Label(StrEnum):
    """What a person knows about the draft of a case."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class CompletenessCase(BaseModel):
    """One case of the set."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: DraftSubject
    label: Label
    source: dict[str, Any]
    criteria: list[str]
    diff: str
    removed: dict[str, Any] | None = None
    note: str | None = None


def cases_directory(directory: Path | None = None) -> Path:
    """The folder of the cases: `directory`, else the folder of this checkout."""
    return directory or find_repo_root() / CASES_DIRECTORY


def load_cases(directory: Path | None = None) -> list[CompletenessCase]:
    """Read each case folder of `directory`, in the order of the folder names."""
    folder = cases_directory(directory)
    cases = []
    for case_file in sorted(folder.glob(f"*/{_CASE_FILE}")):
        meta = json.loads(case_file.read_text(encoding="utf-8"))
        diff = (case_file.parent / _DIFF_FILE).read_text(encoding="utf-8")
        cases.append(CompletenessCase(**meta, diff=diff))
    return cases


@dataclass(frozen=True)
class CaseResult:
    """What the check gave for one case."""

    id: str
    label: Label
    kind: DraftSubject
    result: Completeness

    @property
    def answered(self) -> bool:
        """Whether Jev answered: the check neither failed nor skipped the case."""
        return self.result.outcome in (CompletenessOutcome.PASSED, CompletenessOutcome.HELD)

    def held(self, threshold: float, *, tests: bool) -> bool:
        """Whether the draft is held at `threshold`: a criterion below it, or, with `tests`, a
        score of the tests below the minimum."""
        weak = self.result.test_score is not None and (
            self.result.test_score < CONST_ROADMAP_JEV_MIN_TEST_SCORE
        )
        return any(p < threshold for p in self.result.probabilities) or (tests and weak)


def run_cases(
    cases: Sequence[CompletenessCase], *, new_model: Callable[[], DecisionModel[Any]]
) -> list[CaseResult]:
    """Ask Jev about each case, one request at a time. Each request gets a new model: the HTTP
    client of a model belongs to the event loop of its first request, which ends with that request,
    so a second request on the same model fails with "Event loop is closed"."""
    return [
        CaseResult(
            case.id,
            case.label,
            case.kind,
            assess(case.criteria, case.diff, case.kind, model=new_model()),
        )
        for case in cases
    ]


@dataclass(frozen=True)
class Rates:
    """The recall of incomplete drafts and the false holds, from the answered cases."""

    incomplete: int
    held_incomplete: int
    complete: int
    held_complete: int

    @property
    def recall(self) -> float | None:
        return self.held_incomplete / self.incomplete if self.incomplete else None

    @property
    def false_hold_rate(self) -> float | None:
        return self.held_complete / self.complete if self.complete else None


def rates(results: Sequence[CaseResult], threshold: float, *, tests: bool) -> Rates:
    """The two rates at `threshold`, over the cases that Jev answered."""
    answered = [r for r in results if r.answered]
    incomplete = [r for r in answered if r.label is Label.INCOMPLETE]
    complete = [r for r in answered if r.label is Label.COMPLETE]
    return Rates(
        len(incomplete),
        sum(r.held(threshold, tests=tests) for r in incomplete),
        len(complete),
        sum(r.held(threshold, tests=tests) for r in complete),
    )


def usd(results: Sequence[CaseResult]) -> float:
    """The cost of the run at the price of Jev for input tokens."""
    tokens = sum(r.result.input_tokens for r in results)
    return tokens * CONST_AI_JEV_USD_PER_MILLION_INPUT_TOKENS / 1_000_000


def switch_stays_off(results: Sequence[CaseResult]) -> list[str]:
    """The reasons to keep the switch off at the configured thresholds, empty when none holds."""
    texts = MESSAGES.roadmap
    current = rates(results, CONST_ROADMAP_JEV_CRITERION_THRESHOLD, tests=True)
    reasons = []
    answered = current.incomplete + current.complete
    smallest = min(current.incomplete, current.complete)
    if (
        answered < CONST_ROADMAP_JEV_EVAL_MIN_CASES
        or smallest < CONST_ROADMAP_JEV_EVAL_MIN_CASES_PER_LABEL
    ):
        reasons.append(
            texts.jev_eval_reason_small.format(
                answered=answered,
                minimum=CONST_ROADMAP_JEV_EVAL_MIN_CASES,
                per_label=CONST_ROADMAP_JEV_EVAL_MIN_CASES_PER_LABEL,
            )
        )
    rate = current.false_hold_rate
    if rate is not None and rate > CONST_ROADMAP_JEV_EVAL_MAX_FALSE_HOLD_RATE:
        reasons.append(
            texts.jev_eval_reason_false_holds.format(
                rate=_percent(rate), limit=_percent(CONST_ROADMAP_JEV_EVAL_MAX_FALSE_HOLD_RATE)
            )
        )
    return reasons


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def render(results: Sequence[CaseResult], *, model: str, gateway: str) -> str:
    """The report as text: the two rates at the configured thresholds, the sweep, the cases that
    Jev did not answer, the cost, and the decision on the switch."""
    texts = MESSAGES.roadmap
    lines = [texts.jev_eval_title.format(cases=len(results), model=model, gateway=gateway)]
    current = rates(results, CONST_ROADMAP_JEV_CRITERION_THRESHOLD, tests=True)
    lines.append(
        texts.jev_eval_recall.format(
            held=current.held_incomplete, total=current.incomplete, rate=_percent(current.recall)
        )
    )
    lines.append(
        texts.jev_eval_false_holds.format(
            held=current.held_complete,
            total=current.complete,
            rate=_percent(current.false_hold_rate),
        )
    )
    lines.append(texts.jev_eval_sweep_header)
    for threshold in CONST_ROADMAP_JEV_EVAL_SWEEP:
        row = rates(results, threshold, tests=False)
        lines.append(
            texts.jev_eval_sweep_row.format(
                threshold=threshold,
                recall=_percent(row.recall),
                false=_percent(row.false_hold_rate),
            )
        )
    unanswered = [r for r in results if not r.answered]
    if unanswered:
        lines.append(
            texts.jev_eval_unanswered.format(
                count=len(unanswered), cases=", ".join(r.id for r in unanswered)
            )
        )
    lines.append(texts.jev_eval_cost.format(usd=usd(results)))
    reasons = switch_stays_off(results)
    lines.append(
        texts.jev_eval_decision_off.format(reasons=" ".join(reasons))
        if reasons
        else texts.jev_eval_decision_ok
    )
    return "\n".join(lines) + "\n"


def report_json(results: Sequence[CaseResult], *, model: str, gateway: str, taken: str) -> str:
    """The report as JSON, with the probabilities of each case so a threshold can be chosen again."""
    current = rates(results, CONST_ROADMAP_JEV_CRITERION_THRESHOLD, tests=True)
    body = {
        "model": model,
        "gateway": gateway,
        "taken": taken,
        "criterion_threshold": CONST_ROADMAP_JEV_CRITERION_THRESHOLD,
        "min_test_score": CONST_ROADMAP_JEV_MIN_TEST_SCORE,
        "recall": current.recall,
        "false_hold_rate": current.false_hold_rate,
        "usd": usd(results),
        "switch_stays_off": switch_stays_off(results),
        "cases": [
            {
                "id": r.id,
                "label": r.label.value,
                "kind": r.kind,
                "outcome": r.result.outcome.value,
                "probabilities": list(r.result.probabilities),
                "test_score": r.result.test_score,
                "input_tokens": r.result.input_tokens,
                "reason": r.result.reason,
            }
            for r in results
        ],
    }
    return json.dumps(body, indent=2)


__all__ = [
    "CASES_DIRECTORY",
    "CaseResult",
    "CompletenessCase",
    "Label",
    "Rates",
    "cases_directory",
    "load_cases",
    "rates",
    "render",
    "report_json",
    "run_cases",
    "switch_stays_off",
    "usd",
]
