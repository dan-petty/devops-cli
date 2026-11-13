"""The stage Job: the stage job of one item in a pod of its own (#5483, #4559).

`devops roadmap stage --job-item <n> --confirm` runs this entry point in the pod of a Job from
CronJob `roadmap-stage`. A rollout of the Service then does not stop the plan. The Job plans and
publishes with the code of the Service, `plan_stage` and `StageWriter`, and holds no git write of
its own. The pod:

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
`stage.job`, `stage.job_at` and `stage.job_deadline`. At its end the Job checks in: it writes
`stage.job_result` and clears the check-out in one write, only when `stage.job` names this Job
(`roadmap.stage.job`). A Job that no check-out names, such as a Job that a person starts, writes
no check-in.

**Ends.** The exit code of the command is the end of the Job:

- 0 (`result`): the item has a result: staged, needs_split or skipped.
- 1 (`failure`): the plan or a write of the item failed. The writer records the failure.
- 75 (`evicted`): SIGTERM before the time budget ends, from an eviction, a node drain or a person.
  The check-out stays, and the pod failure policy of the Job runs the pod again. The check-out
  names the Job, so that pod removes the branch of the intent mark of the pod before it at once,
  and plans the item again.
- 143 (`deadline`): SIGTERM after the time budget, or a time budget that ends before a model call.
  The Job records the failure with the class `timeout` and checks in with the result `deadline`.

The planner run tool (ADR 0018) has no wiring in a plan run, so the stage Job has none.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import AwareDatetime, BaseModel, ConfigDict

from devops_cli.ai.client.network import set_model_call_limit
from devops_cli.config.constants import CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS
from devops_cli.config.settings import load_settings
from devops_cli.core.process import acts_as_github_app
from devops_cli.exceptions import RoadmapStageError, RoadmapTimeBudgetError
from devops_cli.github.rate_limiter import set_request_gate
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled, kill_of, sigterm_raises
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.round_log import log_failed_item
from devops_cli.roadmap.run import model_clone
from devops_cli.roadmap.stage.stage import (
    StageApplied,
    StagePlan,
    StageResult,
    StageWriter,
    emit_stage_results,
    parse_filters,
    plan_stage,
    stage_results,
)
from devops_cli.roadmap.stores.store import Item, RoadmapStore, StageRecordKey
from devops_cli.roadmap.time_budget import TimeBudget
from devops_cli.server.service import RequestBudget

if TYPE_CHECKING:
    from devops_cli.ai.client import LLMClient
    from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel

logger = logging.getLogger(__name__)

_BUDGET_SETTING: Final[str] = "roadmap.stage.time_budget_seconds"
# The result of the check-in of a Job that the deadline ended.
DEADLINE_RESULT: Final[str] = "deadline"
_FAILED: Final[frozenset[StageResult]] = frozenset({StageResult.FAILED, StageResult.DEGENERATE})


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


def check_in(
    store: RoadmapStore,
    number: int,
    *,
    job: str | None,
    result: str,
    now: datetime,
    marks: dict[StageRecordKey, str] | None = None,
) -> bool:
    """Write the check-in of the Job `job` on item `number`: its result and `marks`, with the
    check-out cleared, in one write. Nothing is written, and the answer is False, when no
    check-out names the Job."""
    if job is None:
        return False
    item = store.item(number)
    if item is None or item.job_record.get(StageRecordKey.JOB) != job:
        return False
    store.set_marks(
        item,
        {
            StageRecordKey.JOB_RESULT: JobCheckIn(job=job, result=result, time=now).record,
            StageRecordKey.JOB: None,
            StageRecordKey.JOB_AT: None,
            StageRecordKey.JOB_DEADLINE: None,
            **(marks or {}),
        },
    )
    return True


def _deadline_end(
    store: RoadmapStore,
    number: int,
    job: str | None,
    budget: RequestBudget,
    kill: AttemptKill | None,
    now: datetime | None,
) -> StageJobRun:
    """Record the failure of a Job that the deadline ended and check in."""
    at = now or datetime.now(UTC)
    marks = {
        StageRecordKey.FAILED_AT: at.isoformat(),
        StageRecordKey.FAILED_ERROR: DEADLINE_RESULT,
        StageRecordKey.FAILED_STEP: StepName.PLAN.value,
        StageRecordKey.FAILED_CLASS: FailureClass.TIMEOUT.value,
    }
    check_in(store, number, job=job, result=DEADLINE_RESULT, now=at, marks=marks)
    return StageJobRun(StageJobExit.DEADLINE, DEADLINE_RESULT, budget, kill=kill)


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
    """Plan and publish item `item` of `repo` as one stage Job, as the module says. `source` is a
    clone to work in; without it, the Job makes a blobless clone. `model` and `verifier` are the
    models of `plan_stage`. `now` is the time of the records, the time of the system without it.

    Raises `RoadmapStageError` before any clone or request when the token of the App is not
    limited to `repo`, the errors of `plan_stage` that no item explains, and the errors of the
    check-in.
    """
    require_job_token_scope(repo)
    settings = load_settings().roadmap.stage
    set_model_call_limit(1)
    budget = install_request_budget(settings.github_requests_per_hour)
    seconds = job_time_budget(
        settings.time_budget_seconds, settings.job_deadline, now or datetime.now(UTC)
    )
    if seconds <= 0:
        return _deadline_end(store, item, settings.job, budget, None, now)
    time_budget = TimeBudget.start(seconds, _BUDGET_SETTING)
    try:
        with sigterm_raises():
            clone = Path(source) if source is not None else model_clone(repo, blobless=True)
            writer = StageWriter(store, clone, now=now)
            plan = plan_stage(
                store,
                repo=repo,
                source=clone,
                filters=parse_filters(()),
                item_number=item,
                model=model,
                verifier=verifier,
                now=now,
                writer=writer,
                named=False,
                job=settings.job,
                time_budget=time_budget,
            )
    except AttemptKilled as killed:
        kill = kill_of(time_budget, killed)
        if kill is AttemptKill.EVICTED:
            return StageJobRun(StageJobExit.EVICTED, kill.value, budget, kill=kill)
        return _deadline_end(store, item, settings.job, budget, kill, now)
    except RoadmapTimeBudgetError:
        return _deadline_end(store, item, settings.job, budget, None, now)
    applied = writer.applied()
    emit_stage_results(plan, applied, repo=repo)
    for failure in (*plan.failed, *applied.failed):
        log_failed_item(repo, failure.number, failure.step.value, failure.failure_class.value)
    result = stage_results(plan, applied).get(item, StageResult.SKIPPED)
    check_in(store, item, job=settings.job, result=result.value, now=now or datetime.now(UTC))
    exit_code = StageJobExit.FAILURE if result in _FAILED else StageJobExit.RESULT
    return StageJobRun(exit_code, result.value, budget, plan=plan, applied=applied)


__all__ = [
    "DEADLINE_RESULT",
    "JobCheckIn",
    "StageJobExit",
    "StageJobRun",
    "check_in",
    "install_request_budget",
    "job_time_budget",
    "recorded_check_in",
    "require_job_token_scope",
    "run_stage_job",
]
