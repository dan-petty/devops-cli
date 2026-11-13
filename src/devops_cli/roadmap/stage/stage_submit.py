"""The stage row of the Service: one stage Job for each Ready item (#4559).

The Service plans no item. A round of its `stage` row talks to the Kubernetes API and GitHub, in
four moves, as the `implement` row does (`implement_submit.py`). The Job list is the lock: the
round lists the stage Jobs of every repository by their component label (ADR 0022), so a restart
of the Service loses nothing.

**Recover.** An item whose record holds a check-out (`stage.job`) has a Job that has not checked
in. The round compares the check-out with the Job that the list holds, and checks in for the Job
that ended with no check-in (`stage_job.check_in`). The record is text of the issue, which its
author can edit, so the round acts on a listed Job only when the item label of the Job, which the
Service sets, names the item. The round reads its items before it lists the Jobs, so a Job can
check in between the two: `check_in` reads the item again, and an item that no check-out names now
is no recovery. Recovery runs only when the stage row runs, until the poll of #5524.

- `evicted`: the Job is gone, such as a Job that a person or a drain deleted. The item is due at
  once, and the round records the count of these ends on the body in `stage.evictions`. The
  ends after `CONST_ROADMAP_STAGE_FREE_EVICTIONS` on one body count as `ci_infra` failures.
- `deadline`: the Job failed with `DeadlineExceeded`, or it still runs
  `CONST_ROADMAP_STAGE_JOB_OVERRUN_SECONDS` after the deadline of the check-out, and the round
  deletes it. The class is `timeout` when its pod ran, and `ci_infra` when its pod has no log,
  such as a pod that waited for its image or a node until the deadline.
- `failed`: the Job failed by its pod failure policy or its backoff limit. The class comes from
  the exit code in the message of the condition and the tail of the log of its pod.
- `succeeded`: the Job completed and its check-in was lost. The item is free, with no failure.

An end that fails gets the failure marks and waits for the wait of its class (`RETRY_AFTER`).
Only a class of `SPLIT_CLASSES` counts toward `roadmap.stage.plan_defect_limit`: the end that
reaches the limit returns the item to New and asks refine to split it. An item that holds its
draft is `succeeded`. No pod of the Job writes the record of a recovered item any more, so the
round judges its orphan at any age. The removal of an orphan keeps the failure marks, the count
and `stage.evictions`.

**Clean.** The round removes the staged branches of closed items and the orphans, and writes the
rejections of the items that it does not submit, with the writer of a stage round, before any
create. The selection then reads the heads without the branches of the orphans, so the item of an
orphan gets its Job in the same round.

**Submit.** The selection is the normal one (`read_stage_round`), with each item that a running
stage Job works on left out, up to `roadmap.stage.jobs` less the stage Jobs that run in the
cluster, for every repository: each one holds a model call slot of the one model tier. For each item that
it takes, the round writes the check-out with the claim `owner/service` first, then creates the Job
from CronJob `roadmap-stage`, named `RepoRef.unit_name` of the item and the hash of its body. A
create that gets 409 finds the Job of the same item and body: the check-out names it. A Job of
that name that ended is deleted first, so the item gets its new Job only when its failure wait
allows it. A create that fails takes the check-out and the claim back.

**Status and counts.** The round sets the Status of each item from the record and the plans
(`status_sync.py`), counts the left-out items in `devops_cli_roadmap_stage_total`, and counts each
Job in `devops_cli_service_stage_jobs_total` by `result` and `class`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES,
    CONST_ROADMAP_STAGE_FREE_EVICTIONS,
    CONST_ROADMAP_STAGE_JOB_OVERRUN_SECONDS,
    CONST_SERVICE_METRIC_STAGE_JOBS,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import RoadmapStageError
from devops_cli.exceptions.k8s import ClusterJobError, ClusterJobExistsError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import (
    ITEM_LABEL,
    OWNER_LABEL,
    REPO_LABEL,
    STAGE_TEMPLATE,
    stage_job_env,
    stage_job_labels,
    stage_job_name,
    stage_jobs_selector,
)
from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import service_claim, service_release
from devops_cli.roadmap.failure import FailureClass, FailureEvidence, classify_failure
from devops_cli.roadmap.round_log import log_failed_item
from devops_cli.roadmap.stage.stage import (
    StageFailure,
    StagePlan,
    StageWriter,
    emit_stage_results,
    parse_filters,
    plan_body_hash,
    read_stage_round,
)
from devops_cli.roadmap.stage.stage_job import StageJobEnd, check_in
from devops_cli.roadmap.status_sync import sync_statuses
from devops_cli.roadmap.stores.store import Item, RoadmapStore, StageRecordKey
from devops_cli.telemetry.metrics import GLOBAL_METRICS

logger = logging.getLogger(__name__)

# The reason of the condition Failed of a Job over its `activeDeadlineSeconds`.
_DEADLINE_EXCEEDED: Final[str] = "DeadlineExceeded"
# The message of a pod failure policy rule names the exit code of the container.
_EXIT_CODE: Final = re.compile(r"exit code (\d+)")
_NONE: Final[str] = "none"
_CHECK_OUT: Final[tuple[StageRecordKey, ...]] = (
    StageRecordKey.JOB,
    StageRecordKey.JOB_AT,
    StageRecordKey.JOB_DEADLINE,
)


class Evictions(BaseModel):
    """The record `stage.evictions`: the hash of the body and the count of its evicted Jobs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    body: str
    count: int

    @property
    def record(self) -> str:
        """The value of `stage.evictions`."""
        return self.model_dump_json()


