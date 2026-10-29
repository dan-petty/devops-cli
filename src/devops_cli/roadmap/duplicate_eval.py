"""The evaluation of intake's duplicate judgement against the set of cases a person judged (#1989).

Each case is a candidate, the item intake compared it with, and whether a person judged the
candidate a duplicate of the item (#1755). A run seeds an in-memory roadmap that holds the
case's item, plans intake for the candidate with no write, and reads intake's verdict from the
decision, so intake's own code reads the model's reply. pydantic-evals scores each verdict
against the person's and counts the verdicts; it is imported only when a run starts.

The run makes no embedding call: the roadmap of a case holds one item, so that item is the whole
shortlist whatever the vectors are. It reads the type labels from `.github/labels.yml` of the
checkout and sends no GitHub request.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.config.defaults import DEFAULT_ROADMAP_MEMORY_REPO
from devops_cli.core.repo import find_repo_root
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake import IntakeDecision, NewCandidate, Outcome, intake_candidate
from devops_cli.roadmap.intake_model import IntakeModel
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField

# The evaluation set, shipped with the package so an installed command can read it.
DUPLICATE_CASES = files("devops_cli.roadmap").joinpath("intake_duplicate_cases.json")

# The Priority that makes a case's item an Item, so intake compares the candidate with it.
_ITEM_PRIORITY = "P3-Low"
_DATASET_NAME = "intake_duplicates"


class Verdict(StrEnum):
    """Whether intake judged the candidate a duplicate of the case's item."""

    DUPLICATE = "duplicate"
    NEW_ITEM = "new item"
    SKIPPED = "skipped"


class CaseText(BaseModel):
    """A title and a short excerpt of an issue's body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    body: str


class CaseItem(CaseText):
    """The item intake compared the candidate with, by its number on GitHub."""

    number: int


class DuplicateCase(BaseModel):
    """One case of the set. `answer` is the model's recorded reply, which the tests replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    duplicate: bool
    source: str
    candidate: CaseText
    item: CaseItem
    answer: dict[str, Any] | None = None

    @property
    def expected(self) -> Verdict:
        """The person's verdict."""
        return Verdict.DUPLICATE if self.duplicate else Verdict.NEW_ITEM


@dataclass(frozen=True)
class CaseResult:
    """A case's verdict, or the error that stopped it, with intake's reason."""

    name: str
    expected: Verdict
    verdict: Verdict | None
    reason: str = ""
    error: str = ""

    @property
    def agrees(self) -> bool:
        return self.verdict is self.expected


@dataclass(frozen=True)
class DuplicateScore:
    """Each case's result, and the counts of the `duplicate` verdict from the confusion matrix."""

    results: tuple[CaseResult, ...]
    true_duplicates: int
    false_duplicates: int
    missed_duplicates: int

    @property
    def agreed(self) -> int:
        return sum(result.agrees for result in self.results)

    @property
    def failed(self) -> int:
        return sum(bool(result.error) for result in self.results)

    @property
    def said_duplicate(self) -> int:
        return self.true_duplicates + self.false_duplicates

    @property
    def expected_duplicates(self) -> int:
        return self.true_duplicates + self.missed_duplicates


class SameVector:
    """Gives every text one vector: a case's roadmap holds one item, the whole shortlist."""

    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        return [[1.0] for _ in texts]


def load_cases() -> list[DuplicateCase]:
    """The cases of the evaluation set."""
    raw = json.loads(DUPLICATE_CASES.read_text(encoding="utf-8"))["cases"]
    return TypeAdapter(list[DuplicateCase]).validate_python(raw)


def checkout_labels() -> str:
    """The text of `.github/labels.yml` at the root of the checkout the command runs in."""
    path = find_repo_root() / CONST_ROADMAP_LABELS_PATH
    if not path.is_file():
        message = MESSAGES.roadmap.intake_eval_labels_missing.format(path=CONST_ROADMAP_LABELS_PATH)
        raise ConfigurationError(message, details={"path": str(path)})
    return path.read_text(encoding="utf-8")


def _reason(decision: IntakeDecision) -> str:
    """The reason intake gives for its verdict."""
    if decision.outcome is Outcome.SKIP:
        return decision.reason
    return decision.duplicate_reason or decision.related_reason or "; ".join(decision.notes)


def judge_case(case: DuplicateCase, model: IntakeModel, labels: str) -> tuple[Verdict, str]:
    """Intake's verdict for one case, and its reason: plan intake for the candidate in a roadmap
    that holds the case's item and nothing else, and write nothing."""
    store = InMemoryRoadmapStore(repo=DEFAULT_ROADMAP_MEMORY_REPO)
    store.seed_file(CONST_ROADMAP_LABELS_PATH, labels)
    number = store.seed_issue(
        case.item.title, body=case.item.body, fields={ItemField.PRIORITY: _ITEM_PRIORITY}
    )
    candidate = NewCandidate(title=case.candidate.title, body=case.candidate.body)
    decision = intake_candidate(
        store, candidate, repo=DEFAULT_ROADMAP_MEMORY_REPO, model=model
    ).decision
    if decision.outcome is Outcome.SKIP:
        return Verdict.SKIPPED, _reason(decision)
    verdict = Verdict.DUPLICATE if decision.possible_duplicate == number else Verdict.NEW_ITEM
    return verdict, _reason(decision)


