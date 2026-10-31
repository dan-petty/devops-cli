"""The Service's submission of the implement Job (#2667).

The Service never runs a step: its image holds no dev tool, and the step needs 2 CPU and an hour.
A round of its `implement` row asks the Kubernetes API for the runner Jobs of the repository, in
three moves.

**Report.** An item whose record holds `implement.job` and no `implement.job_state` has a Job
that no round reported. When the Job has ended, the round comments the state and the tail of the
log of its pod on the item, and records `implement.job_state` as `succeeded` or `failed`. A Job
that no longer exists is recorded as `gone`. A Job that leaves its item In Progress, or Ready and
not stopped, is a stop that the runner could not write, such as a pod killed for its memory: the
round sets the item to Ready and records `implement.stopped` as `job`, or the next round would
create the same Job again. A person's comment `implement: retry` clears it, as it clears the stop
of the job.

**Wait.** A Job of the repository that has not ended blocks the round, whether or not an item
records it, and a person's `devops roadmap implement --item` starts such a Job too (#2913). The API
is the lock, so a restart of the Service loses nothing. The lock is best effort: the round lists
the Jobs again just before it creates one, but a Job that starts between that list and the create
is not seen. A hard lock needs an object on the server, such as a Lease.

**Submit.** Else the round plans the Staged and Planned items that the default filter names and
creates one Job for the first of them, from CronJob `devops-cli-runner`, with the item's
arguments and a token for the one repository (`service.github_app.token_repository`). The record
of the item then names the Job.

**Status.** After it reports the Jobs, and again after it creates one, the round sets the Status
label of each item from the record and the plans on the default branch (`status_sync.py`, #2920):
Planned once the plan is merged, and In Progress as soon as the record names a Job. The round reads
the plans once, for the sweep and for the plan. A sweep that fails for an item does not stop the
round: the failures come back in `SubmitResult.status_failed` for the row to raise.
"""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.constants import (
    CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_JOB_LABEL,
    CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES,
    CONST_ROADMAP_IMPLEMENT_JOB_STEP,
    CONST_ROADMAP_IMPLEMENT_LOG_CHARS,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_LIMIT
from devops_cli.config.env import setting_variables
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, job_name, repository_label
from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by, service_claim, service_release
from devops_cli.roadmap.implement import (
    GIT_OPERATION,
    ImplementTarget,
    parse_implement_filters,
    plan_implement,
)
from devops_cli.roadmap.planned import read_planned_changes
from devops_cli.roadmap.stage import StageFailure
from devops_cli.roadmap.status_sync import sync_statuses
from devops_cli.roadmap.store import GitHubState, ImplementRecordKey, Item, ItemField, RoadmapStore
from devops_cli.security.sanitizer import mask_secrets

_GONE = "gone"


@dataclass(frozen=True)
class SubmitResult:
    """What a round did: the Jobs it reported, whether a running Job held it, the Job it created,
    and the item it left because an agent or a person claimed it after the plan (#2910), and the
    items whose Status it could not set."""

    reported: tuple[str, ...] = ()
    waiting: bool = False
    created: str | None = None
    left: int | None = None
    status_failed: tuple[StageFailure, ...] = ()


def _record(item: Item, key: ImplementRecordKey) -> str | None:
    return item.job_record.get(key)


def _unreported(store: RoadmapStore) -> list[tuple[Item, str]]:
    """The open items that record a Job and no state of it, with the Job's name."""
    return [
        (item, name)
        for item in store.items()
        if item.state is GitHubState.OPEN
        and (name := _record(item, ImplementRecordKey.JOB))
        and not _record(item, ImplementRecordKey.JOB_STATE)
    ]


def _settles_as_stop(item: Item) -> bool:
    """Whether an item that a Job ended is a stop that nobody wrote: it is In Progress, or Ready or
    Planned and not stopped. Any other Status, In Review and Done included, is the Job's own
    result. An item that an agent or a person claimed is theirs, and the Job ended its run for that
    claim."""
    if claimed_by(item) is not None:
        return False
    stopped = _record(item, ImplementRecordKey.STOPPED)
    return item.status == CONST_ROADMAP_STATUS_IN_PROGRESS or (
        item.status in {CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED} and not stopped
    )


def _fresh(store: RoadmapStore, number: int) -> Item:
    held = store.item(number)
    if held is None:
        raise LookupError(MESSAGES.roadmap.implement_left_not_item)
    return held


def _comment(name: str, state: str, log: str, *, stopped: bool) -> str:
    texts = MESSAGES.roadmap
    if state == _GONE:
        body = texts.implement_job_report_gone.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, name=name
        )
    else:
        quoted = (
            textwrap.indent(mask_secrets(log).strip()[-CONST_ROADMAP_IMPLEMENT_LOG_CHARS:], "    ")
            or texts.implement_job_report_no_log
        )
        body = texts.implement_job_report.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, name=name, state=state, log=quoted
        )
    return body + (texts.implement_job_report_stopped if stopped else "")