@dataclass(frozen=True)
class Recovered:
    """A Job that ended with no check-in, and the class of the failure that its end counts as."""

    number: int
    job: str
    end: StageJobEnd
    failure: FailureClass | None = None


@dataclass(frozen=True)
class StageSubmitResult:
    """What a round did: the plan of its selection, the Jobs it recovered, created, found by
    409 and deleted, the Jobs that run after the round, and the items whose Status it could not
    set."""

    plan: StagePlan
    recovered: tuple[Recovered, ...] = ()
    created: tuple[str, ...] = ()
    existed: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    running: int = 0
    status_failed: tuple[StageFailure, ...] = ()


def job_name_of(repo: str, item: Item) -> str:
    """The name of the stage Job of `item`: the unit name of the item and the hash of its body,
    so a second create for the same body gets 409."""
    return stage_job_name(RepoRef(repo), item.number, plan_body_hash(item))


def _count(repo: str, result: str, failure: FailureClass | None = None) -> None:
    GLOBAL_METRICS.increment_counter(
        CONST_SERVICE_METRIC_STAGE_JOBS,
        labels={"repo": repo, "result": result, "class": failure.value if failure else _NONE},
    )


def _time(item: Item, key: StageRecordKey) -> datetime | None:
    try:
        return datetime.fromisoformat(item.job_record.get(key) or "")
    except ValueError:
        return None


def _end_of(job: ClusterJob | None, item: Item, now: datetime) -> StageJobEnd | None:
    """The end of the Job of a check-out, or None while it runs inside its deadline."""
    if job is None:
        return StageJobEnd.EVICTED
    if job.state is JobState.SUCCEEDED:
        return StageJobEnd.SUCCEEDED
    if job.state is JobState.FAILED:
        return StageJobEnd.DEADLINE if job.reason == _DEADLINE_EXCEEDED else StageJobEnd.FAILED
    deadline = _time(item, StageRecordKey.JOB_DEADLINE)
    overrun = timedelta(seconds=CONST_ROADMAP_STAGE_JOB_OVERRUN_SECONDS)
    if deadline is not None and now > deadline + overrun:
        return StageJobEnd.DEADLINE
    return None


