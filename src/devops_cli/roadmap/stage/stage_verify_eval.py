"""The score of the verification pass on the golden set of the stage job (#3153).

For each case the run reads the files that the recorded plan cites from the checkout of the staging
commit, makes the request of the pass (`VerificationInput`) and asks the model for findings. A
finding matches at most one labeled defect of its type, the most serious first, so one finding of
a common type does not cover every defect of that type. The match is by type and not by text. The
recall is the matched defects over the labeled ones. A finding on a `good` plan is a false alarm,
and the score counts those that would return the plan to the planner.

pydantic-evals runs the cases, and its per-case hook (`CaseLifecycle.teardown`) gives each case to
the caller when the case ends, so the caller stores the report after each case and a stop keeps
the cases that ended. A later run reads a stored report (`resumed_outcomes`) and runs only the
cases that it lacks or that failed in it (#4344). pydantic-evals is imported only when a run
starts.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.config.constants import CONST_ROADMAP_VERIFY_RECALL_FLOOR
from devops_cli.dry_run import PlannedRequest
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.clone_git import checkout_at
from devops_cli.roadmap.refine.refine_investigation import task_window
from devops_cli.roadmap.stage.stage import StageClient, openspec_tool
from devops_cli.roadmap.stage.stage_eval_cases import (
    Defect,
    DefectType,
    Severity,
    StageCase,
    Verdict,
    left_out_note,
)
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient, ToolboxModel, review
from devops_cli.roadmap.stage.stage_verify import Finding, VerificationInput, returning

if TYPE_CHECKING:
    from pydantic_evals.reporting import ReportCase, ReportCaseFailure

_DATASET_NAME: Final[str] = "stage_verification"
_OPERATION: Final[str] = "roadmap.eval.stage-verify"
_TASK: Final[str] = "verification"
# The severities from the most serious, and the ones that the serious recall counts.
_BY_SEVERITY: Final[tuple[Severity, ...]] = (
    Severity.BLOCKER,
    Severity.MAJOR,
    Severity.MINOR,
    Severity.NIT,
)
_SERIOUS: Final[frozenset[Severity]] = frozenset({Severity.BLOCKER, Severity.MAJOR})
_NOT_RUN: Final[str] = "not run"


def matched_defects(defects: Sequence[Defect], findings: Sequence[Finding]) -> tuple[Defect, ...]:
    """The defects that `findings` find: each finding takes the most serious defect of its type
    that no finding took before, and a finding with no such defect finds nothing."""
    pool = sorted(defects, key=lambda defect: _BY_SEVERITY.index(defect.severity))
    found: list[Defect] = []
    for finding in findings:
        hit = next((defect for defect in pool if defect.type is finding.type), None)
        if hit is not None:
            pool.remove(hit)
            found.append(hit)
    return tuple(found)


@dataclass(frozen=True)
class CaseVerification:
    """The output of the pass on one case: the findings, and how many of them would return the
    plan to the planner."""

    findings: tuple[Finding, ...]
    returning: int


@dataclass(frozen=True)
class CaseOutcome:
    """One case in the score. `error` is set, and the counts are zero, for a case whose call
    failed."""

    name: str
    good: bool
    labeled: int
    found: int
    findings: tuple[Finding, ...] = ()
    returning: int = 0
    error: str = ""


@dataclass(frozen=True)
class TypeRecall:
    """The labeled defects of one type, and how many the findings found."""

    type: DefectType
    labeled: int
    found: int

    @property
    def rate(self) -> float | None:
        """The share found, or None when no case has the type."""
        return self.found / self.labeled if self.labeled else None


@dataclass(frozen=True)
class VerifyScore:
    """The score of a run: the recall by type, the recall of the serious defects, the findings on
    the good plans and each case, and the names of the cases that the run left out because they
    hold no commit (#3688)."""

    model: str
    rows: tuple[TypeRecall, ...]
    serious_labeled: int
    serious_found: int
    cases: tuple[CaseOutcome, ...]
    left_out: tuple[str, ...] = ()

    @property
    def labeled(self) -> int:
        """The labeled defects of all cases."""
        return sum(row.labeled for row in self.rows)

    @property
    def found(self) -> int:
        """The labeled defects that a finding found."""
        return sum(row.found for row in self.rows)

    @property
    def recall(self) -> float | None:
        """The share of the labeled defects found, or None when the set has none."""
        return self.found / self.labeled if self.labeled else None

    @property
    def serious_recall(self) -> float | None:
        """The share of the blocker and major defects found, or None when the set has none."""
        return self.serious_found / self.serious_labeled if self.serious_labeled else None

    @property
    def failed(self) -> int:
        """The cases whose call failed."""
        return sum(bool(case.error) for case in self.cases)

    @property
    def good_cases(self) -> int:
        """The good plans that the run verified."""
        return sum(case.good and not case.error for case in self.cases)

    @property
    def good_findings(self) -> int:
        """The findings on the good plans."""
        return sum(len(case.findings) for case in self.cases if case.good)

    @property
    def good_returning(self) -> int:
        """The findings on the good plans that would return the plan to the planner."""
        return sum(case.returning for case in self.cases if case.good)


def verify_score(
    model: str,
    cases: Sequence[StageCase],
    outcomes: Iterable[CaseOutcome],
    *,
    left_out: tuple[str, ...] = (),
) -> VerifyScore:
    """The score of `cases` from the outcome of each case: the defects that the findings of each
    case find, by type and in all. A case with no outcome counts as a case that did not run."""
    by_name = {outcome.name: outcome for outcome in outcomes}
    ended = tuple(by_name.get(case.name) or _not_run(case) for case in cases)
    defects = [defect for case in cases for defect in case.defects]
    found = [
        defect
        for case, outcome in zip(cases, ended, strict=True)
        for defect in matched_defects(case.defects, outcome.findings)
    ]
    rows = tuple(
        TypeRecall(kind, sum(d.type is kind for d in defects), sum(d.type is kind for d in found))
        for kind in DefectType
    )
    return VerifyScore(
        model,
        rows,
        sum(d.severity in _SERIOUS for d in defects),
        sum(d.severity in _SERIOUS for d in found),
        ended,
        left_out,
    )


def _not_run(case: StageCase, error: str = "") -> CaseOutcome:
    """The outcome of a case whose call failed with `error`, or that did not run."""
    return CaseOutcome(
        case.name, case.verdict is Verdict.GOOD, len(case.defects), 0, error=error or _NOT_RUN
    )


def pending_cases(cases: Sequence[StageCase], done: Iterable[CaseOutcome]) -> list[StageCase]:
    """The cases that a run with the stored outcomes `done` runs: each case with no outcome, or
    whose call failed."""
    kept = {outcome.name for outcome in done if not outcome.error}
    return [case for case in cases if case.name not in kept]


def evaluate_cases(
    model: str,
    cases: Sequence[StageCase],
    client: StageClient,
    repository: Path,
    *,
    toolbox: ToolboxModel,
    left_out: tuple[str, ...] = (),
    done: Iterable[CaseOutcome] = (),
    store: Callable[[VerifyScore], object] | None = None,
) -> VerifyScore:
    """Run the pass on each case, one at a time, and score it. A call that fails ends its case
    as failed. Rejected credentials stop the run. The pass of each case is an agent of the `toolbox`
    model with the read tools of the job on the checkout of the case, so the score measures the
    pass that the job runs (#3039). `client` answers a call that is not for the pass. `left_out`
    names the cases that the caller did not pass, as they hold no commit; the score reports them.

    `done` holds the outcomes of a stored report: the run keeps each one whose call did not fail
    and runs only the other cases. `store` gets the score of the cases that ended, at the start
    and again when each case ends, so a stop of the run keeps them (#4344). A case that ran after
    the credentials were rejected is not stored."""
    ended = {outcome.name: outcome for outcome in done if not outcome.error}

    def keep(outcome: CaseOutcome | None = None) -> None:
        if outcome is not None:
            ended[outcome.name] = outcome
        if store is not None:
            closed = [case for case in cases if case.name in ended]
            store(verify_score(model, closed, ended.values(), left_out=left_out))

    keep()
    with openspec_tool() as tool:
        _run_cases(pending_cases(cases, ended.values()), client, repository, toolbox, tool, keep)
    return verify_score(model, cases, ended.values(), left_out=left_out)


def _run_cases(
    cases: Sequence[StageCase],
    client: StageClient,
    repository: Path,
    toolbox: ToolboxModel,
    tool: OpenSpecTool | None,
    ended: Callable[[CaseOutcome], None],
) -> None:
    """Run the pass on `cases`, with `tool` for the specs that `read_spec` reads, and give the
    outcome of each case to `ended` when the case ends."""
    from pydantic_evals import Case, Dataset
    from pydantic_evals.lifecycle import CaseLifecycle

    by_name = {case.name: case for case in cases}
    rejected: list[AICredentialsError] = []

    def task(name: str) -> CaseVerification:
        if rejected:
            raise rejected[0]
        case = by_name[name]
        try:
            with checkout_at(repository, case.base_commit, operation=_OPERATION) as source:
                given = VerificationInput.of(
                    number=case.issue,
                    title=case.title,
                    body=case.issue_body,
                    plan=case.plan,
                    source=source,
                    window=task_window(_TASK),
                )
                reviewer = ToolboxClient(
                    toolbox.model,
                    client,
                    source,
                    case.base_commit,
                    window=task_window(_TASK),
                    openspec=tool,
                )
                findings, read = review(reviewer, given)
        except AICredentialsError as exc:
            rejected.append(exc)
            raise
        return CaseVerification(tuple(findings), len(returning(findings, read)))

    class Store(CaseLifecycle[str, CaseVerification, StageCase]):
        """Gives the outcome of the case to `ended` when the case ends. A stop of the run in
        the case gives no result, and the case is not stored."""

        async def teardown(
            self,
            result: ReportCase[str, CaseVerification, StageCase]
            | ReportCaseFailure[str, CaseVerification, StageCase]
            | None,
        ) -> None:
            if result is not None and not rejected:
                ended(_outcome(by_name[result.name], result))

    dataset: Dataset[str, CaseVerification, StageCase] = Dataset(
        name=_DATASET_NAME,
        cases=[Case(name=case.name, inputs=case.name, metadata=case) for case in cases],
    )
    dataset.evaluate_sync(task, max_concurrency=1, progress=False, lifecycle=Store)
    if rejected:
        raise rejected[0]


def _outcome(
    case: StageCase,
    result: ReportCase[str, CaseVerification, StageCase]
    | ReportCaseFailure[str, CaseVerification, StageCase],
) -> CaseOutcome:
    """The outcome of `case` from the result of its run."""
    from pydantic_evals.reporting import ReportCaseFailure

    if isinstance(result, ReportCaseFailure):
        return _not_run(case, result.error_message)
    output = result.output
    return CaseOutcome(
        case.name,
        case.verdict is Verdict.GOOD,
        len(case.defects),
        len(matched_defects(case.defects, output.findings)),
        output.findings,
        output.returning,
    )


class _StoredReport(BaseModel):
    """The part of a report of `verify_json` that a resumed run reads."""

    model_config = ConfigDict(extra="ignore")

    model: str
    cases: tuple[CaseOutcome, ...]


def resumed_outcomes(path: Path, model: str) -> tuple[CaseOutcome, ...]:
    """The case outcomes of the report in `path`, which `verify_json` wrote for `model`. A file
    that is not such a report, or a report of another model, raises `ConfigurationError`, as the
    scores of two models must not mix."""
    try:
        stored = _StoredReport.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise ConfigurationError(
            MESSAGES.roadmap.verify_eval_resume_unread.format(path=path),
            details={"path": str(path), "errors": exc.error_count()},
        ) from exc
    if stored.model != model:
        raise ConfigurationError(
            MESSAGES.roadmap.verify_eval_resume_model.format(
                path=path, stored=stored.model, model=model
            ),
            details={"path": str(path), "stored": stored.model, "model": model},
        )
    return stored.cases


def _percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else MESSAGES.roadmap.stage_eval_no_value


def _floor_line(score: VerifyScore) -> str:
    """Whether the recall of the blocker and major defects reaches the floor (#3039)."""
    texts = MESSAGES.roadmap
    floor = _percent(CONST_ROADMAP_VERIFY_RECALL_FLOOR)
    if score.serious_recall is None:
        return texts.verify_eval_floor_unscored.format(floor=floor)
    template = (
        texts.verify_eval_floor_met
        if score.serious_recall >= CONST_ROADMAP_VERIFY_RECALL_FLOOR
        else texts.verify_eval_floor_missed
    )
    return template.format(floor=floor, rate=_percent(score.serious_recall))


def render_verify(score: VerifyScore, *, gateway: str) -> str:
    """The score as text: the recall by type, the two totals, the findings on the good plans and
    how the cases ended."""
    texts = MESSAGES.roadmap
    lines = [
        texts.verify_eval_title.format(cases=len(score.cases), model=score.model, gateway=gateway),
        "",
        texts.verify_eval_header,
        *(
            texts.verify_eval_row.format(
                type=row.type.value, labeled=row.labeled, found=row.found, rate=_percent(row.rate)
            )
            for row in score.rows
        ),
        "",
        texts.verify_eval_recall.format(
            found=score.found, labeled=score.labeled, rate=_percent(score.recall)
        ),
        texts.verify_eval_serious.format(
            found=score.serious_found,
            labeled=score.serious_labeled,
            rate=_percent(score.serious_recall),
        ),
        _floor_line(score),
        texts.verify_eval_good.format(
            findings=score.good_findings, cases=score.good_cases, returning=score.good_returning
        ),
        texts.verify_eval_ended.format(
            ended=f"verified {len(score.cases) - score.failed}, failed {score.failed}"
        ),
    ]
    if score.left_out:
        lines.append(left_out_note(score.left_out))
    return "\n".join(lines) + "\n"


def verify_json(score: VerifyScore, *, gateway: str, taken: str) -> str:
    """The score as JSON, for the file under `.data/` and for `--json`. Each case lists its
    findings, so a person can read what the model said."""
    data: dict[str, Any] = {
        "model": score.model,
        "gateway": gateway,
        "taken": taken,
        "labeled": score.labeled,
        "found": score.found,
        "recall": score.recall,
        "serious_labeled": score.serious_labeled,
        "serious_found": score.serious_found,
        "serious_recall": score.serious_recall,
        "good_cases": score.good_cases,
        "good_findings": score.good_findings,
        "good_returning": score.good_returning,
        "failed": score.failed,
        "left_out": list(score.left_out),
        "rows": [
            {"type": row.type.value, "labeled": row.labeled, "found": row.found, "rate": row.rate}
            for row in score.rows
        ],
        "cases": [
            {
                "name": case.name,
                "good": case.good,
                "labeled": case.labeled,
                "found": case.found,
                "returning": case.returning,
                "error": case.error,
                "findings": [finding.model_dump(mode="json") for finding in case.findings],
            }
            for case in score.cases
        ],
    }
    return json.dumps(data, indent=2) + "\n"


def planned_verify_calls(cases: Sequence[StageCase], gateway: str) -> list[PlannedRequest]:
    """The model calls of a run, making none: one agent run for each case."""
    texts = MESSAGES.roadmap
    return [
        PlannedRequest(
            method="POST",
            target=f"{gateway}/chat/completions",
            stdin=texts.verify_eval_dry_run_case.format(name=case.name),
            repeat=texts.verify_eval_dry_run_repeat,
        )
        for case in cases
    ]
