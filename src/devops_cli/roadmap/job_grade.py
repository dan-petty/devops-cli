"""The job grade of a roadmap workflow, from the counts of its attempts (#5165).

The owner gives each agentic workflow a grade from its measured success, with one action for each
grade (owner request 2026-11-12). `GRADE_POLICIES` holds the grade table once: the floor of each
grade, its name, its action and whether efficiency work starts at it. `devops docs generate`
writes the table into `docs/roadmap/job-success.md`, between the markers of `sync_grade_table`.

The ratio `p` is the successes over the attempts that no infrastructure cut ended, because the
action of a grade is for the workflow. The grade is `100` when every such attempt is a first pass,
else the floor of `p`, and `too few` under `MIN_ATTEMPTS` attempts. The Wilson 95% interval of `p`
(statsmodels) gives the grades that the evidence spans. A job grade is not the band of a decision
point (ADR 0020).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class JobGrade(StrEnum):
    """The grade of a workflow: a floor of its success ratio, `100`, or `too few`."""

    CHECK_MEASURE = "100"
    WELL = "90"
    ACCEPTABLE = "80"
    DEGRADED = "70"
    INEFFECTIVE = "60"
    COIN_FLIP = "<60"
    TOO_FEW = "too few"


class GradeWindow(StrEnum):
    """A window of the grade report. 7 days gives the grade, 24 hours the trend, and 6 hours
    finds a broken workflow."""

    H6 = "6h"
    H24 = "24h"
    D7 = "7d"


class EfficiencyWork(StrEnum):
    """What the report does with the tokens and the seconds of a workflow at its grade: work on
    them from grade 80 up, else only show them (owner direction 2026-11-12)."""

    OPTIMIZE = "optimize"
    REPORT_ONLY = "report only"


@dataclass(frozen=True)
class GradePolicy:
    """One row of the grade table. `floor` is the least ratio of a grade of the floor rule, and
    None for `100` and `too few`, which another rule gives."""

    grade: JobGrade
    floor: float | None
    rule: str
    name: str
    action: str
    efficiency: EfficiencyWork


# The attempts with no infrastructure cut that a grade needs in its window.
MIN_ATTEMPTS: Final = 30
# The Wilson interval is at 95% confidence.
_ALPHA: Final = 0.05
# Ratios and bounds are rounded to 4 decimals in the report.
_DECIMALS: Final = 4

# The owner table of 2026-11-12, in ASD-STE100. The floor grades come in the order of their
# floors, highest first, so the first floor that a ratio reaches is its grade.
GRADE_POLICIES: Final[tuple[GradePolicy, ...]] = (
    GradePolicy(
        JobGrade.CHECK_MEASURE,
        None,
        "every attempt is a first pass",
        "Check the measure",
        "Look for measure defects or bugs. Look for ways to tighten gates, restrictions and "
        "correction suggestions.",
        EfficiencyWork.OPTIMIZE,
    ),
    GradePolicy(
        JobGrade.WELL,
        0.90,
        "p ≥ 0.90",
        "Well performing",
        "Apply routine updates and refinements. Give priority to new features.",
        EfficiencyWork.OPTIMIZE,
    ),
    GradePolicy(
        JobGrade.ACCEPTABLE,
        0.80,
        "0.80 ≤ p < 0.90",
        "Acceptable",
        "Find the leading failure modes. Give priority to fixes and fixer jobs that increase "
        "success.",
        EfficiencyWork.OPTIMIZE,
    ),
    GradePolicy(
        JobGrade.DEGRADED,
        0.70,
        "0.70 ≤ p < 0.80",
        "Degraded",
        "Find the leading causes of failure, with high priority.",
        EfficiencyWork.REPORT_ONLY,
    ),
    GradePolicy(
        JobGrade.INEFFECTIVE,
        0.60,
        "0.60 ≤ p < 0.70",
        "Ineffective",
        "Look for implementation alternatives, or serious defects that a fix can correct.",
        EfficiencyWork.REPORT_ONLY,
    ),
    GradePolicy(
        JobGrade.COIN_FLIP,
        0.0,
        "p < 0.60",
        "Coin flip",
        "Re-architect the workflow.",
        EfficiencyWork.REPORT_ONLY,
    ),
    GradePolicy(
        JobGrade.TOO_FEW,
        None,
        f"fewer than {MIN_ATTEMPTS} attempts",
        "Not graded",
        "Show p and the interval. Give no grade.",
        EfficiencyWork.REPORT_ONLY,
    ),
)
_POLICY_OF: Final = {policy.grade: policy for policy in GRADE_POLICIES}
_FLOORS: Final = tuple(policy for policy in GRADE_POLICIES if policy.floor is not None)

GRADE_TABLE_START: Final = "<!-- JOB_GRADES_START -->"
GRADE_TABLE_END: Final = "<!-- JOB_GRADES_END -->"
_GRADE_TABLE_BLOCK: Final = re.compile(
    rf"{re.escape(GRADE_TABLE_START)}.*?{re.escape(GRADE_TABLE_END)}", re.DOTALL
)


class GradeMeasure(BaseModel):
    """The ratio, the interval and the grades of the attempts of one workflow in one window."""

    model_config = ConfigDict(frozen=True)

    attempts: int = Field(description="Attempts that no infrastructure cut ended")
    successes: int = Field(description="Those attempts with the intended result")
    first_pass: int | None = Field(
        description="Successes with no fix round; None when the line has no counts for the rule"
    )
    ratio: float | None = Field(description="p: successes / attempts; None with no attempt")
    lower: float | None = Field(description="The Wilson 95% lower bound of p")
    upper: float | None = Field(description="The Wilson 95% upper bound of p")
    point_grade: JobGrade | None = Field(
        description="The grade of p at any count of attempts; None with no attempt"
    )
    grade: JobGrade = Field(description="The point grade, or `too few` under the least attempts")
    range_low: JobGrade | None = Field(description="The grade of the lower bound")
    range_high: JobGrade | None = Field(description="The grade of the upper bound")


def grade_policy(grade: JobGrade) -> GradePolicy:
    """The row of the grade table for `grade`."""
    return _POLICY_OF[grade]


def floor_grade(ratio: float) -> JobGrade:
    """The grade of the highest floor that `ratio` reaches; `<60` for a bound under 0 that the
    arithmetic of the interval can give."""
    return next(
        (policy.grade for policy in _FLOORS if policy.floor is not None and ratio >= policy.floor),
        JobGrade.COIN_FLIP,
    )


def wilson_interval(successes: int, attempts: int) -> tuple[float, float] | None:
    """The Wilson 95% interval of `successes / attempts`, or None with no attempt."""
    if attempts == 0:
        return None
    from statsmodels.stats.proportion import proportion_confint

    lower, upper = proportion_confint(successes, attempts, alpha=_ALPHA, method="wilson")
    return float(lower), float(upper)


def share(part: int, whole: int) -> float | None:
    """`part / whole` rounded for the report, or None when `whole` is 0."""
    return round(part / whole, _DECIMALS) if whole else None


def _point_grade(attempts: int, successes: int, first_pass: int | None) -> JobGrade | None:
    """`100` when every attempt is a first pass, else the floor of the ratio; None with no
    attempt."""
    if attempts == 0:
        return None
    if first_pass == attempts:
        return JobGrade.CHECK_MEASURE
    return floor_grade(successes / attempts)


def measure_grade(*, attempts: int, successes: int, first_pass: int | None) -> GradeMeasure:
    """The ratio, the interval, the point grade, the grade and the range of one workflow."""
    interval = wilson_interval(successes, attempts)
    point = _point_grade(attempts, successes, first_pass)
    return GradeMeasure(
        attempts=attempts,
        successes=successes,
        first_pass=first_pass,
        ratio=share(successes, attempts),
        lower=round(interval[0], _DECIMALS) if interval else None,
        upper=round(interval[1], _DECIMALS) if interval else None,
        point_grade=point,
        grade=point if point is not None and attempts >= MIN_ATTEMPTS else JobGrade.TOO_FEW,
        range_low=floor_grade(interval[0]) if interval else None,
        range_high=floor_grade(interval[1]) if interval else None,
    )


def render_grade_table() -> str:
    """The grade table as Markdown, for `docs/roadmap/job-success.md`."""
    lines = [
        "| Grade | Rule | Name | Action | Efficiency work |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    lines += [
        f"| `{policy.grade}` | {policy.rule} | {policy.name} | {policy.action} | "
        f"{policy.efficiency} |"
        for policy in GRADE_POLICIES
    ]
    return "\n".join(lines)


def sync_grade_table(page: str) -> str | None:
    """`page` with the grade table between its markers, or None when it has no markers."""
    if not _GRADE_TABLE_BLOCK.search(page):
        return None
    block = f"{GRADE_TABLE_START}\n\n{render_grade_table()}\n\n{GRADE_TABLE_END}"
    return _GRADE_TABLE_BLOCK.sub(lambda _match: block, page)


__all__ = [
    "GRADE_POLICIES",
    "GRADE_TABLE_END",
    "GRADE_TABLE_START",
    "MIN_ATTEMPTS",
    "EfficiencyWork",
    "GradeMeasure",
    "GradePolicy",
    "GradeWindow",
    "JobGrade",
    "floor_grade",
    "grade_policy",
    "measure_grade",
    "render_grade_table",
    "share",
    "sync_grade_table",
    "wilson_interval",
]
