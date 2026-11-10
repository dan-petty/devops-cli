"""The score of the verify screen against the reviewer alone, on the golden set (#4282, ADR 0019).

Each row is a case of the golden set with the probabilities that Jev gave for the questions of the
screen, and what a stored run of the reviewer found there. The cascade runs the reviewer only when
the screen does not give the band *continue*. So a case that the screen clears loses the serious
defects (blocker or major) that the reviewer alone found in it. The score counts:

- the skipped reviews and their share of the reviewed cases;
- the lost serious defects: the ones the reviewer alone found, in the cases the screen cleared;
- the false clears: the cleared cases whose plan has a labelled serious defect, whether or not the
  reviewer found it.

The cuts are fitted on one fixed half of the cases (`split.json` of the golden set) and scored on
the other, and the fit repeats with the halves swapped. The bar of pilot 1 holds when both reports
lose no serious defect and skip at least `CONST_ROADMAP_STAGE_SCREEN_BAR_SKIP` of the reviews.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_JEV_TIMEOUT_SECONDS,
    CONST_ROADMAP_STAGE_JEV_USD_PER_MILLION_INPUT_TOKENS,
    CONST_ROADMAP_STAGE_SCREEN_BAR_SKIP,
)
from devops_cli.core.repo import find_repo_root
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import checkout_at
from devops_cli.roadmap.decision_fit import (
    CutScore,
    FitCase,
    evaluate_cuts,
    fit_cuts,
    fit_shared_cut,
)
from devops_cli.roadmap.decision_step import Cut, Thresholds, decide_all, probabilities_of
from devops_cli.roadmap.refine.refine_investigation import task_window
from devops_cli.roadmap.stage.stage_eval_cases import Severity, StageCase, Verdict
from devops_cli.roadmap.stage.stage_jev_screen import STEP, request_of
from devops_cli.roadmap.stage.stage_verify import Finding, VerificationInput
from devops_cli.roadmap.stage.stage_verify_eval import matched_defects

SPLIT_FILE: Final[str] = "split.json"
_OPERATION: Final[str] = "roadmap.eval.screen"
_TASK: Final[str] = "verification"
_SERIOUS: Final[frozenset[Severity]] = frozenset({Severity.BLOCKER, Severity.MAJOR})

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings


@dataclass(frozen=True)
class ScreenRow:
    """One case: the probabilities of Jev, what the plan is labelled with, and what the reviewer
    alone found. `reviewed` is false for a case that the reviewer run did not cover."""

    name: str
    good: bool
    labelled: int
    labelled_serious: int
    reviewed: bool
    found: int
    serious_found: int
    probabilities: Mapping[str, float]
    input_tokens: int = 0

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "good": self.good,
            "labelled": self.labelled,
            "labelled_serious": self.labelled_serious,
            "reviewed": self.reviewed,
            "found": self.found,
            "serious_found": self.serious_found,
            "probabilities": dict(self.probabilities),
            "input_tokens": self.input_tokens,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> ScreenRow:
        return cls(
            name=data["name"],
            good=data["good"],
            labelled=data["labelled"],
            labelled_serious=data["labelled_serious"],
            reviewed=data["reviewed"],
            found=data["found"],
            serious_found=data["serious_found"],
            probabilities=data["probabilities"],
            input_tokens=data.get("input_tokens", 0),
        )


@dataclass(frozen=True)
class CascadeScore:
    """The cascade on some rows: the reviewed cases, the skipped reviews, the serious defects that
    the reviewer alone found and the cascade lost, and the false clears."""

    reviewed: int
    skipped: int
    lost_cases: int
    alone_serious: int
    lost_serious: int
    false_clears: int
    labelled_bad: int

    @property
    def skip_rate(self) -> float:
        """The share of the reviews that the screen skips."""
        return self.skipped / self.reviewed if self.reviewed else 0.0

    @property
    def false_clear_rate(self) -> float:
        """The share of the plans with a labelled serious defect that the screen clears."""
        return self.false_clears / self.labelled_bad if self.labelled_bad else 0.0

    @property
    def serious_recall(self) -> float:
        """The share of the serious defects of the reviewer alone that the cascade keeps."""
        return 1.0 - self.lost_serious / self.alone_serious if self.alone_serious else 1.0


def fit_cases(rows: Sequence[ScreenRow]) -> list[FitCase]:
    """The cases to fit on: the rows that the reviewer run covers, which must run when the reviewer
    found a serious defect there."""
    return [
        FitCase(row.name, row.probabilities, row.serious_found > 0, row.serious_found)
        for row in rows
        if row.reviewed
    ]


def cascade_score(rows: Sequence[ScreenRow], cuts: Mapping[str, Cut]) -> CascadeScore:
    """The cascade of the screen with `cuts` on `rows`."""
    reviewed = [row for row in rows if row.reviewed]
    floor = evaluate_cuts(fit_cases(reviewed), cuts)
    cleared = _cleared(reviewed, cuts)
    return CascadeScore(
        reviewed=floor.cases,
        skipped=floor.skipped,
        lost_cases=floor.lost,
        alone_serious=sum(row.serious_found for row in reviewed),
        lost_serious=floor.lost_weight,
        false_clears=sum(row.labelled_serious > 0 for row in cleared),
        labelled_bad=sum(row.labelled_serious > 0 for row in reviewed),
    )


def _cleared(rows: Sequence[ScreenRow], cuts: Mapping[str, Cut]) -> list[ScreenRow]:
    return [
        row
        for row in rows
        if all(row.probabilities[name] < cut.continue_below for name, cut in cuts.items())
    ]


@dataclass(frozen=True)
class HalfReport:
    """One direction of the check: the cuts fitted on `fitted_on` and their score on both halves."""

    rule: str
    fitted_on: str
    cuts: Mapping[str, Cut]
    on_fit: CascadeScore
    on_report: CascadeScore

    @property
    def bar_met(self) -> bool:
        """Whether the half that the fit did not see loses no serious defect and skips enough."""
        return (
            self.on_report.lost_serious == 0
            and self.on_report.skip_rate >= CONST_ROADMAP_STAGE_SCREEN_BAR_SKIP
        )


def read_split(directory: Path) -> dict[str, list[str]]:
    """The two halves of the golden set in `split.json` of `directory`."""
    data = json.loads((directory / SPLIT_FILE).read_text(encoding="utf-8"))
    return {"A": list(data["A"]), "B": list(data["B"])}


# The two ways to fit the cuts: one cut for each question, and one cut for all of them. The report
# gives both for the other half, and the data file holds the cuts of `SHIPPED_RULE`.
RULES: Final[Mapping[str, Callable[[Sequence[FitCase]], dict[str, Cut]]]] = {
    "per_question": fit_cuts,
    "shared": fit_shared_cut,
}
SHIPPED_RULE: Final[str] = "shared"


def two_way(rows: Sequence[ScreenRow], split: Mapping[str, Sequence[str]]) -> list[HalfReport]:
    """For each rule, fit on half A and score on B, then fit on B and score on A."""
    by_half = {key: [row for row in rows if row.name in set(names)] for key, names in split.items()}
    reports = []
    for rule, fit in RULES.items():
        for fitted, other in (("A", "B"), ("B", "A")):
            cuts = fit(fit_cases(by_half[fitted]))
            reports.append(
                HalfReport(
                    rule,
                    fitted,
                    cuts,
                    cascade_score(by_half[fitted], cuts),
                    cascade_score(by_half[other], cuts),
                )
            )
    return reports


def oracle_skip(rows: Sequence[ScreenRow]) -> int:
    """The most reviews that any screen can skip with no loss: the reviewed cases in which the
    reviewer alone found no serious defect."""
    return sum(row.reviewed and row.serious_found == 0 for row in rows)


def jev_usd(rows: Sequence[ScreenRow]) -> float:
    """The price of the Jev requests of the rows."""
    tokens = sum(row.input_tokens for row in rows)
    return tokens * CONST_ROADMAP_STAGE_JEV_USD_PER_MILLION_INPUT_TOKENS / 1_000_000


def _line(name: str, score: CascadeScore) -> str:
    return MESSAGES.roadmap.screen_eval_score.format(
        name=name,
        skipped=score.skipped,
        reviewed=score.reviewed,
        skip=f"{score.skip_rate:.0%}",
        lost=score.lost_serious,
        alone=score.alone_serious,
        cases=score.lost_cases,
        clears=score.false_clears,
        bad=score.labelled_bad,
    )


def render_screen(
    rows: Sequence[ScreenRow], reports: Sequence[HalfReport], *, reviewer_usd: float | None
) -> str:
    """The report as text: the two directions of the fit, the bar, the oracle and the cost."""
    texts = MESSAGES.roadmap
    lines = [texts.screen_eval_title.format(cases=len(rows))]
    for report in reports:
        other = "B" if report.fitted_on == "A" else "A"
        lines.append(
            texts.screen_eval_direction.format(
                rule=report.rule, fitted=report.fitted_on, other=other
            )
        )
        lines.append(_line("  fitted half", report.on_fit))
        lines.append(_line("  other half ", report.on_report))
        lines.append(texts.screen_eval_bar.format(met="met" if report.bar_met else "not met"))
    reviewed = sum(row.reviewed for row in rows)
    lines.append(
        texts.screen_eval_oracle.format(
            oracle=oracle_skip(rows),
            reviewed=reviewed,
            share=f"{oracle_skip(rows) / max(reviewed, 1):.0%}",
        )
    )
    per_plan = jev_usd(rows) / max(len(rows), 1)
    lines.append(texts.screen_eval_jev_cost.format(usd=f"{per_plan:.5f}"))
    if reviewer_usd is not None:
        for report in reports:
            skip = report.on_report.skip_rate
            lines.append(
                texts.screen_eval_cost.format(
                    fitted=f"{report.rule}, {report.fitted_on}",
                    alone=f"{reviewer_usd:.4f}",
                    cascade=f"{per_plan + (1 - skip) * reviewer_usd:.4f}",
                )
            )
    return "\n".join(lines) + "\n"


def screen_json(
    rows: Sequence[ScreenRow], reports: Sequence[HalfReport], *, taken: str, jev_model: str
) -> str:
    """The report as JSON, with every row, so a later run can fit again with no request."""
    data = {
        "taken": taken,
        "jev_model": jev_model,
        "bar_skip": CONST_ROADMAP_STAGE_SCREEN_BAR_SKIP,
        "oracle_skip": oracle_skip(rows),
        "rows": [row.as_json() for row in rows],
        "reports": [
            {
                "rule": report.rule,
                "fitted_on": report.fitted_on,
                "cuts": {k: c.model_dump() for k, c in report.cuts.items()},
                "bar_met": report.bar_met,
                "on_fit": report.on_fit.__dict__,
                "on_report": report.on_report.__dict__,
            }
            for report in reports
        ],
    }
    return json.dumps(data, indent=1) + "\n"


def _reviewer_findings(reports: Sequence[Path]) -> dict[str, list[Finding]]:
    """The findings of each case that the stored reports of the reviewer alone verified. A case
    that failed in a report has none. A later report wins over an earlier one."""
    found: dict[str, list[Finding]] = {}
    for path in reports:
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
            if not case["error"]:
                found[case["name"]] = [Finding.model_validate(item) for item in case["findings"]]
    return found


def _given(case: StageCase, repository: Path) -> VerificationInput:
    """The input of the review for `case`: the cited files from the commit that staged the plan.
    A case with no commit has no file."""
    if not case.has_commit:
        return VerificationInput(case.issue, case.title, case.issue_body, case.plan, {})
    with checkout_at(repository, case.base_commit, operation=_OPERATION) as source:
        return VerificationInput.of(
            number=case.issue,
            title=case.title,
            body=case.issue_body,
            plan=case.plan,
            source=source,
            window=task_window(_TASK),
        )


def screen_rows(
    cases: Sequence[StageCase], reviewer: Sequence[Path], *, settings: Settings
) -> list[ScreenRow]:
    """One row for each case: one Jev request about its digest, and what the stored reviewer runs
    found there. A Jev error raises, so a report never holds a case that failed open."""
    found = _reviewer_findings(reviewer)
    repository = find_repo_root()
    requests = [request_of(_given(case, repository), case.tree().files) for case in cases]
    responses = decide_all(
        requests, settings=settings, timeout=CONST_ROADMAP_STAGE_JEV_TIMEOUT_SECONDS
    )
    rows = []
    for case, response in zip(cases, responses, strict=True):
        matched = matched_defects(case.defects, found.get(case.name, []))
        rows.append(
            ScreenRow(
                name=case.name,
                good=case.verdict is Verdict.GOOD,
                labelled=len(case.defects),
                labelled_serious=sum(d.severity in _SERIOUS for d in case.defects),
                reviewed=case.name in found,
                found=len(matched),
                serious_found=sum(d.severity in _SERIOUS for d in matched),
                probabilities=probabilities_of(response),
                input_tokens=response.usage.input_tokens,
            )
        )
    return rows


def rows_from_report(path: Path) -> list[ScreenRow]:
    """The rows of an earlier report of this command, so a fit repeats with no request."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ScreenRow.from_json(item) for item in data["rows"]]


