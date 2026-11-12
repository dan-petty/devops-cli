"""The Service's submission of the implement Job (#2667).

The Service never runs a step: its image holds no dev tool, and the step needs CPU, memory and an
hour. A round of its `implement` row asks the Kubernetes API for the runner Jobs of the repository,
in three moves.

**Report.** An item whose record holds `implement.job` and no `implement.job_state` has a Job
that no round reported. The round reports the Job of each such open item, and of each such closed
item whose Job the cluster still holds, because the pull request of a Job can merge and close its
item before the round (#4703). A closed item is no stop. When the Job has ended, the round
comments the state and the tail of the log of its pod on the item, and records `implement.job_state` as `succeeded` or `failed`. A Job
that no longer exists is recorded as `gone`. A runner writes `implement.result` as the last mark
of its end (#4071); a Job with the result `ready`, `yielded` or `returned` ended on purpose and
causes no stop. A Job with no result that leaves its item In Progress, or Ready and
not stopped, is a stop that the runner could not write, such as a pod killed for its memory: the
round sets the item to Blocked and records `implement.stopped` as `job`, or the next round would
create the same Job again. A clear rule of the Service takes the item out of Blocked
(`stop_clear.py`), as it does for the stop of the job.

**Deadline.** A Job that has not ended gets a deadline that follows its progress: the Service
extends it while the log of the Job changes, and ends a Job whose log stays the same for the stall
time (`implement_deadline.py`, #3063).

**Wait.** A Job of the repository that has not ended blocks the round, whether or not an item
records it, and a person's `devops roadmap implement --item` starts such a Job too (#2913). The API
is the lock, so a restart of the Service loses nothing. The lock is best effort: the round lists
the Jobs again just before it creates one, but a Job that starts between that list and the create
is not seen. A hard lock needs an object on the server, such as a Lease.

**Submit.** Else the round plans the Staged and Planned items that the default filter names and
creates one Job for the first of them, from CronJob `devops-cli-runner`, with the item's
arguments and a token for the one repository (`service.github_app.token_repository`). The record
of the item then names the Job. The Job has the CPU and the memory request of the row of the size
table that fits the number of files in the tasks of the plan, and the memory limit of the setting
`roadmap.implement.max_memory_limit` (`implement_size.py`, #3193).

**Clear.** After the report, the round clears the stop of each item that the Service set Blocked
when a person asked for a retry, when the stop is `job` and a continuation is left (#3721), or when
the digest in the CronJob template differs from the digest of the Job that stopped it
(`stop_clear.py`, #2912). A cleared item is eligible in the same round, so the plan below can take
it. `implement.job_digest` is the digest in the template at the time of the create, recorded with
the Job.

**Failure class** (#3065). Each Job that left a stop is counted once, in the counter
`devops_cli_service_implement_failures_total` by `class` and `repo`, when the round reports it. The
counter `devops_cli_service_implement_jobs_total` counts the same Job once with the `result`
`failed`, whatever the state of the Job: a runner that writes its stop exits 0 (#4703). The runner
records the class of its own stop in `implement.failure`. A Job that left the item without a result
has only its log, so the round classifies that log (`failure.py`), records the class with the stop,
and names the class and the action left in its comment. The runner pod is not scraped, so the Service
counts.

**Needs fix.** The plan leaves out a Staged item while its draft holds the label `plan/needs-fix`
of a plan with an open finding (`implement.py`, #4477). The round returns such an item once for
each draft, for the row to log, and records the draft in `implement.needs_fix`. A round that judges
the item and does not leave it out for the label clears the mark, so a new label is logged again.

**Status.** After it reports the Jobs, and again after it creates one, the round sets the Status
label of each item from the record and the plans on the default branch (`status_sync.py`, #2920):
Planned once the plan is merged, and In Progress as soon as the record names a Job. The round reads
the plans once, for the sweep and for the plan. A sweep that fails for an item does not stop the
round: the failures come back in `SubmitResult.status_failed` for the row to raise.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from devops_cli.config.constants import (
    CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING,
    CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT,
    CONST_ROADMAP_IMPLEMENT_ANNOTATION_STALLED,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_JOB_LABEL,
    CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES,
    CONST_ROADMAP_IMPLEMENT_JOB_STEP,
    CONST_ROADMAP_IMPLEMENT_LOG_CHARS,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
    CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
    CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
    CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
    CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_LIMIT
from devops_cli.config.env import setting_variables
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, image_digest, job_name, repository_label
from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by, service_claim, service_release
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.failure import (
    FailureClass,
    FailureEvidence,
    classify_failure,
    failure_lines,
)
from devops_cli.roadmap.fence import code_fence
from devops_cli.roadmap.implement.consecutive_failures import get_consecutive_failures
from devops_cli.roadmap.implement.implement import (
    GIT_OPERATION,
    ImplementPlan,
    ImplementTarget,
    NeedsFix,
    parse_implement_filters,
    plan_implement,
)
from devops_cli.roadmap.implement.implement_deadline import manage_deadlines
from devops_cli.roadmap.implement.implement_size import RunnerSize, plan_file_count, runner_size
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from devops_cli.roadmap.plan_read import tasks_at
from devops_cli.roadmap.planned import PlannedChanges, read_planned_changes
from devops_cli.roadmap.round_log import log_implement_attempt
from devops_cli.roadmap.stage.stage import StageFailure
from devops_cli.roadmap.status_sync import StatusFacts, derive_status, sync_statuses
from devops_cli.roadmap.stop_clear import clear_stops
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ImplementRecordKey,
    ImplementResult,
    Item,
    ItemField,
    RoadmapStore,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.metrics import GLOBAL_METRICS

_GONE = "gone"
# The results of a run that ended on purpose and is no stop.
_ENDS_WITHOUT_STOP = frozenset(
    {ImplementResult.READY.value, ImplementResult.YIELDED.value, ImplementResult.RETURNED.value}
)
# The exit status of a Job that the Job controller ended for its active deadline (SIGTERM).
_DEADLINE_EXIT_STATUS = 143


@dataclass(frozen=True)
class SubmitResult:
    """What a round did: the Jobs it reported, whether a running Job held it, the Job it created,
    and the item it left because an agent or a person claimed it after the plan (#2910), and the
    items whose Status it could not set, and the items whose stop it cleared (#2912). `effort` and
    `fallback` name the effort pass that selected the item (#3385). `needs_fix` holds the items
    that the round left out for the label `plan/needs-fix` and had not logged yet."""

    reported: tuple[str, ...] = ()
    waiting: bool = False
    created: str | None = None
    left: int | None = None
    status_failed: tuple[StageFailure, ...] = ()
    cleared: tuple[int, ...] = ()
    effort: str = ""
    fallback: bool = False
    needs_fix: tuple[NeedsFix, ...] = ()


def _record(item: Item, key: ImplementRecordKey) -> str | None:
    return item.job_record.get(key)


def _spend_tokens(item: Item) -> int:
    """The input and output tokens in `implement.spend`. A spend that is absent or cannot be read
    holds no tokens."""
    try:
        data = json.loads(_record(item, ImplementRecordKey.SPEND) or "{}")
        if isinstance(data, dict):
            return max(int(data.get("input_tokens", 0)) + int(data.get("output_tokens", 0)), 0)
    except json.JSONDecodeError, ValueError, TypeError:
        pass
    return 0


def _counted_tokens(item: Item) -> int:
    """The tokens of the spend that the token counter holds: `implement.spend_counted`, or none."""
    try:
        return max(int(_record(item, ImplementRecordKey.SPEND_COUNTED) or 0), 0)
    except ValueError:
        return 0


def _unreported(store: RoadmapStore, held: Mapping[str, ClusterJob]) -> list[tuple[Item, str]]:
    """The items that record a Job and no state of it, with the Job's name: each open item, and
    each closed item whose Job the cluster still holds. An item closes before the report when the
    pull request of its Job merges first (#4703). A closed item whose Job is gone is not reported,
    so a closed item of an earlier version is not counted again."""
    return [
        (item, name)
        for item in store.items()
        if (name := _record(item, ImplementRecordKey.JOB))
        and not _record(item, ImplementRecordKey.JOB_STATE)
        and (item.state is GitHubState.OPEN or name in held)
    ]


def _settles_as_stop(item: Item) -> bool:
    """Whether an item that a Job ended is a stop that nobody wrote: it is In Progress, or Ready or
    Planned and not stopped. Any other Status, In Review and Done included, is the Job's own
    result. An item that an agent or a person claimed is theirs, and the Job ended its run for that
    claim. A Job whose runner wrote a result that is no stop (`ready`, `yielded` or `returned`)
    ended its run on purpose, so the Status it left is its own (#4071). A closed item is no stop:
    nothing creates a Job for it again (#4703)."""
    if item.state is not GitHubState.OPEN or claimed_by(item) is not None:
        return False
    if _record(item, ImplementRecordKey.RESULT) in _ENDS_WITHOUT_STOP:
        return False
    stopped = _record(item, ImplementRecordKey.STOPPED)
    return item.status == CONST_ROADMAP_STATUS_IN_PROGRESS or (
        item.status in {CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED} and not stopped
    )


def _fresh(store: RoadmapStore, number: int) -> Item:
    held = store.item(number)
    if held is None:
        raise LookupError(MESSAGES.roadmap.item_left_not_item)
    return held


def _recorded_failure(item: Item) -> FailureClass | None:
    """The failure class that the runner recorded with its stop, or None."""
    try:
        return FailureClass(_record(item, ImplementRecordKey.FAILURE) or "")
    except ValueError:
        return None


def _failure_of(item: Item, log: str, *, stops: bool, stalled: bool) -> FailureClass | None:
    """The class of the failure that a Job left. A stop that the runner wrote has its class on
    record. A Job that left the item without a result has only its log, so the class comes from
    that log (#3065). A Job that the Service ended for a stall went over its deadline, which is
    the exit status 143 of a Job over its active deadline (#3063). A Job that ended with a result
    has no failure."""
    if stops:
        return classify_failure(
            FailureEvidence(text=log, exit_status=_DEADLINE_EXIT_STATUS if stalled else None)
        )
    if _record(item, ImplementRecordKey.STOPPED):
        return _recorded_failure(item)
    return None


def _comment(
    name: str,
    state: str,
    log: str,
    *,
    failure: FailureClass | None,
    stopped: bool,
    digest: str | None,
    stall: str | None = None,
) -> str:
    texts = MESSAGES.roadmap
    shown = texts.implement_job_report_digest.format(digest=digest) if digest else ""
    if state == _GONE:
        body = texts.implement_job_report_gone.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, name=name, digest=shown
        )
    else:
        excerpt = mask_secrets(log).strip()[-CONST_ROADMAP_IMPLEMENT_LOG_CHARS:]
        quoted = (
            texts.implement_job_report_log.format(fence=code_fence(excerpt), log=excerpt)
            if excerpt
            else texts.implement_job_report_no_log
        )
        body = texts.implement_job_report.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
            name=name,
            state=state,
            digest=shown,
            log=quoted,
        )
    if stall:
        body += texts.implement_job_report_stalled.format(seconds=stall)
    if not stopped or failure is None:
        return body
    return body + texts.implement_job_report_stopped.format(failure=failure_lines(failure))


def _log_of(jobs: ClusterJobs, name: str) -> str:
    """The tail of the log of Job `name`, or empty when the API refuses it: a pod that was evicted
    or never started has no log, and the report of the Job must not wait for one."""
    try:
        return jobs.log_tail(name, CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES)
    except ClusterJobError:
        return ""


def _report(
    store: RoadmapStore,
    jobs: ClusterJobs,
    repo: str,
    item: Item,
    name: str,
    ended: ClusterJob | None,
) -> None:
    """Comment on the item what became of its Job, record the state, and stop the item when the
    Job left it eligible. The comment comes first, so a write that fails is reported again. The
    item is read again after the log, which is a request to the cluster: the runner can write its
    stop in that time, and a stop that it wrote keeps its class (#3476). This narrows the race and
    does not close it: a stop that the runner writes after this read can still be overwritten."""
    state = ended.state.value if ended else _GONE
    log = _log_of(jobs, name) if ended else ""
    item = _fresh(store, item.number)
    stops = _settles_as_stop(item)
    stall = ended.annotations.get(CONST_ROADMAP_IMPLEMENT_ANNOTATION_STALLED) if ended else None
    failure = _failure_of(item, log, stops=stops, stalled=stall is not None)
    digest = _record(item, ImplementRecordKey.JOB_DIGEST)
    store.comment(
        item.number,
        _comment(name, state, log, failure=failure, stopped=stops, digest=digest, stall=stall),
    )
    spend = _spend_tokens(item)
    counted = _counted_tokens(item)
    # The spend is the sum of all Jobs, so only the part after the count is new. A spend below the
    # count means the record started again: the whole spend is new (#4200).
    new_tokens = spend - counted if spend >= counted else spend
    marks: dict[ImplementRecordKey, str | None] = {ImplementRecordKey.JOB_STATE: state}
    if spend > 0:
        marks[ImplementRecordKey.SPEND_COUNTED] = str(spend)
    service_release(store, item.number, marks)
    if stops and failure is not None:
        store.set_field(
            _fresh(store, item.number),
            ItemField.STATUS,
            derive_status(StatusFacts(stopped=True)),
            marks={
                ImplementRecordKey.STOPPED: CONST_ROADMAP_IMPLEMENT_JOB_STEP,
                ImplementRecordKey.FAILURE: failure.value,
            },
        )
    _emit_implement_metrics(repo, item, _outcome(state, failure), failure, new_tokens)
    log_implement_attempt(
        repo,
        item.number,
        state=state,
        failure_class=failure.value if failure else None,
        repair_rounds=_repair_rounds(item),
        tokens=new_tokens,
        digest=digest,
    )
    log_job_result(
        RoadmapJob.IMPLEMENT,
        repo,
        item.number,
        _attempt_result(item),
        failure=failure,
        counts={
            "repair_rounds": _repair_rounds(item),
            "tokens": new_tokens,
            "seconds": _seconds(ended),
        },
    )


def _attempt_result(item: Item) -> str:
    """The result of the attempt of a Job, as its runner recorded it: `ready`, `yielded`,
    `returned` or `stopped`. A Job that recorded no result, such as a pod that the kernel killed,
    stopped (#4845)."""
    recorded = _record(item, ImplementRecordKey.RESULT)
    results = {result.value for result in ImplementResult}
    return recorded if recorded in results else ImplementResult.STOPPED.value


def _seconds(ended: ClusterJob | None) -> int:
    """The seconds from the start of the pod of a Job to its end, or 0 when the API does not hold
    both times, as for a Job that is gone."""
    if ended is None or ended.started is None or ended.ended is None:
        return 0
    return round((ended.ended - ended.started).total_seconds())


def _repair_rounds(item: Item) -> int:
    """The repair rounds that the record of `item` holds, or 0 when it holds no number."""
    recorded = _record(item, ImplementRecordKey.REPAIR_ROUNDS) or ""
    return int(recorded) if recorded.isdigit() else 0


def _outcome(state: str, failure: FailureClass | None) -> str:
    """The result of an attempt: `failed` when it left a failure class, else the state of its Job.
    A runner that writes its own stop exits 0, so its Job is Complete and the attempt failed
    (#4703)."""
    return JobState.FAILED.value if failure is not None else state


def _emit_implement_metrics(
    repo: str, item: Item, result: str, failure: FailureClass | None, new_tokens: int
) -> None:
    item_class = commit_type(item.title) or "chore"
    GLOBAL_METRICS.increment_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
        labels={"repo": repo, "item_class": item_class, "result": result},
    )
    if (repair_rounds := _repair_rounds(item)) > 0:
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
            repair_rounds,
            labels={"repo": repo, "item_class": item_class},
        )
    if new_tokens > 0:
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
            new_tokens,
            labels={"repo": repo, "item_class": item_class},
        )
    tracker = get_consecutive_failures()
    if failure is not None:
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
            labels={"class": failure.value, "repo": repo},
        )
        tracker.failed(repo, failure.value)
    else:
        tracker.delivered(repo)


