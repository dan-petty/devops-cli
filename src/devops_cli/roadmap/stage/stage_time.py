"""The CI job-time premise of a roadmap item (#4026).

An item can state that a CI job stays under a duration. The stage job reads that limit from the
item body, compares it with the mean of the job's last runs, and returns the item to New when the
premise is false, before it spends a plan. The comparison takes the verdict of `devops ci job-time`:
a mean equal to the limit passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from devops_cli.ci.job_time import JobTimeReport

# The check name in a code span, then a duration under a limit, as the acceptance criteria of an
# item state it: "`Tests & Coverage` average job duration stays under 300 s".
_JOB_TIME_LIMIT: Final[re.Pattern[str]] = re.compile(
    r"`(?P<check>[^`\n]+)`[^.\n]{0,80}?\bunder\s+(?P<limit>\d+)\s*(?:s|seconds?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class JobTimePremise:
    """The check that the item names, and the limit in seconds that its mean must not exceed."""

    check: str
    limit_seconds: float


def job_time_premise(body: str) -> JobTimePremise | None:
    """The first CI duration limit that `body` states, or None."""
    found = _JOB_TIME_LIMIT.search(body)
    if found is None:
        return None
    return JobTimePremise(found.group("check"), float(found.group("limit")))


def job_time_failure(premise: JobTimePremise, report: JobTimeReport) -> str | None:
    """The evidence that the premise is false, or None when the mean is inside the limit."""
    if report.mean_seconds <= premise.limit_seconds:
        return None
    return MESSAGES.roadmap.stage_job_time_premise.format(
        check=premise.check,
        mean=report.mean_seconds,
        runs=len(report.runs),
        limit=premise.limit_seconds,
    )
