"""The fix-checks units that the watch row starts (#5027, ADR 0021 section 8).

**Due.** A bot pull request is due when `due_steps` gives `fix_checks`: its verdict is FAILED, a
check failed with the class test, lint, types or plan check, and no live unit holds its item
(`steps/watch.py`). A `ci_infra` failure gets no unit. The predicate moves to `due_jobs` with
#5504; there is no due mark.

**Unit.** One Job from CronJob `devops-cli-runner` through the launcher seam (`job_launcher.py`),
named `RepoRef.unit_name(FIX_CHECKS, "<pr>:<head>:<check>", item)`, so the same head and check
give the same name and a second create gets 409. The Job runs `devops roadmap step fix-checks
--repo <owner/name> --pull <pr> --head <head> --check <check>`, with `--confirm` in mode `on`, and
without it in mode `plan`, where the step logs the action that it would take and writes nothing.
The Job has the large row of the size table: it runs the check of a whole pull request again, and
the row reads no plan. Its deadline is `fix_checks_deadline`.

**One Job for each pull request.** While a fix Job of a pull request runs or waits, no unit of that
pull request gets a Job (#6018). Thus two checks that fail on one head do not hold two model
places: the second check gets its unit after the first Job ends with no repair, and a repair
pushes a new head, which is a new unit.

**Order.** A fix Job counts against `roadmap.model_jobs`. The round resumes the fix Jobs of the
repository that wait, oldest first, while a place is free. Then it creates the Job of each new
unit, suspended when no place is free or when a fix Job of the repository still waits. The round
deletes each fix Job of any repository that has waited longer than
`roadmap.fix_checks.max_wait_minutes`, with a log line (`job_launcher.stale`).

**Report.** The round reads the result line of each ended fix Job of the repository once: the JSON
line of the step on the log of its pod. It logs the outcome as the result line of the job
`fix_checks`, counts it in `devops_cli_service_fix_checks_jobs_total`, and writes it on the Job in
the annotation `roadmap.devops-cli/outcome`. A Job that left no result line has the outcome
`deadline` when its deadline ended it, `error` when its command exited 1, a typed stop such as a
refused checkout, and `none` for each other end: a pod that an eviction or a drain ended with exit
75, or that left no status. The alert `RoadmapFixChecksJobWithoutResult` reads the three.

**Next attempt.** A unit whose last Job has the outcome `none` gets the next attempt as a new Job,
named from `<pr>:<head>:<check>#<n>`. The attempts after the first are at most
`roadmap.implement.continuations_per_item`, and each waits after the end of the last Job, from
`CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS`, doubled at each attempt, up to
`CONST_ROADMAP_FIX_CHECKS_RETRY_CAP_SECONDS`. A Job with a result line, or the outcome `error` or
`deadline`, ends its unit: the step records what it did, and an error or a slow step would come
again. A new head or another check is a new unit.

**Unit record.** In mode `on`, the round writes the attempt, the outcome and the next allowed time
of each reported unit in the item record, `fix_checks.units`, keyed by the unit. The runner
template deletes an ended Job after 24 hours; a unit with no Job takes its last attempt from the
record, so the cap and the wait do not start again (#6018).

**Mode.** `roadmap.fix_checks.mode`: `off` reads and writes nothing, and `plan` and `on` work as
above. In mode `plan` the Service writes nothing to GitHub. In mode `on` the Service writes the
unit record, and the watch row runs the ready path of the step in the Service pod: it can mark a
repaired draft ready and record `fix_checks.result`. Only the Job of mode `on` pushes a repair or
posts a comment.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from devops_cli.config.constants import (
    CONST_ROADMAP_FIX_CHECKS_JOB_MARGIN_SECONDS,
    CONST_ROADMAP_FIX_CHECKS_JOB_MIN_MARGIN_SECONDS,
    CONST_ROADMAP_FIX_CHECKS_RETRY_CAP_SECONDS,
    CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS,
    CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS,
    CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES,
    CONST_RUNNER_PHASE_PREPARE,
    CONST_RUNNER_PHASE_PUBLISH,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.k8s import ClusterJobError, ClusterJobExistsError
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.k8s.cluster_job import (
    ATTEMPT_ANNOTATION,
    COMPONENT_LABEL,
    FIX_CHECKS_COMPONENT,
    ITEM_LABEL,
    OUTCOME_ANNOTATION,
    OWNER_LABEL,
    REPO_LABEL,
    RUNNER_TEMPLATE,
    UNIT_KEY_ANNOTATION,
)
from devops_cli.k8s.cluster_job_api import ClusterJob, ClusterJobs, JobState
from devops_cli.roadmap.implement.implement_size import RUNNER_SIZES
from devops_cli.roadmap.job_launcher import (
    CREATED_AT_ANNOTATION,
    ModelSlots,
    RunnerUnit,
    created_at,
    launch,
    model_slots,
    oldest_first,
    stale,
    waits,
)
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from devops_cli.roadmap.stores.store import FixChecksRecordKey
from devops_cli.telemetry.metrics import GLOBAL_METRICS

if TYPE_CHECKING:
    from devops_cli.config.settings import RoadmapImplementConfig
    from devops_cli.roadmap.stores.store import RoadmapStore

logger = logging.getLogger(__name__)

# The outcomes of an ended Job that left no result line: a kill, a command that exited 1, and the
# end by the deadline of the Job.
OUTCOME_NONE: Final[str] = "none"
OUTCOME_ERROR: Final[str] = "error"
OUTCOME_DEADLINE: Final[str] = "deadline"
# The count of a round that a Kubernetes or a configuration error stopped (#6018).
ROUND_ERROR: Final[str] = "round_error"
_ERROR_EXIT: Final[int] = 1
# The reason of the condition Failed of a Job that its `activeDeadlineSeconds` ended.
_DEADLINE_REASON: Final[str] = "DeadlineExceeded"
# The containers of a Job on the phases that print the result line, in the order that it is read.
_RESULT_CONTAINERS: Final[tuple[str, ...]] = (
    CONST_RUNNER_PHASE_PUBLISH,
    CONST_RUNNER_PHASE_PREPARE,
)
# The `job` value of the result line of the step (`FixChecksReport.to_json`).
_STEP_JOB: Final[str] = "fix_checks"
_LARGE = RUNNER_SIZES[-1]
# The units that the record of one item keeps, the last written first to go after the others.
_MAX_UNITS: Final[int] = 8


@dataclass(frozen=True)
class FixDue:
    """A fix unit that the watch row found due: the pull request, the head that it judged, the
    failed check, the item that the pull request delivers or plans, and the text of
    `fix_checks.units` of that item when the row read it."""

    pull: int
    head: str
    check: str
    item: int
    units: str | None = field(default=None, compare=False)

    @property
    def key(self) -> str:
        """The input key of the unit name: `<pr>:<head>:<check>`."""
        return f"{self.pull}:{self.head}:{self.check}"


class UnitRecord(BaseModel):
    """What the item record keeps of one unit (#6018): its last attempt, the outcome of that
    attempt, and the time (epoch seconds) before which no next attempt starts, 0 for none."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    attempt: int = Field(ge=1)
    outcome: str
    retry_at: int = 0


_UNITS: Final = TypeAdapter(dict[str, UnitRecord])


def unit_records(text: str | None) -> dict[str, UnitRecord]:
    """The unit records of the text of `fix_checks.units`, by the unit key. Text that does not
    hold them gives none, with a warning."""
    if not text:
        return {}
    try:
        return _UNITS.validate_json(text)
    except ValidationError:
        logger.warning("The record fix_checks.units is not readable; the round reads no unit")
        return {}


def _same_pull_other_head(key: str, other: str) -> bool:
    pull, head = key.split(":", 2)[:2]
    other_pull, other_head = (other.split(":", 2) + ["", ""])[:2]
    return other_pull == pull and other_head != head


def with_unit(units: Mapping[str, UnitRecord], key: str, record: UnitRecord) -> str:
    """The text of `fix_checks.units` with `record` for the unit `key`. A unit of the same pull
    request on another head goes: the row judges only the current head. At most `_MAX_UNITS`
    units stay, the last written last."""
    kept = {
        other: held
        for other, held in units.items()
        if other != key and not _same_pull_other_head(key, other)
    }
    kept[key] = record
    newest = dict(list(kept.items())[-_MAX_UNITS:])
    return _UNITS.dump_json(newest).decode()


@dataclass(frozen=True)
class FixChecksRound:
    """What a round did: the Jobs that it created, created suspended, found by 409, resumed and
    deleted after their wait, and the outcome of each Job that it reported, by the name of the
    Job."""

    created: tuple[str, ...] = ()
    queued: tuple[str, ...] = ()
    existed: tuple[str, ...] = ()
    resumed: tuple[str, ...] = ()
    expired: tuple[str, ...] = ()
    reported: Mapping[str, str] = field(default_factory=dict[str, str])


def fix_checks_deadline(implement: RoadmapImplementConfig) -> int:
    """The `activeDeadlineSeconds` of a fix-checks Job: the time limit of its model step plus
    `CONST_ROADMAP_FIX_CHECKS_JOB_MARGIN_SECONDS`. The limits nest: a model request ends before a
    command, a command before the step, the step at least 300 s before the deadline of the Job, and
    that deadline at the latest at the cap of the admission policy.

    Raises ConfigurationError, which names the two settings, when the order breaks.
    """
    deadline = implement.step_time_limit_seconds + CONST_ROADMAP_FIX_CHECKS_JOB_MARGIN_SECONDS
    chain = (
        ("roadmap.implement.request_timeout_seconds", implement.request_timeout_seconds),
        ("roadmap.implement.command_timeout_seconds", implement.command_timeout_seconds),
        ("roadmap.implement.step_time_limit_seconds", implement.step_time_limit_seconds),
    )
    for (inner, short), (outer, long) in pairwise(chain):
        if short >= long:
            raise ConfigurationError(
                f"{inner} ({short}) must be below {outer} ({long}) for a fix-checks Job"
            )
    step = implement.step_time_limit_seconds
    if deadline - step < CONST_ROADMAP_FIX_CHECKS_JOB_MIN_MARGIN_SECONDS:
        raise ConfigurationError("The deadline of a fix-checks Job must be 300 s above its step")
    if deadline > CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS:
        raise ConfigurationError(
            f"roadmap.implement.step_time_limit_seconds ({step}) gives a fix-checks Job a deadline "
            f"of {deadline} s, above the cap of {CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS} s"
        )
    return deadline


def fix_args(repo: str, due: FixDue, *, confirm: bool) -> tuple[str, ...]:
    """The args of the fix-checks Job of `due`: the step on the judged head and the failed check,
    with `--confirm` only in mode `on`."""
    args = (
        "roadmap",
        "step",
        "fix-checks",
        "--repo",
        repo,
        "--pull",
        str(due.pull),
        "--head",
        due.head,
        "--check",
        due.check,
    )
    return (*args, "--confirm") if confirm else args


def _attempt_key(due: FixDue, attempt: int) -> str:
    return due.key if attempt == 1 else f"{due.key}#{attempt}"


def fix_unit(
    repo: str, due: FixDue, *, attempt: int, confirm: bool, suspend: bool, now: datetime
) -> RunnerUnit:
    """The runner unit of attempt `attempt` of `due`, as the module says."""
    ref = RepoRef(repo)
    return RunnerUnit(
        row=ServiceRow.FIX_CHECKS,
        repo=ref,
        item=due.item,
        args=fix_args(repo, due, confirm=confirm),
        size=_LARGE,
        name=ref.unit_name(ServiceRow.FIX_CHECKS, _attempt_key(due, attempt), due.item),
        deadline=fix_checks_deadline(load_settings().roadmap.implement),
        annotations={
            UNIT_KEY_ANNOTATION: due.key,
            ATTEMPT_ANNOTATION: str(attempt),
            CREATED_AT_ANNOTATION: str(int(now.timestamp())),
        },
        suspend=suspend,
    )


def result_of(log: str) -> str | None:
    """The `result` of the last result line of the step in `log`, or None when the log holds
    none."""
    for line in reversed(log.splitlines()):
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("job") == _STEP_JOB and data.get("result"):
            return str(data["result"])
    return None


def _count(repo: str, result: str) -> None:
    GLOBAL_METRICS.increment_counter(
        CONST_SERVICE_METRIC_FIX_CHECKS_JOBS, labels={"repo": repo, "result": result}
    )


def _attempt(job: ClusterJob) -> int:
    text = job.annotations.get(ATTEMPT_ANNOTATION, "")
    return int(text) if text.isdecimal() else 1


def _pull_of(job: ClusterJob) -> int | None:
    """The pull request of the fix Job `job`, from its unit key `<pr>:<head>:<check>`."""
    pull = job.annotations.get(UNIT_KEY_ANNOTATION, "").split(":", 1)[0]
    return int(pull) if pull.isdecimal() else None


def _retry_at(ended: datetime | None, attempt: int) -> int:
    """The time (epoch seconds) after which the attempt after `attempt` may start: the end of the
    Job plus the wait of the module, or 0 when the Job has no end time."""
    wait = min(
        CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS * 2 ** (attempt - 1),
        CONST_ROADMAP_FIX_CHECKS_RETRY_CAP_SECONDS,
    )
    return int((ended + timedelta(seconds=wait)).timestamp()) if ended else 0


def _log_tail(api: ClusterJobs, name: str, container: str) -> str:
    """The tail of the log of `container` in the pod of Job `name`, or empty when the API refuses
    it: a pod that an eviction ended or that never started has no log."""
    try:
        return api.log_tail(name, CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES, container=container)
    except ClusterJobError:
        return ""


def _result_line(api: ClusterJobs, name: str) -> str | None:
    """The result of the result line of Job `name`. On the phases (#3700), `publish` prints it,
    and `prepare` prints it when it ended the round itself. A pod with one container holds both."""
    for container in _RESULT_CONTAINERS:
        found = result_of(_log_tail(api, name, container))
        if found is not None:
            return found
    return None


def _outcome(api: ClusterJobs, job: ClusterJob) -> str:
    """The outcome of the ended Job `job`: the result of its result line, else `deadline` when its
    deadline ended it, else `error` for a command that exited 1, else `none`. A read of the pod
    that the API refuses gives no exit."""
    found = _result_line(api, job.name)
    if found is not None:
        return found
    if job.reason == _DEADLINE_REASON:
        return OUTCOME_DEADLINE
    try:
        exit_status = api.pod_end(job.name).exit_status
    except ClusterJobError:
        exit_status = None
    return OUTCOME_ERROR if exit_status == _ERROR_EXIT else OUTCOME_NONE


def _record_unit(store: RoadmapStore, job: ClusterJob, outcome: str) -> None:
    """Write the attempt, the outcome and the next allowed time of the unit of `job` in the record
    of its item, as the item holds it now. A Job with no unit key or no item writes nothing."""
    key = job.annotations.get(UNIT_KEY_ANNOTATION, "")
    item_text = job.labels.get(ITEM_LABEL, "")
    if not key or not item_text.isdecimal():
        return
    item = store.item(int(item_text))
    if item is None:
        return
    attempt = _attempt(job)
    record = UnitRecord(
        attempt=attempt,
        outcome=outcome,
        retry_at=_retry_at(job.ended, attempt) if outcome == OUTCOME_NONE else 0,
    )
    units = unit_records(item.job_record.get(FixChecksRecordKey.UNITS))
    store.set_marks(item, {FixChecksRecordKey.UNITS: with_unit(units, key, record)})


def _report(
    api: ClusterJobs, repo: str, held: Sequence[ClusterJob], store: RoadmapStore | None
) -> dict[str, str]:
    """Report each ended fix Job that has no outcome yet, as the module says, and write its unit
    record in `store` when one is given. The record goes first: a write that fails leaves the Job
    with no annotation, so the next round reports it again. The outcome of each, by the name of
    its Job."""
    reported: dict[str, str] = {}
    for job in held:
        if job.state is JobState.RUNNING or OUTCOME_ANNOTATION in job.annotations:
            continue
        outcome = _outcome(api, job)
        if store is not None:
            _record_unit(store, job, outcome)
        api.patch_job(job.name, annotations={OUTCOME_ANNOTATION: outcome})
        item = job.labels.get(ITEM_LABEL, "")
        seconds = (
            round((job.ended - job.started).total_seconds()) if job.ended and job.started else 0
        )
        log_job_result(
            RoadmapJob.FIX_CHECKS,
            repo,
            int(item) if item.isdecimal() else None,
            outcome,
            counts={"attempt": _attempt(job), "seconds": seconds},
            names={"end": job.reason or job.state.value},
        )
        _count(repo, outcome)
        reported[job.name] = outcome
    return reported


def _last_try(
    jobs: Sequence[ClusterJob], outcomes: Mapping[str, str], record: UnitRecord | None
) -> UnitRecord | None:
    """The last attempt of a unit: from its last Job in the cluster, or from its unit record when
    the record holds a later attempt or the TTL deleted the Jobs."""
    tries: list[UnitRecord] = []
    if jobs:
        last = max(jobs, key=_attempt)
        attempt = _attempt(last)
        outcome = outcomes.get(last.name) or last.annotations.get(OUTCOME_ANNOTATION, "")
        tries.append(
            UnitRecord(attempt=attempt, outcome=outcome, retry_at=_retry_at(last.ended, attempt))
        )
    if record is not None:
        tries.append(record)
    return max(tries, key=lambda held: held.attempt) if tries else None


def _next_attempt(
    jobs: Sequence[ClusterJob],
    outcomes: Mapping[str, str],
    now: datetime,
    extra: int,
    record: UnitRecord | None = None,
) -> int | None:
    """The attempt to create for a unit whose Jobs are `jobs` and whose unit record is `record`,
    or None: 1 with no attempt, else the attempt after the last when it left no result line,
    within `extra` more attempts and after its wait."""
    if any(job.state is JobState.RUNNING for job in jobs):
        return None
    last = _last_try(jobs, outcomes, record)
    if last is None:
        return 1
    if last.outcome != OUTCOME_NONE or last.attempt > extra:
        return None
    if now.timestamp() < last.retry_at:
        return None
    return last.attempt + 1


def _of_repo(job: ClusterJob, ref: RepoRef) -> bool:
    labels = job.labels
    return labels.get(OWNER_LABEL) == ref.owner_label and labels.get(REPO_LABEL) == ref.repo_label


def _expire(
    api: ClusterJobs, repo: str, jobs: Iterable[ClusterJob], now: datetime
) -> tuple[str, ...]:
    """Delete each fix Job of `jobs` that has waited longer than
    `roadmap.fix_checks.max_wait_minutes`, of any repository, with a log line. A delete that the
    API refuses leaves the Job, which holds no place, for the next round."""
    limit = load_settings().roadmap.fix_checks.max_wait_minutes
    deleted: list[str] = []
    for job in jobs:
        if not stale(job, now):
            continue
        waited = (now - datetime.fromtimestamp(created_at(job), UTC)).total_seconds() // 60
        try:
            api.delete_job(job.name)
        except ClusterJobError as error:
            logger.warning("Could not delete the waiting fix-checks Job %s: %s", job.name, error)
            continue
        logger.warning(
            "Deleted the fix-checks Job %s: it waited %d min for a model place, above "
            "roadmap.fix_checks.max_wait_minutes (%d)",
            job.name,
            waited,
            limit,
        )
        _count(repo, "expired")
        deleted.append(job.name)
    return tuple(deleted)


def _starts(
    due: Sequence[FixDue],
    held: Sequence[ClusterJob],
    reported: Mapping[str, str],
    now: datetime,
    extra: int,
) -> list[tuple[FixDue, int]]:
    """The units of `due` to start, with their attempt: at most one for each pull request, and
    none for a pull request whose fix Job runs or waits."""
    live = {_pull_of(job) for job in held if job.state is JobState.RUNNING}
    starts: list[tuple[FixDue, int]] = []
    for unit_due in due:
        if unit_due.pull in live:
            continue
        attempt = _next_attempt(
            [job for job in held if job.annotations.get(UNIT_KEY_ANNOTATION) == unit_due.key],
            reported,
            now,
            extra,
            unit_records(unit_due.units).get(unit_due.key),
        )
        if attempt is not None:
            starts.append((unit_due, attempt))
            live.add(unit_due.pull)
    return starts


def run_fix_checks_round(
    repo: str,
    due: Sequence[FixDue],
    *,
    now: datetime,
    jobs: ClusterJobs | None = None,
    store: RoadmapStore | None = None,
) -> FixChecksRound:
    """One round of the fix-checks units of `repo`, after a tick of the watch row that found the
    units `due`, as the module says. In mode `on` the round writes the unit record of each Job
    that it reports in `store`.

    Raises ClusterJobError when the Kubernetes API refuses a call or CronJob `devops-cli-runner` is
    missing, and ConfigurationError when the limits of a fix Job do not nest.
    """
    settings = load_settings().roadmap
    mode = settings.fix_checks.mode
    if mode == "off":
        return FixChecksRound()
    api = jobs or ClusterJobs()
    ref = RepoRef(repo)
    listed = api.list_jobs({COMPONENT_LABEL: FIX_CHECKS_COMPONENT})
    expired = _expire(api, repo, listed, now)
    held = [job for job in listed if _of_repo(job, ref) and job.name not in expired]
    reported = _report(api, repo, held, store if mode == "on" else None)
    starts = _starts(due, held, reported, now, settings.implement.continuations_per_item)
    waiting = oldest_first(job for job in held if waits(job) and not stale(job, now))
    if not starts and not waiting:
        return _logged(repo, mode, FixChecksRound(expired=expired, reported=reported))
    queue = _Queue(api, repo, model_slots(api, now=now))
    resumed = queue.resume(waiting)
    for unit_due, attempt in starts:
        unit = fix_unit(
            repo, unit_due, attempt=attempt, confirm=mode == "on", suspend=queue.full, now=now
        )
        queue.start(unit)
    return _logged(
        repo,
        mode,
        FixChecksRound(
            created=tuple(queue.created),
            queued=tuple(queue.queued),
            existed=tuple(queue.existed),
            resumed=resumed,
            expired=expired,
            reported=reported,
        ),
    )


def round_failed(repo: str, error: Exception) -> FixChecksRound:
    """Log and count the error that stopped the fix-checks round of `repo`: the Kubernetes API
    refused a call, the CronJob is missing, or the limits of a fix Job do not nest. The watch row
    goes on with an empty round (#6018)."""
    logger.warning("The fix-checks round of %s stopped: %s", repo, error)
    _count(repo, ROUND_ERROR)
    return FixChecksRound()


class _Queue:
    """The places of the model limit for the fix Jobs of one repository in one round: the round
    resumes the waiting fix Jobs of the repository, oldest first, and then starts each new Job,
    suspended while no place is free or a fix Job of the repository still waits."""

    def __init__(self, api: ClusterJobs, repo: str, slots: ModelSlots) -> None:
        self.api = api
        self.repo = repo
        self.free = slots.for_fix
        self.waiting = 0
        self.created: list[str] = []
        self.queued: list[str] = []
        self.existed: list[str] = []
        self._cronjob: dict[str, Any] | None = None

    @property
    def full(self) -> bool:
        """Whether a new Job of the repository must wait suspended."""
        return self.free <= 0 or self.waiting > 0

    def resume(self, waiting: Sequence[ClusterJob]) -> tuple[str, ...]:
        """Resume the waiting fix Jobs `waiting` of the repository while a place is free, in
        their order."""
        resumed: list[str] = []
        for job in waiting:
            if self.free <= 0:
                self.waiting += 1
                continue
            self.api.patch_job(job.name, suspend=False)
            _count(self.repo, "resumed")
            resumed.append(job.name)
            self.free -= 1
        return tuple(resumed)

    def start(self, unit: RunnerUnit) -> None:
        """Create the Job of `unit`. A 409 finds the Job of the same unit name."""
        self._cronjob = self._cronjob or self.api.cronjob(RUNNER_TEMPLATE)
        try:
            name = launch(self.api, unit, cronjob=self._cronjob)
        except ClusterJobExistsError:
            _count(self.repo, "existed")
            self.existed.append(unit.name)
            return
        if unit.suspend:
            _count(self.repo, "queued")
            self.queued.append(name)
            self.waiting += 1
            return
        _count(self.repo, "created")
        self.created.append(name)
        self.free -= 1


def _logged(repo: str, mode: str, result: FixChecksRound) -> FixChecksRound:
    """Log what the round did, and give `result`."""
    reported = result.reported
    logger.info(
        "The fix-checks units of %s (mode %s): created %s, queued %s, existed %s, resumed %s, "
        "expired %s, reported %s",
        repo,
        mode,
        ",".join(result.created) or "none",
        ",".join(result.queued) or "none",
        ",".join(result.existed) or "none",
        ",".join(result.resumed) or "none",
        ",".join(result.expired) or "none",
        ",".join(f"{name}={outcome}" for name, outcome in reported.items()) or "none",
    )
    return result


__all__ = [
    "OUTCOME_DEADLINE",
    "OUTCOME_ERROR",
    "OUTCOME_NONE",
    "ROUND_ERROR",
    "FixChecksRound",
    "FixDue",
    "UnitRecord",
    "fix_args",
    "fix_checks_deadline",
    "fix_unit",
    "result_of",
    "round_failed",
    "run_fix_checks_round",
    "unit_records",
    "with_unit",
]