def _duplicate_counts(matrix: Any) -> tuple[int, int, int]:
    """True, false and missed `duplicate` verdicts from the confusion matrix, whose rows are the
    expected verdicts and whose columns are intake's."""
    labels: list[str] = list(matrix.class_labels)
    if Verdict.DUPLICATE.value not in labels:
        return 0, 0, 0
    index = labels.index(Verdict.DUPLICATE.value)
    rows: list[list[int]] = matrix.matrix
    true = rows[index][index]
    false = sum(row[index] for row_index, row in enumerate(rows) if row_index != index)
    missed = sum(rows[index]) - true
    return true, false, missed


def evaluate_duplicates(
    cases: Sequence[DuplicateCase], model: IntakeModel, labels: str
) -> DuplicateScore:
    """Run each case through intake with `model`, one case at a time, and score it against the
    person's verdict with pydantic-evals."""
    from pydantic_evals import Case, Dataset
    from pydantic_evals.dataset import set_eval_attribute
    from pydantic_evals.evaluators import ConfusionMatrixEvaluator, EqualsExpected

    by_name = {case.name: case for case in cases}

    def task(name: str) -> str:
        verdict, reason = judge_case(by_name[name], model, labels)
        set_eval_attribute("reason", reason)
        return verdict.value

    dataset: Dataset[str, str, None] = Dataset(
        name=_DATASET_NAME,
        cases=[
            Case(name=case.name, inputs=case.name, expected_output=case.expected.value)
            for case in cases
        ],
        evaluators=[EqualsExpected()],
        report_evaluators=[ConfusionMatrixEvaluator()],
    )
    report = dataset.evaluate_sync(task, max_concurrency=1, progress=False)
    ran = {
        case.name: CaseResult(
            name=case.name,
            expected=by_name[case.name].expected,
            verdict=Verdict(case.output),
            reason=str(case.attributes.get("reason", "")),
        )
        for case in report.cases
    }
    failed = {
        failure.name: CaseResult(
            name=failure.name,
            expected=by_name[failure.name].expected,
            verdict=None,
            error=failure.error_message,
        )
        for failure in report.failures
    }
    matrix = next(iter(report.analyses), None)
    true, false, missed = _duplicate_counts(matrix) if matrix is not None else (0, 0, 0)
    return DuplicateScore(
        results=tuple({**ran, **failed}[case.name] for case in cases),
        true_duplicates=true,
        false_duplicates=false,
        missed_duplicates=missed,
    )


def _ratio(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else MESSAGES.roadmap.intake_eval_no_ratio


def _result_line(result: CaseResult) -> str:
    texts = MESSAGES.roadmap
    if result.error:
        return texts.intake_eval_error.format(name=result.name, error=result.error)
    shown = {
        "name": result.name,
        "person": result.expected.value,
        "intake": result.verdict.value if result.verdict else "",
    }
    if result.agrees:
        return texts.intake_eval_agree.format(**shown)
    reason = texts.intake_eval_reason.format(reason=result.reason) if result.reason else ""
    return texts.intake_eval_disagree.format(**shown, reason=reason)


def render_duplicate_score(score: DuplicateScore, *, model: str, gateway: str, spend: str) -> str:
    """The run's report: a line for each case, the agreement count, the score of the
    `duplicate` verdict, and what the run spent."""
    texts = MESSAGES.roadmap
    cases = len(score.results)
    lines = [texts.intake_eval_title.format(cases=cases, model=model, gateway=gateway), ""]
    lines += [_result_line(result) for result in score.results]
    lines += ["", texts.intake_eval_agreed.format(agreed=score.agreed, cases=cases)]
    lines.append(
        texts.intake_eval_score.format(
            true=score.true_duplicates,
            said=score.said_duplicate,
            precision=_ratio(score.true_duplicates, score.said_duplicate),
            expected=score.expected_duplicates,
            recall=_ratio(score.true_duplicates, score.expected_duplicates),
            false=score.false_duplicates,
        )
    )
    lines += ["", spend]
    return "\n".join(lines) + "\n"


def render_duplicate_dry_run(cases: Sequence[DuplicateCase], *, gateway: str) -> str:
    """The requests a run makes, making none: one `analysis` call for each case."""
    texts = MESSAGES.roadmap
    lines = [texts.intake_eval_dry_run.format(gateway=gateway), ""]
    lines += [f"- {case.name}" for case in cases]
    lines += ["", texts.intake_eval_dry_run_calls.format(calls=len(cases))]
    return "\n".join(lines) + "\n"


__all__ = [
    "DUPLICATE_CASES",
    "CaseResult",
    "DuplicateCase",
    "DuplicateScore",
    "SameVector",
    "Verdict",
    "checkout_labels",
    "evaluate_duplicates",
    "judge_case",
    "load_cases",
    "render_duplicate_dry_run",
    "render_duplicate_score",
]
