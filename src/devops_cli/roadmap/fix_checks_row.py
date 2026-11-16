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

**Order.** A fix Job counts against `roadmap.model_jobs`. The round resumes the fix Jobs of the
repository that wait, oldest first, while a place is free. Then it creates the Job of each new
unit, suspended when no place is free or when a fix Job of the repository still waits.

**Report.** The round reads the result line of each ended fix Job of the repository once: the JSON
line of the step on the log of its pod. It logs the outcome as the result line of the job
`fix_checks`, counts it in `devops_cli_service_fix_checks_jobs_total`, and writes it on the Job in
the annotation `roadmap.devops-cli/outcome`. A Job that left no result line has the outcome
`error` when its command exited 1, a typed stop such as a refused checkout, and `none` for each
other end: a pod that an eviction or a drain ended with exit 75, that its deadline ended, or that
left no status. The alert `RoadmapFixChecksJobWithoutResult` reads both.

**Next attempt.** A unit whose last Job has the outcome `none` gets the next attempt as a new Job,
named from `<pr>:<head>:<check>#<n>`. The attempts after the first are at most
`roadmap.implement.continuations_per_item`, and each waits after the end of the last Job, from
`CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS`, doubled at each attempt, up to
`CONST_ROADMAP_FIX_CHECKS_RETRY_CAP_SECONDS`. A Job with a result line or the outcome `error` ends
its unit: the step records what it did, an error would come again, and a new head or another check
is a new unit.

**Mode.** `roadmap.fix_checks.mode`: `off` reads and writes nothing, and `plan` and `on` work as
above. The Service writes nothing to GitHub in either mode; only the Job of mode `on` does.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_FIX_CHECKS_JOB_MARGIN_SECONDS,
    CONST_ROADMAP_FIX_CHECKS_JOB_MIN_MARGIN_SECONDS,
    CONST_ROADMAP_FIX_CHECKS_RETRY_CAP_SECONDS,
    CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS,
    CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS,
    CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES,
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
    launch,
    model_slots,
)
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from devops_cli.telemetry.metrics import GLOBAL_METRICS

if TYPE_CHECKING:
    from devops_cli.config.settings import RoadmapImplementConfig

logger = logging.getLogger(__name__)

# The outcomes of an ended Job that left no result line: a kill, and a command that exited 1.
OUTCOME_NONE: Final[str] = "none"
OUTCOME_ERROR: Final[str] = "error"
_ERROR_EXIT: Final[int] = 1
# The `job` value of the result line of the step (`FixChecksReport.to_json`).
_STEP_JOB: Final[str] = "fix_checks"
_LARGE = RUNNER_SIZES[-1]


@dataclass(frozen=True)
class FixDue:
    """A fix unit that the watch row found due: the pull request, the head that it judged, the
    failed check, and the item that the pull request delivers or plans."""

    pull: int
    head: str
    check: str
    item: int

    @property
    def key(self) -> str:
        """The input key of the unit name: `<pr>:<head>:<check>`."""
        return f"{self.pull}:{self.head}:{self.check}"


@dataclass(frozen=True)
class FixChecksRound:
    """What a round did: the Jobs that it created, created suspended, found by 409 and resumed,
    and the outcome of each Job that it reported, by the name of the Job."""

    created: tuple[str, ...] = ()
    queued: tuple[str, ...] = ()
    existed: tuple[str, ...] = ()
    resumed: tuple[str, ...] = ()
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


def _log_tail(api: ClusterJobs, name: str) -> str:
    """The tail of the log of the pod of Job `name`, or empty when the API refuses it: a pod that
    an eviction ended or that never started has no log."""
    try:
        return api.log_tail(name, CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES)
    except ClusterJobError:
        return ""


def _outcome(api: ClusterJobs, name: str) -> str:
    """The outcome of the ended Job `name`: the result of its result line, else `error` for a
    command that exited 1, else `none`. A read of the pod that the API refuses gives no exit."""
    found = result_of(_log_tail(api, name))
    if found is not None:
        return found
    try:
        exit_status = api.pod_end(name).exit_status
    except ClusterJobError:
        exit_status = None
    return OUTCOME_ERROR if exit_status == _ERROR_EXIT else OUTCOME_NONE