def _report_ended(
    store: RoadmapStore, jobs: ClusterJobs, held: Mapping[str, ClusterJob], repo: str
) -> tuple[str, ...]:
    reported: list[str] = []
    for item, name in _unreported(store, held):
        job = held.get(name)
        if job is not None and job.state is JobState.RUNNING:
            continue
        _report(store, jobs, repo, item, name, job)
        reported.append(name)
    return tuple(reported)


def _size_of(source: Path | str, planned: PlannedChanges, target: ImplementTarget) -> RunnerSize:
    """The row of the size table for the plan of `target`. The plan is on the default branch for a
    Planned item and on the branch of the item for a Staged one. Raises `GitOperationError` when
    git cannot read it."""
    rev = f"origin/{planned.default if target.planned else target.branch}"
    tasks = tasks_at(Path(source), rev, target.item.number, operation=GIT_OPERATION)
    return runner_size(plan_file_count(tasks))


def _create(
    store: RoadmapStore,
    jobs: ClusterJobs,
    repo: str,
    target: ImplementTarget,
    label: str,
    size: RunnerSize,
) -> str | None:
    """Claim the item and record the Job on it, then create the Job. The record comes first: a
    record that fails after the create would leave a Job that no item names, and a Job that dies
    early would leave its item eligible for a new Job in every round. A create that fails takes the
    record and the claim back. A round that dies between the two leaves a record of a Job that does
    not exist, which the next round reports as gone and stops the item for. The name of the Job, or
    None, with nothing written, when an agent or a person claimed the item since the plan."""
    number = target.item.number
    settings = load_settings().roadmap.implement
    name = job_name(template=RUNNER_TEMPLATE)
    cronjob = jobs.cronjob(RUNNER_TEMPLATE)
    marks = {
        ImplementRecordKey.JOB: name,
        ImplementRecordKey.JOB_STATE: None,
        ImplementRecordKey.RESULT: None,
        ImplementRecordKey.JOB_DIGEST: image_digest(cronjob, RUNNER_TEMPLATE),
    }
    if not service_claim(store, number, marks):
        return None
    try:
        jobs.create(
            ["roadmap", "implement", "--repo", repo, "--item", str(number), "--confirm"],
            template=RUNNER_TEMPLATE,
            env={setting_variables()[CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING]: repo, **size.env},
            resources=size.resources(settings.max_memory_limit),
            labels={CONST_ROADMAP_IMPLEMENT_JOB_LABEL: label},
            name=name,
            cronjob=cronjob,
            deadline=settings.deadline_extension_seconds,
            annotations={
                CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT: str(
                    int(datetime.now(UTC).timestamp())
                )
            },
        )
    except ClusterJobError:
        service_release(store, number, {ImplementRecordKey.JOB: None})
        raise
    return name


