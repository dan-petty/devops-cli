"""Whether a CI job stays inside its time budget, read from its last runs on a branch (#2699).

AGENTS.md rule 5 makes a check that averages more than 5 minutes a P0 bug, and the owner allows
1 minute more for the variation of the runners (2026-10-23). A pull request cannot show the mean:
its own run is one sample. The check reads the last runs of the job on the branch from GitHub's
Actions API instead, and passes only when it read all that it asked for and their mean is inside
the limit. The time in the queue is reported, but the limit does not apply to it (#4634). When the
mean is over the limit, `raise_alarm` writes the report into the body of the open alarm issue of
the check, or files one with the priority P0, so one breach has one issue (#5247) and the issue
holds the report one time, with no comment (#6199).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import (
    CONST_CI_JOB_TIME_LIMIT_SECONDS,
    CONST_CI_TEST_JOB_NAME,
    CONST_CI_WORKFLOW_FILE,
    CONST_GIT_MAIN_BRANCH,
)
from devops_cli.config.defaults import DEFAULT_CI_JOB_TIME_RUNS

if TYPE_CHECKING:
    from collections.abc import Sequence

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
# The two lines around the report in the body of the alarm issue. A later run replaces the text
# between them, and the text of a person outside them stays (#6199).
_REPORT_START: Final[str] = "<!-- devops ci job-time report: start -->"
_REPORT_END: Final[str] = "<!-- devops ci job-time report: end -->"

_RELEASE_WORKFLOW_FILE: Final[str] = "release.yml"
# The jobs of the two release images of #6522, by the names of the Actions API. release.yml calls
# release-image.yml one time for each image (#6571), and GitHub names each job of a call
# `<caller job> / <called job>`: the caller job is `<Title> Image`, and the called jobs are Build,
# Verify and Attest & Tag. The plan of #6522 names these two images, so their six jobs are the
# checks. The Service Image jobs average inside the limit, and the DevContainer image is not part
# of #6522 (design.md of #6734).
_RELEASE_IMAGE_JOB_NAMES: Final[tuple[str, ...]] = (
    "MCP Server Image / Build",
    "MCP Server Image / Verify",
    "MCP Server Image / Attest & Tag",
    "Runner Image / Build",
    "Runner Image / Verify",
    "Runner Image / Attest & Tag",
)
_RELEASE_IMAGE_RUNS: Final[int] = 10


@dataclass(frozen=True)
class JobTimeCheck:
    """One job whose duration is checked against a limit over its last runs."""

    workflow: str
    branch: str
    job: str
    runs: int
    limit_seconds: float


JOB_TIME_CHECKS: Final[tuple[JobTimeCheck, ...]] = (
    JobTimeCheck(
        workflow=CONST_CI_WORKFLOW_FILE,
        branch=CONST_GIT_MAIN_BRANCH,
        job=CONST_CI_TEST_JOB_NAME,
        runs=DEFAULT_CI_JOB_TIME_RUNS,
        limit_seconds=CONST_CI_JOB_TIME_LIMIT_SECONDS,
    ),
    *(
        JobTimeCheck(
            workflow=_RELEASE_WORKFLOW_FILE,
            branch=CONST_GIT_MAIN_BRANCH,
            job=job_name,
            runs=_RELEASE_IMAGE_RUNS,
            limit_seconds=CONST_CI_JOB_TIME_LIMIT_SECONDS,
        )
        for job_name in _RELEASE_IMAGE_JOB_NAMES
    ),
)


def job_time_checks(
    workflow: str | None = None,
    branch: str | None = None,
    job: str | None = None,
    runs: int | None = None,
    limit_seconds: float | None = None,
) -> tuple[JobTimeCheck, ...]:
    """The checks to run: `JOB_TIME_CHECKS` when no option is given, or one check from the options."""
    if (
        workflow is None
        and branch is None
        and job is None
        and runs is None
        and limit_seconds is None
    ):
        return JOB_TIME_CHECKS
    return (
        JobTimeCheck(
            workflow=workflow or CONST_CI_WORKFLOW_FILE,
            branch=branch or CONST_GIT_MAIN_BRANCH,
            job=job or CONST_CI_TEST_JOB_NAME,
            runs=runs if runs is not None else DEFAULT_CI_JOB_TIME_RUNS,
            limit_seconds=limit_seconds
            if limit_seconds is not None
            else CONST_CI_JOB_TIME_LIMIT_SECONDS,
        ),
    )


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


def job_time_reads(checks: Sequence[JobTimeCheck]) -> tuple[tuple[JobTimeCheck, ...], ...]:
    """The checks of `checks` in groups of one workflow, branch and count, in the order of their
    first check. One read of the runs serves each group (#6734)."""
    groups: dict[tuple[str, str, int], list[JobTimeCheck]] = {}
    for check in checks:
        groups.setdefault((check.workflow, check.branch, check.runs), []).append(check)
    return tuple(tuple(group) for group in groups.values())


def check_job_times(
    client: GitHubClient, repo: str, checks: Sequence[JobTimeCheck]
) -> tuple[JobTimeReport, ...]:
    """The report of each check of `checks`, in their order. The checks of one workflow, branch
    and count share one read, so the jobs of a run are asked for one time (#6734)."""
    reports: dict[JobTimeCheck, JobTimeReport] = {}
    for group in job_time_reads(checks):
        first = group[0]
        times = client.get_run_times_of_jobs(
            repo,
            workflow=first.workflow,
            branch=first.branch,
            jobs=tuple(check.job for check in group),
            count=first.runs,
        )
        for check in group:
            reports[check] = JobTimeReport(
                job=check.job,
                wanted=check.runs,
                limit_seconds=check.limit_seconds,
                runs=tuple(times[check.job]),
            )
    return tuple(reports[check] for check in checks)


@dataclass(frozen=True)
class Alarm:
    """The alarm issue of a check: its number, and whether this run filed it or wrote the report
    into its body."""

    number: int
    filed: bool


def alarm_marker(job: str, *, workflow: str, branch: str) -> str:
    """The line in the body of the alarm issue of `job` of `workflow` on `branch`, which no
    reader sees and which tells the issue of one check from the issue of another."""
    return f"<!-- {ALARM_MARKER}: {job} of {workflow} on {branch} -->"


def alarm_text(report: JobTimeReport, repo: str, *, workflow: str, branch: str) -> str:
    """The report in the body of the alarm issue: the mean, the limit and each run read."""
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


def _with_report(body: str, text: str) -> str:
    """`body` with the report between `_REPORT_START` and `_REPORT_END` replaced by `text`, or
    with the report at its end when it holds none (#6199).

    The report is the last start line and the first end line after it. A person who deletes one
    of the two lines leaves a line with no partner: the next run then adds a new report at the end,
    and no run replaces the text of the person between the two."""
    block = f"{_REPORT_START}\n{text}{_REPORT_END}"
    start = body.rfind(_REPORT_START)
    end = body.find(_REPORT_END, start) if start != -1 else -1
    if end == -1:
        return f"{body.rstrip()}\n\n{block}\n" if body.strip() else f"{block}\n"
    return f"{body[:start]}{block}{body[end + len(_REPORT_END) :]}"


def raise_alarm(
    client: GitHubClient, repo: str, report: JobTimeReport, *, workflow: str, branch: str
) -> Alarm:
    """Write the report into the body of the open alarm issue of the check of `report`, the lowest
    number when more than one is open, or file one with the priority P0 when none is open (#5247).

    The issue search finds the issues whose body holds `ALARM_MARKER`, and only an open issue
    whose body holds the `alarm_marker` of the check counts. So a run while the mean stays over
    the limit files no second issue, also after a person changed the title or the labels. After
    the issue is closed, the next breach files a new issue. The run reads the body as GitHub gives
    it now, replaces only the report in it, and posts no comment: the issue holds the report one
    time (#6199). A body that already holds the same report gets no change.
    """
    marker = alarm_marker(report.job, workflow=workflow, branch=branch)
    text = alarm_text(report, repo, workflow=workflow, branch=branch)
    held = sorted(
        hit.number
        for hit in client.search_issue_bodies(repo, ALARM_MARKER)
        if hit.state == "open" and marker in (hit.body or "")
    )
    if held:
        body = client.get_issue(repo, held[0]).body or ""
        changed = _with_report(body, text)
        if changed != body:
            client.update_issue_body(repo, held[0], changed)
        return Alarm(number=held[0], filed=False)
    title = _ALARM_TITLE.format(
        job=report.job, mean=report.mean_seconds, limit=report.limit_seconds
    )
    number = client.create_issue(
        repo, title=title, body=f"{_with_report('', text)}{marker}\n", labels=_ALARM_LABELS
    )
    return Alarm(number=number, filed=True)