def _log_of(jobs: ClusterJobs, name: str) -> str:
    """The tail of the log of Job `name`, or empty when the API refuses it: a pod that was evicted
    or never started has no log, and the report of the Job must not wait for one."""
    try:
        return jobs.log_tail(name, CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES)
    except ClusterJobError:
        return ""


def _report(
    store: RoadmapStore, jobs: ClusterJobs, item: Item, name: str, ended: ClusterJob | None
) -> None:
    """Comment on the item what became of its Job, record the state, and stop the item when the
    Job left it eligible. The comment comes first, so a write that fails is reported again."""
    state = ended.state.value if ended else _GONE
    log = _log_of(jobs, name) if ended else ""
    stops = _settles_as_stop(item)
    store.comment(item.number, _comment(name, state, log, stopped=stops))
    service_release(store, item.number, {ImplementRecordKey.JOB_STATE: state})
    if stops:
        store.set_field(
            _fresh(store, item.number),
            ItemField.STATUS,
            CONST_ROADMAP_STATUS_READY,
            marks={ImplementRecordKey.STOPPED: CONST_ROADMAP_IMPLEMENT_JOB_STEP},
        )


def _report_ended(
    store: RoadmapStore, jobs: ClusterJobs, held: Mapping[str, ClusterJob]
) -> tuple[str, ...]:
    reported: list[str] = []
    for item, name in _unreported(store):
        job = held.get(name)
        if job is not None and job.state is JobState.RUNNING:
            continue
        _report(store, jobs, item, name, job)
        reported.append(name)
    return tuple(reported)


def _create(
    store: RoadmapStore, jobs: ClusterJobs, repo: str, target: ImplementTarget, label: str
) -> str | None:
    """Claim the item and record the Job on it, then create the Job. The record comes first: a
    record that fails after the create would leave a Job that no item names, and a Job that dies
    early would leave its item eligible for a new Job in every round. A create that fails takes the
    record and the claim back. A round that dies between the two leaves a record of a Job that does
    not exist, which the next round reports as gone and stops the item for. The name of the Job, or
    None, with nothing written, when an agent or a person claimed the item since the plan."""
    number = target.item.number
    name = job_name(template=RUNNER_TEMPLATE)
    marks = {ImplementRecordKey.JOB: name, ImplementRecordKey.JOB_STATE: None}
    if not service_claim(store, number, marks):
        return None
    try:
        jobs.create(
            ["roadmap", "implement", "--repo", repo, "--item", str(number), "--confirm"],
            template=RUNNER_TEMPLATE,
            env={setting_variables()[CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING]: repo},
            labels={CONST_ROADMAP_IMPLEMENT_JOB_LABEL: label},
            name=name,
        )
    except ClusterJobError:
        service_release(store, number, {ImplementRecordKey.JOB: None})
        raise
    return name


def _runs(api: ClusterJobs, label: str) -> bool:
    """Whether a runner Job of the repository with `label` has not ended."""
    jobs = api.list_jobs({CONST_ROADMAP_IMPLEMENT_JOB_LABEL: label})
    return any(job.state is JobState.RUNNING for job in jobs)


def run_implement_round(
    store: RoadmapStore, *, repo: str, source: Path | str, jobs: ClusterJobs | None = None
) -> SubmitResult:
    """One round of the `implement` row: report the Jobs that ended, wait while one runs, else
    create the Job for the first Staged or Planned item that the default filter names.

    Raises ClusterJobError when the Kubernetes API refuses a call or CronJob `devops-cli-runner`
    is missing.
    """
    api = jobs or ClusterJobs()
    label = repository_label(repo)
    held = {job.name: job for job in api.list_jobs({CONST_ROADMAP_IMPLEMENT_JOB_LABEL: label})}
    reported = _report_ended(store, api, held)
    planned = read_planned_changes(Path(source), operation=GIT_OPERATION)
    failed = sync_statuses(store, repo=repo, planned=planned).failed
    if any(job.state is JobState.RUNNING for job in held.values()):
        return SubmitResult(reported=reported, waiting=True, status_failed=failed)
    plan = plan_implement(
        store,
        repo=repo,
        source=source,
        filters=parse_implement_filters(()),
        limit=DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
        planned=planned,
    )
    if not plan.selected:
        return SubmitResult(reported=reported, status_failed=failed)
    if _runs(api, label):
        return SubmitResult(reported=reported, waiting=True, status_failed=failed)
    number = plan.selected[0].item.number
    created = _create(store, api, repo, plan.selected[0], label)
    failed = sync_statuses(store, repo=repo, planned=planned).failed
    return SubmitResult(
        reported=reported,
        created=created,
        left=number if created is None else None,
        status_failed=failed,
    )


__all__ = ["SubmitResult", "run_implement_round"]
