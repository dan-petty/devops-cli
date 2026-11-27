"""The report of the drift check: `devops repos onboard --all --plan` over `service.repos` (#6783).

The nightly Job `repos-drift` runs the check (ADR 0035). For each repository it counts the rows off
the baseline and the rows that the check could not read, and it sets the gauge
`devops_cli_repos_drift_rows` with one series for each count, zero included, so a clean run ends
the alerts of the rule group `repos-drift`. A row that is not readable is its own state: it is no
drift, and it is not clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from devops_cli.github.onboard.model import OnboardReport, RowState
from devops_cli.github.repo_ref import RepoRef
from devops_cli.telemetry.instruments import REPOS_DRIFT_ROWS, bounded_label, emit

# The states of a plan row that leave the repository off its baseline and are no failed read: the
# command exits 1 on each of them (`OnboardReport.failing`).
_DRIFT_STATES: Final[frozenset[RowState]] = frozenset(
    {
        RowState.PENDING,
        RowState.FAILED,
        RowState.WAITING,
        RowState.MISSING,
        RowState.INVALID,
    }
)


class DriftState(StrEnum):
    """The state of one repository in the drift check. Each value is also a label value of the
    gauge, except `clean`, which is both counts at zero."""

    DRIFT = "drift"
    NOT_READABLE = "not_readable"
    CLEAN = "clean"


@dataclass(frozen=True)
class DriftCounts:
    """The rows of one plan that are off the baseline, and the rows that the plan could not read."""

    repo: str
    drift: int
    not_readable: int

    @property
    def state(self) -> DriftState:
        """`drift` when a row is off the baseline, else `not_readable` when a row could not be
        read, else `clean`."""
        if self.drift:
            return DriftState.DRIFT
        if self.not_readable:
            return DriftState.NOT_READABLE
        return DriftState.CLEAN


def drift_counts(report: OnboardReport) -> DriftCounts:
    """The counts of the rows of `report` that count: a row that informs only never does."""
    rows = [row for row in report.rows if not row.informs_only]
    return DriftCounts(
        repo=report.repo,
        drift=sum(row.state in _DRIFT_STATES for row in rows),
        not_readable=sum(row.state is RowState.NOT_READABLE for row in rows),
    )


def record_drift(counts: DriftCounts) -> None:
    """Set both series of the repository. The label `repo` holds the key of the repository, which
    `--all` takes from `service.repos` (rule TM3 of docs/SERVICE_PATTERNS.md)."""
    repo = bounded_label(RepoRef(counts.repo).key)
    for state, value in (
        (DriftState.DRIFT, counts.drift),
        (DriftState.NOT_READABLE, counts.not_readable),
    ):
        emit(REPOS_DRIFT_ROWS, value, {"repo": repo, "state": state.value})


__all__ = ["DriftCounts", "DriftState", "drift_counts", "record_drift"]
