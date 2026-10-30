"""Whether a CI job stays inside its time budget, read from its last runs on a branch (#2699).

AGENTS.md rule 5 makes a check that averages more than 5 minutes a P0 bug. A pull request cannot
show that: its own run is one sample. The check reads the last runs of the job on the branch from
GitHub's Actions API instead, and passes only when it read all that it asked for and their mean is
inside the limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient, JobRunTime


@dataclass(frozen=True)
class JobTimeReport:
    """The seconds a job took in its last runs, and the limit its mean must stay inside."""

    job: str
    wanted: int
    limit_seconds: float
    runs: tuple[JobRunTime, ...]

    @property
    def mean_seconds(self) -> float:
        """The mean of the runs read; 0 when none was read."""
        return sum(run.seconds for run in self.runs) / len(self.runs) if self.runs else 0.0

    @property
    def complete(self) -> bool:
        """Whether GitHub gave all the runs that were asked for."""
        return len(self.runs) >= self.wanted

    @property
    def passes(self) -> bool:
        """Whether all the wanted runs were read and their mean is not over the limit."""
        return self.complete and self.mean_seconds <= self.limit_seconds


def check_job_time(
    client: GitHubClient,
    repo: str,
    *,
    workflow: str,
    branch: str,
    job: str,
    wanted: int,
    limit_seconds: float,
) -> JobTimeReport:
    """Read the time of `job` in the last `wanted` completed runs of `workflow` on `branch` of
    `repo` where it ran to an end."""
    runs = client.get_job_run_times(repo, workflow=workflow, branch=branch, job=job, count=wanted)
    return JobTimeReport(job=job, wanted=wanted, limit_seconds=limit_seconds, runs=tuple(runs))