def _note_needs_fix(store: RoadmapStore, plan: ImplementPlan) -> tuple[NeedsFix, ...]:
    """The items that `plan` leaves out for the label `plan/needs-fix` and that no round noted for
    the same draft. The round records the draft in `implement.needs_fix`, and clears the mark of
    an item that the plan judged and did not leave out for the label."""
    new = tuple(
        held
        for held in plan.needs_fix
        if held.item.job_record.get(ImplementRecordKey.NEEDS_FIX) != str(held.pull)
    )
    for held in new:
        store.set_marks(held.item, {ImplementRecordKey.NEEDS_FIX: str(held.pull)})
    judged = {
        *(left.number for left in plan.left_out),
        *(target.item.number for target in plan.selected),
        *plan.beyond,
    }
    free = judged - {held.item.number for held in plan.needs_fix}
    for item in store.items():
        if item.number in free and item.job_record.get(ImplementRecordKey.NEEDS_FIX) is not None:
            store.set_marks(item, {ImplementRecordKey.NEEDS_FIX: None})
    return new


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
    is missing. Raises RoadmapImplementError before any request when `repo` is empty: each
    counter of the round has the label `repo`, and a series with no repository is read by no
    rule of a repository (#4703).
    """
    if not repo:
        raise RoadmapImplementError(MESSAGES.roadmap.implement_round_no_repo)
    api = jobs or ClusterJobs()
    label = repository_label(repo)
    held = {job.name: job for job in api.list_jobs({CONST_ROADMAP_IMPLEMENT_JOB_LABEL: label})}
    reported = _report_ended(store, api, held, repo)
    manage_deadlines(api, held.values())
    planned = read_planned_changes(Path(source), operation=GIT_OPERATION)
    swept = sync_statuses(store, repo=repo, planned=planned).failed
    stops = clear_stops(
        store, planned=planned, digest=partial(api.template_digest, RUNNER_TEMPLATE)
    )
    failed = (*swept, *stops.failed)
    if any(job.state is JobState.RUNNING for job in held.values()):
        return SubmitResult(
            reported=reported, waiting=True, status_failed=failed, cleared=stops.cleared
        )
    plan = plan_implement(
        store,
        repo=repo,
        source=source,
        filters=parse_implement_filters(()),
        limit=DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
        planned=planned,
    )
    needs_fix = _note_needs_fix(store, plan)
    if not plan.selected:
        return SubmitResult(
            reported=reported, status_failed=failed, cleared=stops.cleared, needs_fix=needs_fix
        )
    if _runs(api, label):
        return SubmitResult(
            reported=reported,
            waiting=True,
            status_failed=failed,
            cleared=stops.cleared,
            needs_fix=needs_fix,
        )
    number = plan.selected[0].item.number
    size = _size_of(source, planned, plan.selected[0])
    created = _create(store, api, repo, plan.selected[0], label, size)
    failed = (*stops.failed, *sync_statuses(store, repo=repo, planned=planned).failed)
    return SubmitResult(
        reported=reported,
        created=created,
        left=number if created is None else None,
        status_failed=failed,
        cleared=stops.cleared,
        effort=plan.effort,
        fallback=plan.fallback,
        needs_fix=needs_fix,
    )


__all__ = ["SubmitResult", "run_implement_round"]