def _evictions(item: Item) -> Evictions:
    """The evictions of the body of `item` with this one: a record of another body, or no
    record, starts at 1."""
    body = plan_body_hash(item)
    try:
        held = Evictions.model_validate_json(item.job_record.get(StageRecordKey.EVICTIONS) or "")
    except ValueError:
        return Evictions(body=body, count=1)
    return Evictions(body=body, count=held.count + 1 if held.body == body else 1)


def _log_tail(api: ClusterJobs, name: str) -> str:
    """The tail of the log of the pod of Job `name`, or empty when the API refuses it: a pod that
    was evicted or never started has no log."""
    try:
        return api.log_tail(name, CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES)
    except ClusterJobError:
        return ""


def _failure_of(
    api: ClusterJobs, job: ClusterJob | None, end: StageJobEnd, evictions: Evictions
) -> FailureClass | None:
    """The class of the failure that `end` is, or None for an end that is no failure. A
    `deadline` end of a pod that has no log is `ci_infra`: the pod never ran."""
    if end is StageJobEnd.EVICTED:
        free = evictions.count <= CONST_ROADMAP_STAGE_FREE_EVICTIONS
        return None if free else FailureClass.CI_INFRA
    if end is StageJobEnd.DEADLINE:
        ran = job is not None and _log_tail(api, job.name).strip()
        return FailureClass.TIMEOUT if ran else FailureClass.CI_INFRA
    if end is StageJobEnd.FAILED and job is not None:
        code = _EXIT_CODE.search(job.message)
        evidence = FailureEvidence(
            text=_log_tail(api, job.name), exit_status=int(code.group(1)) if code else None
        )
        return classify_failure(evidence)
    return None


def _recover(
    store: RoadmapStore,
    api: ClusterJobs,
    held: Mapping[str, ClusterJob],
    repo: str,
    now: datetime,
) -> tuple[list[Recovered], list[str]]:
    """Check in for each Job of a check-out that ended with no check-in, as the module says. The
    recovered items, and the Jobs that the round deleted. A listed Job whose item label is not the
    item of the check-out is not the Job of that item: the round leaves it and the item alone."""
    recovered: list[Recovered] = []
    deleted: list[str] = []
    for item in store.items():
        name = item.job_record.get(StageRecordKey.JOB)
        if not name:
            continue
        job = held.get(name)
        if job is not None and job.labels.get(ITEM_LABEL) != str(item.number):
            continue
        if (end := _end_of(job, item, now)) is None:
            continue
        evictions = _evictions(item)
        failure = _failure_of(api, job, end, evictions)
        if job is not None and job.state is JobState.RUNNING:
            api.delete_job(name)
            deleted.append(name)
        marks: dict[StageRecordKey, str | None] = {}
        if end is StageJobEnd.EVICTED and failure is None:
            marks[StageRecordKey.EVICTIONS] = evictions.record
        written = check_in(
            store,
            item.number,
            repo=repo,
            job=name,
            result=end.value,
            now=now,
            failure=failure,
            marks=marks,
        )
        if written is None:
            continue
        _count(repo, written.result, written.failure)
        recovered.append(Recovered(item.number, name, StageJobEnd(written.result), written.failure))
    return recovered, deleted


def _of_repo(job: ClusterJob, ref: RepoRef) -> bool:
    """Whether stage Job `job` works on an item of `ref`, by its owner and repository labels."""
    labels = job.labels
    return labels.get(OWNER_LABEL) == ref.owner_label and labels.get(REPO_LABEL) == ref.repo_label


def _busy(running: Iterable[ClusterJob]) -> dict[int, str]:
    """The running stage Job of each item, by the item label of the Job."""
    return {
        int(text): job.name
        for job in running
        if (text := job.labels.get(ITEM_LABEL, "")).isdecimal()
    }