def _report(api: ClusterJobs, repo: str, held: Sequence[ClusterJob]) -> dict[str, str]:
    """Report each ended fix Job that has no outcome yet, as the module says. The outcome of
    each, by the name of its Job."""
    reported: dict[str, str] = {}
    for job in held:
        if job.state is JobState.RUNNING or OUTCOME_ANNOTATION in job.annotations:
            continue
        outcome = _outcome(api, job.name)
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


def _next_attempt(
    jobs: Sequence[ClusterJob], outcomes: Mapping[str, str], now: datetime, extra: int
) -> int | None:
    """The attempt to create for a unit whose Jobs are `jobs`, or None: 1 with no Job, else the
    attempt after the last when it left no result line, within `extra` more attempts and after its
    wait."""
    if not jobs:
        return 1
    if any(job.state is JobState.RUNNING for job in jobs):
        return None
    last = max(jobs, key=_attempt)
    outcome = outcomes.get(last.name) or last.annotations.get(OUTCOME_ANNOTATION)
    attempt = _attempt(last)
    if outcome != OUTCOME_NONE or attempt > extra:
        return None
    wait = min(
        CONST_ROADMAP_FIX_CHECKS_RETRY_SECONDS * 2 ** (attempt - 1),
        CONST_ROADMAP_FIX_CHECKS_RETRY_CAP_SECONDS,
    )
    if last.ended is not None and now < last.ended + timedelta(seconds=wait):
        return None
    return attempt + 1


def _of_repo(job: ClusterJob, ref: RepoRef) -> bool:
    labels = job.labels
    return labels.get(OWNER_LABEL) == ref.owner_label and labels.get(REPO_LABEL) == ref.repo_label


def run_fix_checks_round(
    repo: str,
    due: Sequence[FixDue],
    *,
    now: datetime,
    jobs: ClusterJobs | None = None,
) -> FixChecksRound:
    """One round of the fix-checks units of `repo`, after a tick of the watch row that found the
    units `due`, as the module says.

    Raises ClusterJobError when the Kubernetes API refuses a call or CronJob `devops-cli-runner` is
    missing, and ConfigurationError when the limits of a fix Job do not nest.
    """
    settings = load_settings().roadmap
    mode = settings.fix_checks.mode
    if mode == "off":
        return FixChecksRound()
    api = jobs or ClusterJobs()
    ref = RepoRef(repo)
    held = [
        job for job in api.list_jobs({COMPONENT_LABEL: FIX_CHECKS_COMPONENT}) if _of_repo(job, ref)
    ]
    reported = _report(api, repo, held)
    starts = [
        (unit_due, attempt)
        for unit_due in due
        if (
            attempt := _next_attempt(
                [job for job in held if job.annotations.get(UNIT_KEY_ANNOTATION) == unit_due.key],
                reported,
                now,
                settings.implement.continuations_per_item,
            )
        )
        is not None
    ]
    if not starts and not any(job.suspended for job in held):
        return _logged(repo, mode, FixChecksRound(reported=reported))
    queue = _Queue(api, repo, model_slots(api))
    resumed = queue.resume()
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
            reported=reported,
        ),
    )


class _Queue:
    """The places of the model limit for the fix Jobs of one repository in one round: the round
    resumes the waiting fix Jobs of the repository, oldest first, and then starts each new Job,
    suspended while no place is free or a fix Job of the repository still waits."""

    def __init__(self, api: ClusterJobs, repo: str, slots: ModelSlots) -> None:
        self.api = api
        self.repo = repo
        self.ref = RepoRef(repo)
        self.slots = slots
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

    def resume(self) -> tuple[str, ...]:
        """Resume the waiting fix Jobs of the repository while a place is free, oldest first."""
        resumed: list[str] = []
        for job in self.slots.waiting:
            if not _of_repo(job, self.ref):
                continue
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
        "reported %s",
        repo,
        mode,
        ",".join(result.created) or "none",
        ",".join(result.queued) or "none",
        ",".join(result.existed) or "none",
        ",".join(result.resumed) or "none",
        ",".join(f"{name}={outcome}" for name, outcome in reported.items()) or "none",
    )
    return result


__all__ = [
    "OUTCOME_ERROR",
    "OUTCOME_NONE",
    "FixChecksRound",
    "FixDue",
    "fix_args",
    "fix_checks_deadline",
    "fix_unit",
    "result_of",
    "run_fix_checks_round",
]