def fitted_cuts(
    rows: Sequence[ScreenRow], reports: Sequence[HalfReport], *, jev_model: str, day: str
) -> str:
    """The text of the data file: the cuts fitted on all the reviewed cases, with the numbers of
    the two-way check that say how far to trust them."""
    cuts = RULES[SHIPPED_RULE](fit_cases(rows))
    full = cascade_score(rows, cuts)
    thresholds = Thresholds(
        step=STEP,
        model=jev_model,
        fitted=day,
        cases=full.reviewed,
        cuts=cuts,
        report={
            "skipped_on_all_cases": full.skipped,
            "lost_serious_on_all_cases": full.lost_serious,
            "oracle_skip": oracle_skip(rows),
            "other_half": {
                f"{report.rule}_fitted_on_{report.fitted_on}": {
                    "skip_rate": round(report.on_report.skip_rate, 4),
                    "lost_serious": report.on_report.lost_serious,
                    "alone_serious": report.on_report.alone_serious,
                    "false_clear_rate": round(report.on_report.false_clear_rate, 4),
                    "bar_met": report.bar_met,
                }
                for report in reports
            },
        },
    )
    return json.dumps(thresholds.model_dump(mode="json"), indent=2) + "\n"


__all__ = [
    "RULES",
    "SHIPPED_RULE",
    "SPLIT_FILE",
    "CascadeScore",
    "CutScore",
    "HalfReport",
    "ScreenRow",
    "cascade_score",
    "fit_cases",
    "fitted_cuts",
    "jev_usd",
    "oracle_skip",
    "read_split",
    "render_screen",
    "rows_from_report",
    "screen_json",
    "screen_rows",
    "two_way",
]
