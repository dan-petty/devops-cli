"""Whether a CI job stays inside its time budget, read from its last runs on a branch (#2699).

AGENTS.md rule 5 makes a check that averages more than 5 minutes a P0 bug, and the owner allows
1 minute more for the variation of the runners (2026-10-23). A pull request cannot show the mean:
its own run is one sample. The check reads the last runs of the job on the branch from GitHub's
Actions API instead, and passes only when it read all that it asked for and their mean is inside
the limit. The time in the queue is reported, but the limit does not apply to it (#4634). When the
mean is over the limit, `raise_alarm` comments on the open alarm issue of the check, or files one
with the priority P0, so one breach has one issue (#5247).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient, JobRunTime

# The labels of the alarm issue: a mean over the limit is a P0 bug of CI (owner, 2026-10-23).
# The issue holds a Priority, so intake does not place it. It gets the Status New that intake
# gives each new item, because refine reads only the items with the Status New or Ready.
_ALARM_LABELS: Final[tuple[str, ...]] = (
    "type/bug",
    "scope/ci",
    "status/new",
    "priority/p0-critical",
)
# The word that the issue search finds in the body of an alarm issue, inside `alarm_marker`.
ALARM_MARKER: Final[str] = "devops-ci-job-time"
_ALARM_TITLE: Final[str] = "fix(ci): {job} averages {mean:.0f} s, over the {limit:.0f} s limit"


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
    def mean_queue_seconds(self) -> float:
        """The mean time the jobs of the runs read waited in the queue; 0 when none was read. The
        limit does not apply to it (#4634)."""
        return sum(run.queue_seconds for run in self.runs) / len(self.runs) if self.runs else 0.0

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


@dataclass(frozen=True)
class Alarm:
    """The alarm issue of a check: its number, and whether this run filed it or commented on it."""

    number: int
    filed: bool


def alarm_marker(job: str, *, workflow: str, branch: str) -> str:
    """The line in the body of the alarm issue of `job` of `workflow` on `branch`, which no
    reader sees and which tells the issue of one check from the issue of another."""
    return f"<!-- {ALARM_MARKER}: {job} of {workflow} on {branch} -->"


def alarm_text(report: JobTimeReport, repo: str, *, workflow: str, branch: str) -> str:
    """The text of the alarm issue or of its comment: the mean, the limit and each run read."""
    rows = "".join(
        f"| [{run.run_id}](https://github.com/{repo}/actions/runs/{run.run_id}) "
        f"| {run.seconds:.0f} | {run.queue_seconds:.0f} |\n"
        for run in report.runs
    )
    return (
        f"`devops ci job-time` found that the last {report.wanted} runs of `{report.job}` of "
        f"`{workflow}` on `{branch}` took {report.mean_seconds:.0f} s on average. The limit is "
        f"{report.limit_seconds:.0f} s. A mean over the limit is a P0 bug (AGENTS.md rule 5). "
        "Find the change that made the check slow, and fix it or revert it (docs/TESTING.md, "
        "Run time).\n\n"
        f"The jobs also waited {report.mean_queue_seconds:.0f} s on average for a runner. The "
        "limit does not count this time.\n\n"
        "| Run | Seconds | Queue seconds |\n| ---: | ---: | ---: |\n"
        f"{rows}"
    )


def raise_alarm(
    client: GitHubClient, repo: str, report: JobTimeReport, *, workflow: str, branch: str
) -> Alarm:
    """Comment on the open alarm issue of the check of `report`, the lowest number when more than
    one is open, or file one with the priority P0 when none is open (#5247).

    The issue search finds the issues whose body holds `ALARM_MARKER`, and only an open issue
    whose body holds the `alarm_marker` of the check counts. So a run while the mean stays over
    the limit comments, and files no second issue, also after a person changed the title or the
    labels. After the issue is closed, the next breach files a new issue.
    """
    marker = alarm_marker(report.job, workflow=workflow, branch=branch)
    text = alarm_text(report, repo, workflow=workflow, branch=branch)
    held = sorted(
        hit.number
        for hit in client.search_issue_bodies(repo, ALARM_MARKER)
        if hit.state == "open" and marker in (hit.body or "")
    )
    if held:
        client.create_issue_comment(repo, held[0], text)
        return Alarm(number=held[0], filed=False)
    title = _ALARM_TITLE.format(
        job=report.job, mean=report.mean_seconds, limit=report.limit_seconds
    )
    number = client.create_issue(
        repo, title=title, body=f"{text}\n{marker}\n", labels=_ALARM_LABELS
    )
    return Alarm(number=number, filed=True)