def _submit(
    store: RoadmapStore,
    api: ClusterJobs,
    repo: str,
    item: Item,
    name: str,
    cronjob: dict[str, Any],
    now: datetime,
) -> str | None:
    """Check `item` out for the Job `name`, then create the Job. The check-out comes first: a
    round that dies between the two leaves a check-out of a Job that does not exist, which the
    next round recovers as `evicted`. `created`, `existed` for a create that got 409, or None, with
    nothing written, when an agent or a person claimed the item since the read."""
    ref = RepoRef(repo)
    seconds = int(cronjob["spec"]["jobTemplate"]["spec"]["activeDeadlineSeconds"])
    deadline = (now + timedelta(seconds=seconds)).astimezone(UTC)
    marks = {
        StageRecordKey.JOB: name,
        StageRecordKey.JOB_AT: now.astimezone(UTC).isoformat(),
        StageRecordKey.JOB_DEADLINE: deadline.isoformat(),
    }
    if not service_claim(store, item.number, marks):
        return None
    try:
        api.create(
            ["roadmap", "stage", "--repo", repo, "--job-item", str(item.number), "--confirm"],
            template=STAGE_TEMPLATE,
            env=stage_job_env(ref, name, deadline),
            labels=stage_job_labels(ref, item.number),
            name=name,
            cronjob=cronjob,
        )
    except ClusterJobExistsError:
        return "existed"
    except ClusterJobError:
        service_release(store, item.number, dict.fromkeys(_CHECK_OUT))
        raise
    return "created"


def run_stage_round(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path | str,
    jobs: ClusterJobs | None = None,
    now: datetime | None = None,
) -> StageSubmitResult:
    """One round of the `stage` row, as the module says, in the clone `source` of `repo`.

    Raises ClusterJobError when the Kubernetes API refuses a call or CronJob `roadmap-stage` is
    missing. Raises RoadmapStageError before any request when `repo` is empty: each counter of
    the round has the label `repo`.
    """
    if not repo:
        raise RoadmapStageError(MESSAGES.roadmap.stage_round_no_repo)
    api = jobs or ClusterJobs()
    at = now or datetime.now(UTC)
    ref = RepoRef(repo)
    listed = api.list_jobs(stage_jobs_selector())
    held = {job.name: job for job in listed if _of_repo(job, ref)}
    recovered, deleted = _recover(store, api, held, repo, at)
    running = [
        job for job in held.values() if job.state is JobState.RUNNING and job.name not in deleted
    ]
    elsewhere = sum(1 for job in listed if job.state is JobState.RUNNING and job.name not in held)
    slots = max(load_settings().roadmap.stage.jobs - len(running) - elsewhere, 0)
    freed: Collection[int] = {found.number for found in recovered}
    read = read_stage_round(
        store,
        repo=repo,
        source=Path(source),
        filters=parse_filters(()),
        limit=slots,
        now=at,
        busy=_busy(running),
        freed=freed,
        every_orphan=True,
    )
    writer = StageWriter(store, source, now=at)
    writer.begin(read.plan, {target.item.number for target in read.selected})
    created: list[str] = []
    existed: list[str] = []
    cronjob = api.cronjob(STAGE_TEMPLATE) if read.selected else {}
    for target in read.selected:
        name = job_name_of(repo, target.item)
        old = held.get(name)
        if old is not None and old.state is not JobState.RUNNING and name not in deleted:
            api.delete_job(name)
            deleted.append(name)
        result = _submit(store, api, repo, target.item, name, cronjob, at)
        if result is not None:
            _count(repo, result)
            (created if result == "created" else existed).append(name)
    applied = writer.applied()
    emit_stage_results(read.plan, applied, repo=repo)
    for failure in (*read.plan.failed, *applied.failed):
        log_failed_item(repo, failure.number, failure.step.value, failure.failure_class.value)
    swept = sync_statuses(store, repo=repo, planned=read.planned).failed
    return StageSubmitResult(
        read.plan,
        recovered=tuple(recovered),
        created=tuple(created),
        existed=tuple(existed),
        deleted=tuple(deleted),
        running=elsewhere + len(running) + len(created) + len(existed),
        status_failed=tuple(swept),
    )


__all__ = [
    "Evictions",
    "Recovered",
    "StageSubmitResult",
    "job_name_of",
    "run_stage_round",
]
