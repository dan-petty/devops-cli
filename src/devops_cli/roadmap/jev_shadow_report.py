"""The report of the Jev shadow records of intake (#4395).

`devops roadmap eval jev --from-shadow` reads every issue of the repository. An issue whose job
record holds the mark `intake.jev_shadow` (`ShadowObservation`) was proposed while the setting
`roadmap.intake.jev` was `shadow`. The report joins the mark with the labels the issue holds now,
its final labels, and gives for each field:

- how often Jev and the triage model agree;
- how often each one equals the final label, and how often only one of them does;
- how often Jev equals the final label in each band of its probability, which is the data for
  the cuts of a later step (ADR 0019 rule 4).

For the duplicate it counts the flags of each model against the issues that GitHub shows closed
as a duplicate. The report makes no model request.

The final label is a weak truth. Intake writes the triage label, and a person who sees a wrong
label changes it, but a person who does not look leaves it. So "the triage model is right" counts
every label that stayed, and the columns "only Jev" and "only triage" are the ones to read.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_TYPE_LABEL_PREFIX
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake.intake_jev import JevField
from devops_cli.roadmap.intake.intake_jev_shadow import ShadowAnswer, ShadowObservation
from devops_cli.roadmap.stores.store import (
    GitHubState,
    IntakeRecordKey,
    IssueRecord,
    item_of,
)

LABEL_FIELDS = (JevField.TYPE, JevField.PRIORITY, JevField.VALUE, JevField.EFFORT)
# The bands of the probability of a Jev answer: the lower end is in the band, the upper is not.
BANDS: tuple[tuple[float, float], ...] = ((0.0, 0.6), (0.6, 0.75), (0.75, 0.9), (0.9, 1.01))
_DUPLICATE_REASON = "duplicate"


@dataclass(frozen=True)
class Observed:
    """An issue with a shadow record: the observation, the final labels and whether GitHub shows
    the issue closed as a duplicate."""

    number: int
    observation: ShadowObservation
    final: Mapping[str, str | None]
    closed_duplicate: bool


@dataclass
class FieldStats:
    """The counts of one label field. `records` holds the records with this field. The counts that
    follow it hold only the records whose issue has a final label for the field."""

    records: int = 0
    agree: int = 0
    judged: int = 0
    jev_right: int = 0
    triage_right: int = 0
    only_jev: int = 0
    only_triage: int = 0
    bands: list[list[int]] = field(default_factory=lambda: [[0, 0] for _ in BANDS])


@dataclass
class DuplicateStats:
    """The flags of the duplicate field against the issues closed as a duplicate."""

    records: int = 0
    jev_flags: int = 0
    triage_flags: int = 0
    both_flags: int = 0
    closed: int = 0
    jev_flags_closed: int = 0
    triage_flags_closed: int = 0


@dataclass(frozen=True)
class ShadowReport:
    """The numbers of the report."""

    issues: int
    unreadable: int
    first: datetime | None
    last: datetime | None
    fields: Mapping[str, FieldStats]
    duplicate: DuplicateStats


def _final_labels(issue: IssueRecord) -> dict[str, str | None]:
    item = item_of(issue)
    kind = next(
        (label for label in issue.labels if label.startswith(CONST_ROADMAP_TYPE_LABEL_PREFIX)),
        None,
    )
    return {
        JevField.TYPE: kind,
        JevField.PRIORITY: item.priority,
        JevField.VALUE: item.value,
        JevField.EFFORT: item.effort,
    }


def _closed_duplicate(issue: IssueRecord) -> bool:
    return issue.state is GitHubState.CLOSED and issue.state_reason == _DUPLICATE_REASON


def observed_issues(issues: Iterable[IssueRecord]) -> tuple[list[Observed], int]:
    """The issues that hold a shadow record, oldest first, and the count of marks that cannot be
    read. A pull request has no record."""
    found: list[Observed] = []
    unreadable = 0
    for issue in sorted(issues, key=lambda each: each.number):
        mark = issue.job_record.get(IntakeRecordKey.JEV_SHADOW)
        if issue.pull_request or not mark:
            continue
        try:
            observation = ShadowObservation.from_mark(mark)
        except ValidationError:
            unreadable += 1
            continue
        found.append(
            Observed(issue.number, observation, _final_labels(issue), _closed_duplicate(issue))
        )
    return found, unreadable


def _band(probability: float) -> int:
    return next(i for i, (low, high) in enumerate(BANDS) if low <= probability < high)


def _count_label(stats: FieldStats, answer: ShadowAnswer, final: str | None) -> None:
    stats.records += 1
    stats.agree += answer.agrees
    if final is None:
        return
    jev_right, triage_right = answer.jev == final, answer.triage == final
    stats.judged += 1
    stats.jev_right += jev_right
    stats.triage_right += triage_right
    stats.only_jev += jev_right and not triage_right
    stats.only_triage += triage_right and not jev_right
    band = stats.bands[_band(answer.probability)]
    band[0] += 1
    band[1] += jev_right


def _count_duplicate(stats: DuplicateStats, answer: ShadowAnswer, closed: bool) -> None:
    jev, triage = bool(answer.jev), bool(answer.triage)
    stats.records += 1
    stats.jev_flags += jev
    stats.triage_flags += triage
    stats.both_flags += jev and triage
    stats.closed += closed
    stats.jev_flags_closed += jev and closed
    stats.triage_flags_closed += triage and closed


def report_of(issues: Iterable[IssueRecord]) -> ShadowReport:
    """The report for the shadow records of `issues`."""
    observed, unreadable = observed_issues(issues)
    fields = {name.value: FieldStats() for name in LABEL_FIELDS}
    duplicate = DuplicateStats()
    for each in observed:
        for name in LABEL_FIELDS:
            answer = each.observation.answers.get(name.value)
            if answer is not None:
                _count_label(fields[name.value], answer, each.final[name])
        flag = each.observation.answers.get(JevField.DUPLICATE.value)
        if flag is not None:
            _count_duplicate(duplicate, flag, each.closed_duplicate)
    times = [each.observation.at for each in observed]
    return ShadowReport(
        issues=len(observed),
        unreadable=unreadable,
        first=min(times, default=None),
        last=max(times, default=None),
        fields=fields,
        duplicate=duplicate,
    )


def _ratio(count: int, total: int) -> str:
    return f"{count}/{total}"


def _band_name(low: float, high: float) -> str:
    return MESSAGES.roadmap.jev_shadow_band.format(low=low, high=min(high, 1.0))


def render_report(report: ShadowReport) -> str:
    """The text of the report. With no record, it says so and names how a record starts."""
    texts = MESSAGES.roadmap
    if report.issues == 0:
        return texts.jev_shadow_none.format(unreadable=report.unreadable) + "\n"
    lines = [
        texts.jev_shadow_title.format(
            issues=report.issues,
            unreadable=report.unreadable,
            first=report.first.date() if report.first else "-",
            last=report.last.date() if report.last else "-",
        ),
        texts.jev_shadow_caveat,
        "",
        texts.jev_shadow_fields_title,
    ]
    for name in LABEL_FIELDS:
        stats = report.fields[name.value]
        lines.append(
            texts.jev_shadow_fields_row.format(
                field=name.value,
                records=stats.records,
                agree=_ratio(stats.agree, stats.records),
                jev=_ratio(stats.jev_right, stats.judged),
                triage=_ratio(stats.triage_right, stats.judged),
                only_jev=stats.only_jev,
                only_triage=stats.only_triage,
            )
        )
    lines += ["", texts.jev_shadow_bands_title]
    for name in LABEL_FIELDS:
        cells = " | ".join(
            f"{_band_name(low, high)} {_ratio(right, total)}"
            for (low, high), (total, right) in zip(
                BANDS, report.fields[name.value].bands, strict=True
            )
        )
        lines.append(texts.jev_shadow_bands_row.format(field=name.value, cells=cells))
    dup = report.duplicate
    lines += [
        "",
        texts.jev_shadow_duplicate.format(
            records=dup.records,
            jev=dup.jev_flags,
            triage=dup.triage_flags,
            both=dup.both_flags,
            closed=dup.closed,
            jev_closed=dup.jev_flags_closed,
            triage_closed=dup.triage_flags_closed,
        ),
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "BANDS",
    "DuplicateStats",
    "FieldStats",
    "Observed",
    "ShadowReport",
    "observed_issues",
    "render_report",
    "report_of",
]
