"""The stage Job: the stage job of one item in a pod of its own (#5483, #4559).

`devops roadmap stage --job-item <n> --confirm` runs this entry point in the pod of a Job from
CronJob `roadmap-stage`. A rollout of the Service then does not stop the plan. The Job plans and
publishes with the code of the Service, the parts of `plan_stage` and `StageWriter`, and holds no
git write of its own. It runs on the phases `prepare`, `agent` and `publish` of one run folder
(`stage_job_phases.py`, #6813): `run_stage_job` runs the three in one process (`--phase all`, the
default), and `prepare_stage_job`, `run_stage_agent` and `publish_stage_job` run one phase each
(`--phase`, `--work`). The agent phase refuses to start with the App key, a GitHub token or a gh
login, and hands over only what the model made; `publish` builds the result from the state of
`prepare`. A SIGTERM in the agent phase exits with the status of its class, with no check-in: the
Service checks in for the Job. The pod:

- holds one model call slot (`set_model_call_limit(1)`), as the model tier of the Service serves;
- counts each GitHub request in a budget of its own: `roadmap.stage.github_requests_per_hour` in
  any one hour (`RequestBudget` through `set_request_gate`), until the shared budget (#4563);
- plans in a time budget: `roadmap.stage.time_budget_seconds`, cut to the deadline of the Job less
  `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS`, so a tool call ends before the plan and the plan ends
  before the deadline of the Job;
- makes the first SIGTERM a kill with a class (`sigterm_raises`, `attempt_kill.py`);
- refuses to run, before a clone or a model call, when it acts as the GitHub App with a token that
  is not limited to its repository (`service.github_app.token_repository`), as the implement
  runner does (#2667). A person who runs it with their own token runs it locally.

The selection is the selection of a round, narrowed to the item: an item with a rejected plan, in
the wait of its failure class or with a recorded split stays out, with the reason of a round. The
plan reads and writes the item alone: its rejection, its orphan and its result.

**Check-out and check-in.** Before the Service creates the Job, it writes the check-out on the item:
`stage.job`, `stage.job_at` and `stage.job_deadline`, with the claim `owner/service`. At its end
the Job checks in: it writes `stage.job_result`, clears the check-out and releases the claim in one
write, only when `stage.job` names this Job (`roadmap.stage.job`). A Job that no check-out names,
such as a Job that a person starts, writes no check-in. The stage row of the Service checks in for
a Job that ended with no check-in (`stage_submit.py`, #4559).

**Ends that fail.** A `deadline` end, and an end that the Service recovers as `failed` or as an
eviction past the free ones, record the failure marks, and the item waits for the wait of its
class. Only an end whose class points at the size of the plan (`SPLIT_CLASSES`: `timeout` and
`plan_defect`) counts toward `roadmap.stage.plan_defect_limit` on one body, as a refused plan does.
The end that reaches the limit returns the item to New with a comment that asks refine to split it:
a plan that keeps failing is too large for one Job (owner rule, 2026-11-13). An outage of the
provider, of GitHub or of the cluster does not count: a split does not help it.

**The result line.** The actor that writes the check-in of an attempt writes its result line
(`roadmap/job_result.py`), so each attempt counts once in the job grades (#5556). The Job logs the
line of its item after its check-in, and only when the check-in found its check-out, or when no
check-out named the Job at its start: a Job that a person starts, with or without a Job name, is
an attempt that the Service does not know. When the check-in finds no check-out of a Job that the
Service knows, the Service ended the attempt and wrote the line of a failed end. When the check-in
fails, the check-out stays, and the Service checks in for the `failed` end and writes its line; an
item that holds its draft then ends `succeeded`, and no actor writes a line. The line goes to
stderr as plain text (`devops roadmap stage --job-item`). `devops_cli_roadmap_stage_total` counts
the item before the check-in, as a round does.

**A published item.** An item whose record holds its draft (`stage.pr`) at the check-in was
published by this Job before its end, such as a pod that a SIGTERM ended during the check-in write.
Its end is `succeeded`, with no failure.

**Ends.** The exit code of the command is the end of the Job:

- 0 (`result`): the item has a result: staged, needs_split or skipped.
- 1 (`failure`): the plan or a write of the item failed with a non-retryable failure, or the provider key was refused. The writer records the failure.
- 75 (`evicted`): a failure whose class a retry can help (such as `provider` or `ci_infra`), or SIGTERM before the time budget ends, from an eviction, a node drain or a person. The check-out stays, and the pod failure policy of the Job runs the pod again. The check-out names the Job, so that pod removes the branch of the intent mark of the pod before it at once, and plans the item again.
- 143 (`deadline`): SIGTERM after the time budget, or a time budget that ends before a model call.
  The Job records the failure with the class `timeout` and checks in with the result `deadline`.

The planner run tool (ADR 0018) has no wiring in a plan run, so the stage Job has none.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import AwareDatetime, BaseModel, ConfigDict

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.client.network import set_model_call_limit
from devops_cli.config.constants import (
    CONST_ROADMAP_OWNER_SERVICE,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import (
    acts_as_github_app,
    finds_github_login,
    held_github_credentials,
)
from devops_cli.exceptions import DevOpsCLIError, RoadmapStageError, RoadmapTimeBudgetError
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.github.rate_limiter import set_request_gate
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled, kill_of, sigterm_raises
from devops_cli.roadmap.claim import service_release
from devops_cli.roadmap.failure import (
    ACTION_BY_CLASS,
    FailureAction,
    FailureClass,
    StepName,
    failure_class_of,
)
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.return_item import apply_return, plan_return
from devops_cli.roadmap.round_log import log_failed_item
from devops_cli.roadmap.stage.stage import (
    StageApplied,
    StagePlan,
    StageResult,
    StageWriter,
    emit_stage_results,
    log_stage_attempts,
    plan_defects,
    stage_results,
)
from devops_cli.roadmap.stage.stage_job_phases import (
    StageAgentEnd,
    StageAgentOutcome,
    StageJobState,
    agent_stage,
    end_state,
    has_inputs,
    planned_of,
    prepare_stage,
    publish_stage,
    read_stage_outcome,
    read_stage_state,
    staged_commit,
    write_agent_end,
)
from devops_cli.roadmap.stage.stage_phases import check_out_staged, stage_runs
from devops_cli.roadmap.stores.store import Item, RoadmapStore, StageRecordKey
from devops_cli.roadmap.time_budget import TimeBudget
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.server.service import RequestBudget

if TYPE_CHECKING:
    from devops_cli.ai.client import LLMClient
    from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel

logger = logging.getLogger(__name__)

_BUDGET_SETTING: Final[str] = "roadmap.stage.time_budget_seconds"
# The result of the check-in of a Job that the deadline ended.
DEADLINE_RESULT: Final[str] = "deadline"
_FAILED: Final[frozenset[StageResult]] = frozenset({StageResult.FAILED, StageResult.DEGENERATE})
# The classes of an end that point at the size of the plan, so they count toward the split.
SPLIT_CLASSES: Final[frozenset[FailureClass]] = frozenset(
    {FailureClass.TIMEOUT, FailureClass.PLAN_DEFECT}
)


class StageJobEnd(StrEnum):
    """How the stage row of the Service found a Job that ended with no check-in (#4559): gone
    from the cluster, ended by its deadline, failed, or succeeded with a lost check-in."""

    EVICTED = "evicted"
    DEADLINE = "deadline"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class StageJobExit(IntEnum):
    """The exit code of a stage Job, as the module says."""

    RESULT = 0
    FAILURE = 1
    EVICTED = 75
    DEADLINE = 143


class JobCheckIn(BaseModel):
    """The record `stage.job_result`: the Job that checked in, its result and the time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job: str
    result: str
    time: AwareDatetime

    @property
    def record(self) -> str:
        """The value of `stage.job_result`."""
        return self.model_dump_json()


def recorded_check_in(item: Item) -> JobCheckIn | None:
    """The check-in that the job record of `item` holds, or None when it holds none. A record that
    is no check-in is logged and read as none."""
    recorded = item.job_record.get(StageRecordKey.JOB_RESULT)
    if not recorded:
        return None
    try:
        return JobCheckIn.model_validate_json(recorded)
    except ValueError:
        logger.warning("The stage Job result recorded on #%d is not a check-in.", item.number)
        return None


@dataclass(frozen=True)
class CheckedIn:
    """What a check-in wrote: the result of the Job, and the class of the failure that its end
    counts as, or None for an end that is no failure."""

    result: str
    failure: FailureClass | None = None


@dataclass(frozen=True)
class StageJobRun:
    """How a stage Job ended: its exit code, its result, the request budget of the pod, the class
    of a kill, and the plan and the writes when the plan ended."""

    exit_code: StageJobExit
    result: str
    budget: RequestBudget
    kill: AttemptKill | None = None
    plan: StagePlan | None = None
    applied: StageApplied | None = None


def job_time_budget(seconds: int, deadline: datetime | None, now: datetime) -> int:
    """The seconds of the time budget of a stage Job at `now`: `seconds`, cut to the `deadline`
    of the Job less `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS`, and 0 when no time is left. The
    deadline counts across the pods of the Job, so a pod that runs again gets the time that is
    left."""
    if deadline is None:
        return seconds
    left = int((deadline - now).total_seconds()) - CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS
    return max(0, min(seconds, left))


def require_job_token_scope(repo: str) -> None:
    """Raise `RoadmapStageError` when the process acts as the GitHub App and its token is not
    limited to `repo` by `service.github_app.token_repository`: a Job that sets no such repository,
    or another one, would plan with a token for every repository of the installation (#2667). A
    process that does not act as the App uses the token of its person, and passes."""
    if not acts_as_github_app():
        return
    scoped = load_settings().service.github_app.token_repository
    if (scoped or "").casefold() != repo.casefold():
        raise RoadmapStageError(
            MESSAGES.roadmap.stage_job_token_scope_refused.format(
                repo=repo, scoped=scoped or "unset"
            )
        )


def install_request_budget(limit: int) -> RequestBudget:
    """Make every GitHub request of the process take a place in a budget of `limit` requests in
    any one hour, and return the budget. A request that the hour has no room for waits."""
    budget = RequestBudget(lambda: datetime.now(UTC), limit)
    set_request_gate(budget.admit, budget.refund)
    return budget


def _retries(failure: FailureClass | None) -> bool:
    """Whether the failure class is retried by default: true when the failure is not None and
    ACTION_BY_CLASS[failure] is FailureAction.RETRY."""
    return failure is not None and ACTION_BY_CLASS.get(failure) is FailureAction.RETRY


def _attempt_failure(plan: StagePlan, applied: StageApplied, number: int) -> FailureClass | None:
    """The class of the entry of `plan.failed` and `applied.failed` whose number is `number`,
    else None."""
    for failure in (*plan.failed, *applied.failed):
        if failure.number == number:
            return failure.failure_class
    return None


def check_in(
    store: RoadmapStore,
    number: int,
    *,
    repo: str,
    job: str | None,
    result: str,
    now: datetime,
    failure: FailureClass | None = None,
    marks: dict[StageRecordKey, str | None] | None = None,
    log_line: bool = True,
) -> CheckedIn | None:
    """Write the check-in of the Job `job` on item `number`: its result and `marks`, with the
    check-out cleared and the claim of the Service released, in one write, and return what it
    wrote. With `failure`, the end fails: the check-in records the failure marks and logs the
    result line of the attempt, and a class of `SPLIT_CLASSES` counts toward
    `roadmap.stage.plan_defect_limit`, where the end that reaches the limit returns the item to New.
    An item that holds its draft was published by the Job: the end is `succeeded`, with no failure
    and no `marks`. Nothing is written, and the answer is None, when no check-out names the Job, as
    the item reads now."""
    if job is None:
        return None
    item = store.item(number)
    if item is None or item.job_record.get(StageRecordKey.JOB) != job:
        return None
    if item.job_record.get(StageRecordKey.PR) and (
        failure is not None or result == StageJobEnd.EVICTED
    ):
        result, failure, marks = StageJobEnd.SUCCEEDED.value, None, None
    written: dict[StageRecordKey, str | None] = {
        StageRecordKey.JOB_RESULT: JobCheckIn(job=job, result=result, time=now).record,
        StageRecordKey.JOB: None,
        StageRecordKey.JOB_AT: None,
        StageRecordKey.JOB_DEADLINE: None,
        **(marks or {}),
    }
    if failure is None:
        service_release(store, number, written)
        return CheckedIn(result)
    written |= {
        StageRecordKey.FAILED_AT: now.isoformat(),
        StageRecordKey.FAILED_ERROR: result,
        StageRecordKey.FAILED_STEP: StepName.PLAN.value,
        StageRecordKey.FAILED_CLASS: failure.value,
    }
    count, body = plan_defects(item)
    limit = load_settings().roadmap.stage.plan_defect_limit
    if failure in SPLIT_CLASSES and count >= limit:
        _return_for_split(store, repo, item, result, count, limit, written)
    else:
        if failure in SPLIT_CLASSES:
            written |= {
                StageRecordKey.PLAN_DEFECTS: str(count),
                StageRecordKey.PLAN_DEFECTS_BODY: body,
            }
        service_release(store, number, written)
    if log_line:
        log_job_result(RoadmapJob.STAGE, repo, number, StageResult.FAILED.value, failure=failure)
    return CheckedIn(result, failure)


def _return_for_split(
    store: RoadmapStore,
    repo: str,
    item: Item,
    result: str,
    count: int,
    limit: int,
    marks: dict[StageRecordKey, str | None],
) -> None:
    """Return `item` to New after the `count`th counted end on one body, at `limit`: post the
    comment that asks refine to split it, set New with `marks` and no count, then release the
    claim of the Service. The comment goes first, so a failed write never leaves a return that no
    one was told about. The item is too large for one plan, so it is divided, not tried again."""
    comment = (
        f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n\n"
        + MESSAGES.roadmap.stage_returned_job_ends.format(result=result, count=count, limit=limit)
    )
    apply_return(
        store,
        plan_return(
            store,
            item.number,
            comment,
            repo,
            marks={
                **marks,
                StageRecordKey.PLAN_DEFECTS: None,
                StageRecordKey.PLAN_DEFECTS_BODY: None,
            },
        ),
    )
    held = store.item(item.number)
    if held is not None and held.owner == CONST_ROADMAP_OWNER_SERVICE:
        service_release(store, item.number, {})


def _deadline_end(
    store: RoadmapStore,
    repo: str,
    number: int,
    job: str | None,
    budget: RequestBudget,
    kill: AttemptKill | None,
    now: datetime | None,
    *,
    known: bool,
) -> StageJobRun:
    """Check in with the failure of a Job that the deadline ended. The end counts. A Job that
    the Service does not know (`known` False) has no check-in, so it logs its result line."""
    at = now or datetime.now(UTC)
    written = check_in(
        store,
        number,
        repo=repo,
        job=job,
        result=DEADLINE_RESULT,
        now=at,
        failure=FailureClass.TIMEOUT,
    )
    if written is None and not known:
        log_job_result(
            RoadmapJob.STAGE, repo, number, StageResult.FAILED.value, failure=FailureClass.TIMEOUT
        )
    return StageJobRun(StageJobExit.DEADLINE, DEADLINE_RESULT, budget, kill=kill)


def _known(store: RoadmapStore, number: int, job: str | None) -> bool:
    """Whether the check-out of item `number` names the Job `job` at the start of the Job. The
    Service knows only the attempt of such a Job: it recovers that attempt and writes its line
    when the Job does not check in. A Job that a person starts has no check-out."""
    if job is None:
        return False
    held = store.item(number)
    return held is not None and held.job_record.get(StageRecordKey.JOB) == job


def _clone(repo: str) -> Path:
    """The blobless clone of `repo` in the clone directory `clone` of the pod. The roadmap run
    imports the stage row, which imports this module, so the run is imported here."""
    from devops_cli.roadmap.run import status_clone

    return status_clone(repo, blobless=True)


def _failed_end(
    store: RoadmapStore,
    repo: str,
    item: int,
    job: str | None,
    budget: RequestBudget,
    failure: FailureClass | None,
    *,
    known: bool,
) -> StageJobRun | None:
    """Log the result line of a project error of class `failure` during planning, and give the
    evicted run when the class is retried; None when the caller raises the error."""
    if not known or _known(store, item, job):
        log_job_result(RoadmapJob.STAGE, repo, item, StageResult.FAILED.value, failure=failure)
    if _retries(failure):
        return StageJobRun(StageJobExit.EVICTED, StageResult.FAILED.value, budget)
    return None


def _handle_stage_cli_error(
    exc: DevOpsCLIError,
    store: RoadmapStore,
    repo: str,
    item: int,
    job: str | None,
    budget: RequestBudget,
    *,
    known: bool,
) -> StageJobRun:
    """Handle a project error during planning: log its result line and return an evicted run if
    the class is retryable, else re-raise."""
    run = _failed_end(store, repo, item, job, budget, failure_class_of(exc), known=known)
    if run is not None:
        return run
    raise exc


def _finish_stage_job(
    store: RoadmapStore,
    *,
    repo: str,
    item: int,
    job: str | None,
    budget: RequestBudget,
    plan: StagePlan,
    applied: StageApplied,
    now: datetime | None,
    known: bool,
) -> StageJobRun:
    """Complete a stage Job run: record failure telemetry, check in if not retried, and log the
    attempt result lines."""
    emit_stage_results(plan, applied, repo=repo, attempt_lines=False)
    for failure in (*plan.failed, *applied.failed):
        log_failed_item(repo, failure.number, failure.step.value, failure.failure_class.value)
    result = stage_results(plan, applied).get(item, StageResult.SKIPPED)
    failure_class = _attempt_failure(plan, applied, item)
    if _retries(failure_class):
        if not known or _known(store, item, job):
            log_stage_attempts(plan, applied, repo=repo)
        return StageJobRun(StageJobExit.EVICTED, result.value, budget, plan=plan, applied=applied)
    at = now or datetime.now(UTC)
    written = check_in(store, item, repo=repo, job=job, result=result.value, now=at)
    if written is not None or not known:
        log_stage_attempts(plan, applied, repo=repo)
    exit_code = StageJobExit.FAILURE if result in _FAILED else StageJobExit.RESULT
    return StageJobRun(exit_code, result.value, budget, plan=plan, applied=applied)


@dataclass(frozen=True)
class _Attempt:
    """What the ends of an attempt of the stage Job need: the store, the item and its repository,
    the Job, the request budget of the pod, the time budget, the time of the records, and whether
    the check-out named the Job at its start."""

    store: RoadmapStore
    repo: str
    item: int
    job: str | None
    budget: RequestBudget
    time_budget: TimeBudget
    now: datetime | None
    known: bool

    def guarded[T](self, work: Callable[[], T]) -> T | StageJobRun:
        """The answer of `work`, with the first SIGTERM a kill, or the end of the Job that the
        kill or the error of `work` gives: an eviction, the deadline, or the end of a project
        error. A refused key of the provider and any other error raise."""
        try:
            with sigterm_raises():
                return work()
        except AttemptKilled as killed:
            kill = kill_of(self.time_budget, killed)
            if kill is AttemptKill.EVICTED:
                return StageJobRun(StageJobExit.EVICTED, kill.value, self.budget, kill=kill)
            return self.deadline(kill)
        except RoadmapTimeBudgetError:
            return self.deadline()
        except AICredentialsError:
            raise
        except DevOpsCLIError as exc:
            return _handle_stage_cli_error(
                exc, self.store, self.repo, self.item, self.job, self.budget, known=self.known
            )

    def deadline(self, kill: AttemptKill | None = None) -> StageJobRun:
        """The check-in of the Job that the deadline ended."""
        return _deadline_end(
            self.store,
            self.repo,
            self.item,
            self.job,
            self.budget,
            kill,
            self.now,
            known=self.known,
        )

    def finish(self, plan: StagePlan, applied: StageApplied) -> StageJobRun:
        """The end of the Job with the plan `plan` and the writes `applied`."""
        return _finish_stage_job(
            self.store,
            repo=self.repo,
            item=self.item,
            job=self.job,
            budget=self.budget,
            plan=plan,
            applied=applied,
            now=self.now,
            known=self.known,
        )


def _start(
    store: RoadmapStore, repo: str, item: int, now: datetime | None
) -> _Attempt | StageJobRun:
    """The start of a phase that acts as the App: the scope of the token, the request budget,
    whether the check-out names the Job, and the time budget, or the deadline end when no time is
    left. Raises `RoadmapStageError` when the token of the App is not limited to `repo`."""
    require_job_token_scope(repo)
    settings = load_settings().roadmap.stage
    budget = install_request_budget(settings.github_requests_per_hour)
    known = _known(store, item, settings.job)
    seconds = job_time_budget(
        settings.time_budget_seconds, settings.job_deadline, now or datetime.now(UTC)
    )
    attempt = _Attempt(
        store,
        repo,
        item,
        settings.job,
        budget,
        TimeBudget.start(max(seconds, 0), _BUDGET_SETTING),
        now,
        known,
    )
    return attempt if seconds > 0 else attempt.deadline()


def _source(repo: str, source: Path | str | None) -> Path:
    return Path(source) if source is not None else _clone(repo)


def _staged_source(repo: str, source: Path | str | None, state: StageJobState) -> Path:
    """The clone of the Job at the staged commit of `state`, on which a `publish` of its own builds
    the plan, as the planner read it."""
    clone = _source(repo, source)
    check_out_staged(clone, staged_commit(state))
    return clone


def run_stage_job(
    store: RoadmapStore,
    *,
    repo: str,
    item: int,
    source: Path | str | None = None,
    model: LLMClient | ToolboxModel | None = None,
    verifier: ToolboxModel | None = None,
    now: datetime | None = None,
) -> StageJobRun:
    """Plan and publish item `item` of `repo` as one stage Job, as the module says: the three
    phases of `stage_job_phases` in one process (`--phase all`), on a new run folder that goes
    when the Job ends. `source` is a clone to work in; without it, the Job makes a blobless clone.
    `model` and `verifier` are the models of `plan_stage`. `now` is the time of the records, the
    time of the system without it.

    Raises `RoadmapStageError` before any clone or request when the token of the App is not
    limited to `repo`, `AICredentialsError` when credentials are refused, the errors of
    `plan_stage` that no item explains, and the errors of the check-in.
    """
    started = _start(store, repo, item, now)
    if isinstance(started, StageJobRun):
        return started
    set_model_call_limit(1)

    def work() -> tuple[StagePlan, StageApplied]:
        with tempfile.TemporaryDirectory(prefix="devops-stage-job-", dir=stage_runs()) as root:
            folders = RunFolders(Path(root)).make()
            clone = _source(repo, source)
            writer = StageWriter(store, clone, now=now)
            prepared = prepare_stage(
                store,
                writer,
                folders,
                repo=repo,
                item=item,
                source=clone,
                job=started.job,
                known=started.known,
                now=now,
            )
            if isinstance(prepared, StagePlan):
                return prepared, writer.applied()
            agent_stage(folders, model=model, verifier=verifier, time_budget=started.time_budget)
            planned = planned_of(read_stage_outcome(folders), prepared, checkout=clone)
            return publish_stage(store, prepared, planned, source=clone, now=now)

    done = started.guarded(work)
    if isinstance(done, StageJobRun):
        return done
    return started.finish(*done)


def prepare_stage_job(
    store: RoadmapStore,
    folders: RunFolders,
    *,
    repo: str,
    item: int,
    source: Path | str | None = None,
    now: datetime | None = None,
) -> StageJobRun | None:
    """`--phase prepare` of item `item` of `repo` on the run folder `folders` (#6813): None when
    the agent phase plans the item next, or the end of a Job that `prepare` ended, which the state
    file records for `publish`."""
    folders.make()
    settings = load_settings().roadmap.stage

    def ended(run: StageJobRun) -> StageJobRun:
        end_state(
            folders,
            repo=repo,
            item=item,
            job=settings.job,
            end=int(run.exit_code),
            result=run.result,
        )
        return run

    started = _start(store, repo, item, now)
    if isinstance(started, StageJobRun):
        return ended(started)

    def work() -> tuple[StagePlan, StageApplied] | StageJobState:
        clone = _source(repo, source)
        writer = StageWriter(store, clone, now=now)
        prepared = prepare_stage(
            store,
            writer,
            folders,
            repo=repo,
            item=item,
            source=clone,
            job=started.job,
            known=started.known,
            now=now,
        )
        return prepared if isinstance(prepared, StageJobState) else (prepared, writer.applied())

    done = started.guarded(work)
    if isinstance(done, StageJobState):
        return None
    if isinstance(done, StageJobRun):
        return ended(done)
    return ended(started.finish(*done))


def run_stage_agent(
    folders: RunFolders,
    *,
    model: LLMClient | ToolboxModel | None = None,
    verifier: ToolboxModel | None = None,
    now: datetime | None = None,
) -> None:
    """`--phase agent` on the run folder `folders` (#6813): plan the item that `prepare` handed on,
    and write the outcome for `publish`. The phase holds the model key only, so it refuses to start
    with the App key or a GitHub token, as the agent phase of the implement job does
    (`require_agent_runner`), and with a gh login that the token lookup of the session finds. It
    reads no store. The end of the time budget and an error that
    the planner makes into no result are outcomes too. Raises `RoadmapStageError` for a credential
    of GitHub, `PhaseOutputError` for an output folder that is there already, `AICredentialsError`
    when the provider refuses the key, and `AttemptKilled` with its class for a SIGTERM."""
    if held := held_github_credentials():
        raise RoadmapStageError(
            MESSAGES.roadmap.stage_agent_phase_key_refused.format(names=", ".join(held))
        )
    if finds_github_login():
        raise RoadmapStageError(MESSAGES.roadmap.stage_agent_phase_login_refused)
    if not has_inputs(folders):
        return
    settings = load_settings().roadmap.stage
    set_model_call_limit(1)
    seconds = job_time_budget(
        settings.time_budget_seconds, settings.job_deadline, now or datetime.now(UTC)
    )
    if seconds <= 0:
        folders.make_out()
        write_agent_end(folders, StageAgentOutcome(end=StageAgentEnd.DEADLINE))
        return
    time_budget = TimeBudget.start(seconds, _BUDGET_SETTING)
    try:
        with sigterm_raises():
            agent_stage(folders, model=model, verifier=verifier, time_budget=time_budget)
    except AttemptKilled as killed:
        raise AttemptKilled(kill_of(time_budget, killed)) from None
    except RoadmapTimeBudgetError:
        write_agent_end(folders, StageAgentOutcome(end=StageAgentEnd.DEADLINE))
    except AICredentialsError, PhaseOutputError:
        raise
    except DevOpsCLIError as exc:
        outcome = StageAgentOutcome(
            end=StageAgentEnd.FAILED, error=mask_secrets(str(exc)), failure=failure_class_of(exc)
        )
        write_agent_end(folders, outcome)


def publish_stage_job(
    store: RoadmapStore,
    folders: RunFolders,
    *,
    repo: str,
    item: int,
    source: Path | str | None = None,
    now: datetime | None = None,
) -> StageJobRun:
    """`--phase publish` of item `item` of `repo` on the run folder `folders` (#6813): the state
    file and the outcome of the agent phase, read as data, give the end of the Job. A run that
    `prepare` ended gets its end and no write. Raises `PhaseOutputError` for a file of the run that
    is not data of its model, and `RoadmapStageError` for an error of the agent phase that no retry
    helps."""
    require_job_token_scope(repo)
    state = read_stage_state(folders, repo=repo, item=item)
    settings = load_settings().roadmap.stage
    budget = install_request_budget(settings.github_requests_per_hour)
    if state.end is not None:
        return StageJobRun(StageJobExit(state.end), state.result, budget)
    outcome = read_stage_outcome(folders)
    seconds = job_time_budget(
        settings.time_budget_seconds, settings.job_deadline, now or datetime.now(UTC)
    )
    attempt = _Attempt(
        store,
        repo,
        item,
        state.job,
        budget,
        TimeBudget.start(max(seconds, 0), _BUDGET_SETTING),
        now,
        state.known,
    )
    if outcome.end is StageAgentEnd.DEADLINE:
        return attempt.deadline()
    if outcome.end is StageAgentEnd.FAILED:
        run = _failed_end(store, repo, item, state.job, budget, outcome.failure, known=state.known)
        if run is not None:
            return run
        raise RoadmapStageError(outcome.error, failed_items=[item])
    clone = attempt.guarded(lambda: _staged_source(repo, source, state))
    if isinstance(clone, StageJobRun):
        return clone
    # A check that refuses the plan raises: no retry of the pod builds another plan from it.
    planned = planned_of(outcome, state, checkout=clone)
    done = attempt.guarded(lambda: publish_stage(store, state, planned, source=clone, now=now))
    if isinstance(done, StageJobRun):
        return done
    return attempt.finish(*done)


__all__ = [
    "DEADLINE_RESULT",
    "SPLIT_CLASSES",
    "CheckedIn",
    "JobCheckIn",
    "StageJobEnd",
    "StageJobExit",
    "StageJobRun",
    "check_in",
    "install_request_budget",
    "job_time_budget",
    "prepare_stage_job",
    "publish_stage_job",
    "recorded_check_in",
    "require_job_token_scope",
    "run_stage_agent",
    "run_stage_job",
]
