"""The stage Job on the phases `prepare`, `agent` and `publish` of one run folder (#6705).

`devops roadmap stage --job-item <n> --confirm --phase <phase> --work <folder>` runs one phase. The
default phase `all` runs `run_stage_job` (`stage_job.py`) in one process, with no run file, as
CronJob `roadmap-stage` runs it until #6814 gives the Job its three containers.

- `prepare` (App key, no model call) reads the round of the item and makes the writes of
  `StageWriter.begin`. It decides what needs no model: the CI job-time premise, the false premise
  of the body probe and the blocker of an open plan. A failed GitHub read fails the item with the
  class `ci_infra`, as on `main`. A decision that ends the run checks in, and the state file says
  so. Else it makes a full clone at the staged commit (`clone_for_agent`), commits the scaffold of
  the change folder with its own date, and writes the state file and the issue listing in
  `state/`, and the inputs of the agent and a copy of the listing in `work/`.
- `agent` (model key only) runs the stock `Coder` agent of `stage_agent.py` in the clone, and
  writes the patch of the change folder from the base, the body candidate and a `StageOutcome`.
- `publish` (App key) reads the state file and the outputs of the agent as data, and decides
  each end with its own checks, as `publish_stage_job` says.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, NonNegativeInt, ValidationError
from pydantic_ai import capture_run_messages
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.client.models import AIClientError, AICredentialsError, spend_limit_error
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_GITHUB_AGENT_REFUSED_ENV,
    CONST_GITHUB_COMMENT_MAX_CHARS,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_PATCH_MAX_BYTES,
    CONST_ROADMAP_PHASE_STATE_FILE,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_STAGE_CANDIDATE_FILE,
    CONST_ROADMAP_STAGE_CANDIDATE_OUT_FILE,
    CONST_ROADMAP_STAGE_ISSUES_FILE,
    CONST_ROADMAP_STAGE_PLAN_PATCH_FILE,
)
from devops_cli.config.settings import RoadmapStageConfig, get_active_config_path, load_settings
from devops_cli.core import clock
from devops_cli.core.process import finds_github_login
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubOperationError,
    GitOperationError,
    RoadmapStageError,
    RoadmapTimeBudgetError,
)
from devops_cli.exceptions.roadmap import PhaseOutputError, PublishRefusedError
from devops_cli.exceptions.tools import DependencyError, ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.gate import GateCheck, check_openspec
from devops_cli.openspec.scaffold import scaffold_design, scaffold_proposal, scaffold_tasks
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled, kill_of, sigterm_raises
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.item_comments import HeldComment, held_comments
from devops_cli.roadmap.phases.files import RunFolders, read_output, read_run_file, write_json
from devops_cli.roadmap.phases.patch import write_patch
from devops_cli.roadmap.phases.publish import NewTree, git_call, publish_patch
from devops_cli.roadmap.plan_read import PlanReadError, read_change
from devops_cli.roadmap.plan_recheck import ListingIssues, recheck_plans
from devops_cli.roadmap.plan_recheck import PlanResult as RecheckResult
from devops_cli.roadmap.planned import PlannedChanges, open_plan_creates
from devops_cli.roadmap.refine.refine import stage_comment_text
from devops_cli.roadmap.refine.refine_investigation import task_window
from devops_cli.roadmap.stage.stage import (
    ITEM_ERRORS,
    Blocked,
    FalsePremise,
    OverBudget,
    Rejection,
    StageApplied,
    StageAttempt,
    StagedChange,
    StageFailure,
    StagePlan,
    StageTarget,
    StageWriter,
    item_failure,
    job_time_decision,
    openspec_tool,
    parse_filters,
    plan_defects,
    plan_state_text,
    read_stage_round,
)
from devops_cli.roadmap.stage.stage_agent import STAGE_CHECKS, StageRunLog, build_stage_agent
from devops_cli.roadmap.stage.stage_candidate import plan_texts, read_candidate
from devops_cli.roadmap.stage.stage_change import (
    MeasuredGroup,
    body_room,
    measure_groups,
    shared_texts,
)
from devops_cli.roadmap.stage.stage_job import (
    BUDGET_SETTING,
    StageJobExit,
    StageJobRun,
    check_in,
    deadline_end,
    finish_stage_job,
    install_request_budget,
    job_clone,
    job_time_budget,
    known_job,
    require_job_token_scope,
    stage_error_end,
)
from devops_cli.roadmap.stage.stage_phases import clone_at_base, clone_for_agent, target_of
from devops_cli.roadmap.stage.stage_probe import Probe, blocked_by, probe_premise
from devops_cli.roadmap.stage.stage_rejected import reasons_of
from devops_cli.roadmap.stage.stage_validate import validate_change
from devops_cli.roadmap.stores.store import IssueRecord, Item, RoadmapStore, StageRecordKey
from devops_cli.roadmap.time_budget import TimeBudget
from devops_cli.security.sanitizer import mask_secrets, redact_text
from devops_cli.server.service import RequestBudget

_GIT_OPERATION: Final[str] = "roadmap.stage.phases"
_CODER_PROMPT: Final[str] = "roadmap_stage_coder.md"
# The result of the plan of one item, as `StageWriter.settle` writes it.
PlanResult = StagedChange | OverBudget | Blocked | FalsePremise | StageFailure


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageState(_Model):
    """`state/state.json`, which `prepare` writes and only `publish` reads (#6705).

    It holds the repository, the item, the Job that the settings name and whether the check-out
    of the item named it at the start of the Job (`known`). For a run that goes on, it holds the
    target of the item (its branch, its change folder and the draft that a re-stage replaces), the
    base (the staged commit), the lease of the push, the default branch, the date of the change,
    the identity of the commits, the rejection of the item, the paths that the open plans create,
    the end time of the time budget, the GitHub requests that `prepare` sent, and what
    `StageWriter.begin` wrote. `ended` says that a decision of `prepare` ended the run with the
    exit code `end` and `result`: the agent phase then has no inputs, and `publish` writes
    nothing."""

    repo: str
    item: int
    job: str | None = None
    known: bool = False
    ended: bool = False
    end: StageJobExit | None = None
    result: str = ""
    target: StageTarget | None = None
    change: str = ""
    base: str = ""
    lease: str = ""
    default: str = ""
    created: date | None = None
    identity: tuple[str, str] = ("", "")
    rejection: Rejection | None = None
    creates: dict[str, int] = Field(default_factory=dict)
    deadline: AwareDatetime | None = None
    requests: int = 0
    begun: StageApplied = Field(default_factory=StageApplied)


class AgentComment(_Model):
    """One comment of the item that the stage agent reads whole: its number, its author, its time,
    its text with each secret masked, and its page."""

    number: int
    author: str
    at: AwareDatetime
    text: str
    url: str | None = None

    @classmethod
    def of(cls, held: HeldComment) -> AgentComment:
        return cls(number=held.number, author=held.author, at=held.at, text=held.text, url=held.url)


class StageAgentInput(_Model):
    """`work/input.json`, the inputs of the agent phase (#6705): the repository, the item with its
    whole body and each comment, the base, the default branch, the branch, the change folder and
    its date, the lines of the probe of the body, the paths that the open plans create, the reason
    of a rejected plan, the step budget of a group, the room of the body text and the end time of
    the time budget."""

    repo: str
    item: int
    title: str
    url: str
    body: str
    comments: tuple[AgentComment, ...] = ()
    base: str
    default: str
    branch: str
    change: str
    created: date
    probes: tuple[str, ...] = ()
    creates: dict[str, int] = Field(default_factory=dict)
    rejected: str | None = None
    step_tokens: int
    body_room: int
    deadline: AwareDatetime


def _write_state(folders: RunFolders, state: StageState) -> None:
    write_json(folders.state / CONST_ROADMAP_PHASE_STATE_FILE, state)


def _with_result(plan: StagePlan, result: PlanResult, seconds: float) -> StagePlan:
    """`plan`, the plan of the reads, with the `result` of its item and the attempt."""
    number = result.number if isinstance(result, StageFailure) else result.target.item.number
    attempt = StageAttempt(number, seconds=round(seconds))
    plan = replace(plan, attempts=(attempt,))
    if isinstance(result, StageFailure):
        return replace(plan, failed=(*plan.failed, result))
    if isinstance(result, FalsePremise):
        return replace(plan, premise=(result,))
    if isinstance(result, Blocked):
        return replace(plan, blocked=(result,))
    if isinstance(result, OverBudget):
        return replace(plan, over_budget=(result,))
    return replace(plan, ready=(result,))


def issue_listing(store: RoadmapStore, planned: PlannedChanges, item: Item) -> ListingIssues:
    """The issue listing of the recheck of the agent (#6705): the item with its body, then each
    issue that an active change folder of the base names, with its number, its title, its URL and
    its state and no body. The issues are read as the recheck reads them from a store: the open
    Items once, and each other one alone."""
    open_items = {held.number: held for held in store.open_items()}
    records = [
        IssueRecord(
            number=item.number, title=item.title, url=item.url, state=item.state, body=item.body
        )
    ]
    for number in sorted(planned.active):
        if number == item.number:
            continue
        held = open_items.get(number) or store.item(number)
        if held is not None:
            records.append(
                IssueRecord(number=held.number, title=held.title, url=held.url, state=held.state)
            )
    return ListingIssues(tuple(records))


def scaffold_files(change: str, number: int, created: date) -> dict[str, str]:
    """The scaffold of the change folder `change` of item `number`, dated `created`, by path from
    the repository root: each file holds the marker that `devops openspec check` refuses until the
    agent replaces it."""
    root = f"{CONST_OPENSPEC_CHANGES_DIR}/{change}"
    return {
        f"{root}/.openspec.yaml": f"schema: spec-driven\ncreated: {created.isoformat()}\n",
        f"{root}/proposal.md": scaffold_proposal(number),
        f"{root}/design.md": scaffold_design(),
        f"{root}/tasks.md": scaffold_tasks(),
    }


class _Reads:
    """What `prepare` reads for the agent when no decision ends the run."""

    def __init__(
        self, comments: tuple[HeldComment, ...], probe: Probe, creates: dict[str, int]
    ) -> None:
        self.comments = comments
        self.probe = probe
        self.creates = creates


def _decide(
    store: RoadmapStore,
    repo: str,
    clone: Path,
    plan: StagePlan,
    planned: PlannedChanges,
    target: StageTarget,
) -> PlanResult | _Reads:
    """The decision of `prepare` on `target`, or the reads of the agent when none ends the run:
    the CI job-time premise, then the comments of the item, the probe of its body for a false
    premise, and the paths that the open plans create for a blocker, in the order of the planner
    of `--phase all`. A failed read of one of them fails the item, as the planner fails it."""
    decided = job_time_decision(repo, target)
    if decided is not None:
        return decided
    try:
        comments = held_comments(store.comments_on(target.item.number))
        probe = probe_premise(clone, plan.sha, target.item.body)
        if probe.false_premises:
            return FalsePremise(target, probe.false_premises)
        creates = open_plan_creates(store, clone, planned, operation=_GIT_OPERATION)
    except AICredentialsError:
        raise
    except ITEM_ERRORS as exc:
        return item_failure(target, exc)
    paths = tuple(path for path in probe.missing if path in creates)
    if blockers := blocked_by(paths, creates):
        return Blocked(target, blockers, paths)
    return _Reads(comments, probe, creates)


def _rejected_reason(store: RoadmapStore, plan: StagePlan, target: StageTarget) -> str | None:
    """The reason of the rejected plan of `target`, as the plan request of `--phase all` holds it."""
    number = target.item.number
    for found in plan.rejections:
        if found.number == number:
            return stage_comment_text(found.comment)
    return reasons_of(store, [target.item]).get(number)


class _Prepare:
    """One run of `prepare`, as `prepare_stage_job` says."""

    def __init__(
        self,
        store: RoadmapStore,
        folders: RunFolders,
        *,
        repo: str,
        item: int,
        settings: RoadmapStageConfig,
        budget: RequestBudget,
        known: bool,
        deadline: datetime,
        now: datetime | None,
    ) -> None:
        self.store = store
        self.folders = folders
        self.repo = repo
        self.item = item
        self.settings = settings
        self.budget = budget
        self.known = known
        self.deadline = deadline
        self.now = now

    def finish(self, plan: StagePlan, applied: StageApplied) -> StageJobRun:
        return finish_stage_job(
            self.store,
            repo=self.repo,
            item=self.item,
            job=self.settings.job,
            budget=self.budget,
            plan=plan,
            applied=applied,
            now=self.now,
            known=self.known,
        )

    def run(self, clone: Path) -> StageJobRun | None:
        """Read the round in `clone`, decide or hand the run on: the end of a run that a
        decision ended, or None for a run that the agent phase takes."""
        writer = StageWriter(self.store, clone, now=self.now)
        read = read_stage_round(
            self.store,
            repo=self.repo,
            source=clone,
            filters=parse_filters(()),
            limit=self.settings.limit,
            item_number=self.item,
            now=self.now,
            named=False,
            job=self.settings.job,
        )
        plan = replace(read.plan, budget=self.settings.step_tokens)
        writer.begin(plan, {target.item.number for target in read.selected})
        if not read.selected:
            return self.finish(plan, writer.applied())
        target = read.selected[0]
        started = clock.monotonic()
        decided = _decide(self.store, self.repo, clone, plan, read.planned, target)
        if not isinstance(decided, _Reads):
            writer.settle(target, decided)
            plan = _with_result(plan, decided, clock.monotonic() - started)
            return self.finish(plan, writer.applied())
        self.hand_on(clone, plan, read.planned, target, decided, writer.applied())
        return None

    def hand_on(
        self,
        source: Path,
        plan: StagePlan,
        planned: PlannedChanges,
        target: StageTarget,
        reads: _Reads,
        begun: StageApplied,
    ) -> None:
        """Clone at the staged commit, commit the scaffold, and write the state file, the listing
        and the inputs of the agent."""
        number = target.item.number
        identity = (
            git_call(source, "config", "user.name").strip(),
            git_call(source, "config", "user.email").strip(),
        )
        clone = clone_for_agent(
            self.folders.work,
            self.repo,
            issue=number,
            branch=target.branch,
            base=plan.sha,
            identity=identity,
        )
        created = (self.now or datetime.now(UTC)).date()
        for name, text in scaffold_files(target.change, number, created).items():
            (clone.path / name).parent.mkdir(parents=True, exist_ok=True)
            (clone.path / name).write_text(text, encoding="utf-8")
        git_call(clone.path, "add", "--", f"{CONST_OPENSPEC_CHANGES_DIR}/{target.change}")
        git_call(clone.path, "commit", "--quiet", "-m", f"docs(openspec): scaffold #{number}")
        listing = issue_listing(self.store, planned, target.item).dump()
        for folder in (self.folders.state, self.folders.work):
            path = folder / CONST_ROADMAP_STAGE_ISSUES_FILE
            path.write_bytes(listing)
            path.chmod(0o600)
        rejection = next((r for r in plan.rejections if r.number == number), None)
        write_json(
            self.folders.work / CONST_ROADMAP_PHASE_INPUT_FILE,
            StageAgentInput(
                repo=self.repo,
                item=number,
                title=target.item.title,
                url=target.item.url,
                body=target.item.body,
                comments=tuple(AgentComment.of(held) for held in reads.comments),
                base=plan.sha,
                default=planned.default,
                branch=target.branch,
                change=target.change,
                created=created,
                probes=reads.probe.lines,
                creates=reads.creates,
                rejected=_rejected_reason(self.store, plan, target),
                step_tokens=plan.budget,
                body_room=body_room(number, target.change),
                deadline=self.deadline,
            ),
        )
        _write_state(
            self.folders,
            StageState(
                repo=self.repo,
                item=self.item,
                job=self.settings.job,
                known=self.known,
                target=target,
                change=target.change,
                base=plan.sha,
                lease=clone.lease,
                default=planned.default,
                created=created,
                identity=identity,
                rejection=rejection,
                creates=reads.creates,
                deadline=self.deadline,
                requests=self.budget.spent(),
                begun=begun,
            ),
        )


def prepare_stage_job(
    store: RoadmapStore,
    folders: RunFolders,
    *,
    repo: str,
    item: int,
    source: Path | str | None = None,
    now: datetime | None = None,
) -> StageJobRun | None:
    """`prepare` of the stage Job of item `item` of `repo` on the run folder `folders`, as the
    module says. `source` is a clone to read the round in; without it, the Job makes a blobless
    clone. `now` is the time of the records, the time of the system without it.

    The end of the run when a decision of `prepare` ended it, with its check-in and the state
    file that says so, or None when the agent phase takes the run. Raises as `run_stage_job`
    raises."""
    require_job_token_scope(repo)
    settings = load_settings().roadmap.stage
    budget = install_request_budget(settings.github_requests_per_hour)
    known = known_job(store, item, settings.job)
    at = now or datetime.now(UTC)
    seconds = job_time_budget(settings.time_budget_seconds, settings.job_deadline, at)

    def ended(run: StageJobRun) -> StageJobRun:
        _write_state(
            folders,
            StageState(
                repo=repo,
                item=item,
                job=settings.job,
                known=known,
                ended=True,
                end=run.exit_code,
                result=run.result,
                requests=budget.spent(),
            ),
        )
        return run

    if seconds <= 0:
        return ended(deadline_end(store, repo, item, settings.job, budget, None, now, known=known))
    time_budget = TimeBudget.start(seconds, BUDGET_SETTING)
    prepare = _Prepare(
        store,
        folders,
        repo=repo,
        item=item,
        settings=settings,
        budget=budget,
        known=known,
        deadline=at + timedelta(seconds=seconds),
        now=now,
    )
    try:
        with sigterm_raises():
            run = prepare.run(Path(source) if source is not None else job_clone(repo))
    except AttemptKilled as killed:
        kill = kill_of(time_budget, killed)
        if kill is AttemptKill.EVICTED:
            return ended(StageJobRun(StageJobExit.EVICTED, kill.value, budget, kill=kill))
        return ended(deadline_end(store, repo, item, settings.job, budget, kill, now, known=known))
    except RoadmapTimeBudgetError:
        return ended(deadline_end(store, repo, item, settings.job, budget, None, now, known=known))
    except AICredentialsError:
        raise
    except DevOpsCLIError as exc:
        return ended(stage_error_end(exc, store, repo, item, settings.job, budget, known=known))
    return None if run is None else ended(run)


class StageEnd(StrEnum):
    """How the agent phase ended (#6705): it `ended` the run, the run `unverified` its checks
    (`CompletionUnverifiedEvent`), the time budget ended (`timeout`), a model call failed
    (`provider`), the provider key reached its spend limit (`spend_limit`), or another error of
    the phase stopped it (`ci_infra`). `publish` trusts none of them as it is."""

    ENDED = "ended"
    UNVERIFIED = "unverified"
    TIMEOUT = "timeout"
    PROVIDER = "provider"
    SPEND_LIMIT = "spend_limit"
    CI_INFRA = "ci_infra"


class StageCheck(StrEnum):
    """The three checks of the stage agent, in the order of `STAGE_CHECKS`."""

    OPENSPEC_CHECK = "openspec-check"
    OPENSPEC_VALIDATE = "openspec-validate"
    PLAN_RECHECK = "plan-recheck"


class StageOutcome(_Model):
    """`out/outcome.json` of the agent phase (#6705): the end, the checks whose last run failed,
    and fixed counts of the run. It holds no text of the model."""

    end: StageEnd
    failed: tuple[StageCheck, ...] = ()
    requests: NonNegativeInt = 0
    tool_calls: NonNegativeInt = 0
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    seconds: NonNegativeInt = 0


def _refuse_credentials() -> None:
    """Refuse a process that holds the App key, a GitHub token, or a gh login (#6705)."""
    held = sorted(
        name for name in CONST_GITHUB_AGENT_REFUSED_ENV if os.environ.get(name, "").strip()
    )
    if held:
        raise RoadmapStageError(
            MESSAGES.roadmap.stage_agent_phase_key_refused.format(names=", ".join(held))
        )
    if finds_github_login():
        raise RoadmapStageError(MESSAGES.roadmap.stage_agent_phase_login_refused)


def check_commands(inputs: StageAgentInput, listing: Path) -> tuple[str, ...]:
    """The three checks of the agent, as it runs them in its clone."""
    return (
        "devops openspec check",
        f"openspec validate {inputs.change} --strict",
        f"devops roadmap plan-recheck --source . --branch HEAD --base {inputs.base} "
        f"--candidate {CONST_ROADMAP_STAGE_CANDIDATE_FILE} --issues {listing}",
    )


def _request(inputs: StageAgentInput, listing: Path) -> str:
    """The user message of the agent: its inputs and its checks, as JSON."""
    return json.dumps(
        {
            "number": inputs.item,
            "title": inputs.title,
            "url": inputs.url,
            "body": inputs.body,
            "comments": [comment.model_dump(mode="json") for comment in inputs.comments],
            "probes": list(inputs.probes),
            "open_plan_creates": inputs.creates,
            "rejected_plan": inputs.rejected,
            "budget": inputs.step_tokens,
            "body_room": inputs.body_room,
            "change_folder": f"{CONST_OPENSPEC_CHANGES_DIR}/{inputs.change}",
            "branch": inputs.branch,
            "base": inputs.base,
            "issue_listing": str(listing),
            "candidate": CONST_ROADMAP_STAGE_CANDIDATE_FILE,
            "checks": list(check_commands(inputs, listing)),
        }
    )


def _failed_checks(commands: list[str]) -> tuple[StageCheck, ...]:
    """The checks among `commands`, the failed commands of `CompletionUnverifiedEvent`."""
    names = list(StageCheck)
    return tuple(
        names[index]
        for index, pattern in enumerate(STAGE_CHECKS)
        if any(re.match(pattern, command.strip()) for command in commands)
    )


def _end_of(error: Exception) -> StageEnd:
    """The end of a run that `error` stopped."""
    if isinstance(error, RoadmapTimeBudgetError):
        return StageEnd.TIMEOUT
    if isinstance(error, ModelHTTPError) and spend_limit_error(error.status_code, error.body):
        return StageEnd.SPEND_LIMIT
    if isinstance(error, ModelAPIError | UnexpectedModelBehavior | AIClientError):
        return StageEnd.PROVIDER
    return StageEnd.CI_INFRA


def _counts(messages: list[ModelMessage]) -> dict[str, int]:
    """The counts of a run from its messages."""
    responses = [message for message in messages if isinstance(message, ModelResponse)]
    return {
        "requests": len(responses),
        "tool_calls": sum(
            1 for response in responses for part in response.parts if isinstance(part, ToolCallPart)
        ),
        "input_tokens": sum(response.usage.input_tokens for response in responses),
        "output_tokens": sum(response.usage.output_tokens for response in responses),
    }


def _hand_over(folders: RunFolders, clone: Path, inputs: StageAgentInput) -> None:
    """Write the patch of the change folder from the base and the body candidate to `out/`."""
    write_patch(
        clone,
        inputs.base,
        folders.out / CONST_ROADMAP_STAGE_PLAN_PATCH_FILE,
        only=f"{CONST_OPENSPEC_CHANGES_DIR}/{inputs.change}",
    )
    try:
        candidate = read_run_file(
            RunFolders(folders.work),
            clone,
            CONST_ROADMAP_STAGE_CANDIDATE_FILE,
            limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
        )
    except PhaseOutputError:
        return
    path = folders.out / CONST_ROADMAP_STAGE_CANDIDATE_OUT_FILE
    path.write_bytes(candidate)
    path.chmod(0o600)


def run_stage_agent(folders: RunFolders, *, model: Any = None) -> StageOutcome | None:
    """The agent phase of the run of `folders` (#6705). It refuses a process that holds a GitHub
    credential. A run folder whose `prepare` ended the run holds no inputs: the phase writes
    nothing and gives None. Else it makes `out/`, which must not be there yet, runs the stage
    agent in the clone of `prepare` with no request limit, and writes the patch of the change
    folder, the body candidate and the outcome. `model` replaces the model of the task `stage`.

    A SIGTERM raises `AttemptKilled` with the class of the kill, and the phase writes no
    outcome and no check-in."""
    _refuse_credentials()
    source = folders.work / CONST_ROADMAP_PHASE_INPUT_FILE
    if not source.is_file():
        return None
    inputs = StageAgentInput.model_validate_json(source.read_text(encoding="utf-8"))
    folders.make_out()
    clone = folders.work / CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME
    listing = folders.work / CONST_ROADMAP_STAGE_ISSUES_FILE
    if model is None:
        from devops_cli.ai.client.factory import get_task_model

        model = get_task_model("stage")
    config = get_active_config_path()
    home = Path(tempfile.mkdtemp(prefix="devops-stage-home-"))
    log = StageRunLog()
    started = clock.monotonic()
    seconds = max(0, int((inputs.deadline - datetime.now(UTC)).total_seconds()))
    time_budget = TimeBudget.start(seconds, BUDGET_SETTING)
    agent = build_stage_agent(
        model,
        clone,
        home=home,
        config=config if config.is_file() else None,
        instructions=load_task_prompt(_CODER_PROMPT),
        window=task_window("stage"),
        deadline=inputs.deadline,
        log=log,
    )
    end = StageEnd.ENDED
    try:
        with sigterm_raises(), capture_run_messages() as messages:
            try:
                agent.run_sync(
                    _request(inputs, listing), usage_limits=UsageLimits(request_limit=None)
                )
            except AttemptKilled as killed:
                raise AttemptKilled(kill_of(time_budget, killed)) from None
            except Exception as error:
                end = _end_of(error)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    if end is StageEnd.ENDED and log.unverified is not None:
        end = StageEnd.UNVERIFIED
    _hand_over(folders, clone, inputs)
    outcome = StageOutcome(
        end=end,
        failed=_failed_checks(log.failed_checks),
        seconds=round(clock.monotonic() - started),
        **_counts(messages),
    )
    write_json(folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE, outcome)
    return outcome


# ── publish ──────────────────────────────────────────────────────────────────

# The files of a change folder that `publish` allows: the files of a plan.
_PLAN_FILES: Final[frozenset[str]] = frozenset(
    {".openspec.yaml", "proposal.md", "design.md", "tasks.md"}
)
_SPEC_FILE: Final[re.Pattern[str]] = re.compile(
    r"specs/[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)?/spec\.md"
)
_TEXT_MODE: Final[str] = "100644"
_DELETED: Final[str] = "D"
# The findings of the gate of OpenSpec that say nothing of the plan: the environment of the check.
_CI_INFRA_CHECKS: Final[frozenset[GateCheck]] = frozenset(
    {GateCheck.VERSION, GateCheck.CONFIGURATION, GateCheck.SKILLS, GateCheck.INSTRUCTIONS}
)
# The errors of a check that say nothing of the plan: a missing tool, a network or GitHub error.
_CI_INFRA_ERRORS: Final = (DependencyError, GitHubOperationError, GitOperationError)
_BUDGET_RULE: Final[str] = "group-over-budget"
# Each control character but the line feed.
_CONTROL: Final[re.Pattern[str]] = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")
# The pull request number that `fit_plan_state` measures the comment with: the longest one.
_LONGEST_PULL: Final[int] = 9_999_999
_CREATED: Final[re.Pattern[str]] = re.compile(r"^created:\s*(\S+)\s*$", re.MULTILINE)


def clean_text(text: str) -> str:
    """`text` with each control character but the line feed removed (#6705)."""
    return _CONTROL.sub("", text)


def fit_plan_state(change: StagedChange) -> StagedChange:
    """`change` with its group titles cut until its plan-state comment holds at most the
    characters of a GitHub comment (#6705). The files of the plan keep the full titles. A change
    whose comment fits comes back as it is."""
    fitted, cap = change, max((len(m.group.title) for m in change.groups), default=0)
    while len(plan_state_text(fitted, _LONGEST_PULL)) > CONST_GITHUB_COMMENT_MAX_CHARS and cap > 1:
        cap //= 2
        groups = tuple(
            replace(m, group=m.group.model_copy(update={"title": m.group.title[:cap]}))
            for m in change.groups
        )
        fitted = replace(change, groups=groups)
    return fitted


@dataclass(frozen=True)
class _Change:
    """One entry of `git diff --raw`."""

    new_mode: str
    status: str
    path: str


def _raw_changes(repo: Path, *revisions: str, home: Path | None = None) -> list[_Change]:
    """Each change of `git diff --raw -z --no-renames <revisions>` in `repo`."""
    listed = git_call(repo, "diff", "--raw", "-z", "--no-renames", *revisions, home=home)
    fields = listed.split("\0")
    found: list[_Change] = []
    for head, path in zip(fields[0::2], fields[1::2], strict=False):
        if head.startswith(":"):
            _old_mode, new_mode, _old, _new, status = head[1:].split(" ")
            found.append(_Change(new_mode, status, path))
    return found


def _plan_texts(repo: Path, changes: list[_Change], root: str) -> dict[str, str]:
    """The text of each changed file of the change folder `root` in the working tree of `repo`.
    Raises `RoadmapStageError` for a change of another path, a mode other than `100644` or a
    file that is not UTF-8: only the files of a plan pass, before any check (#6705)."""
    texts = MESSAGES.roadmap
    files: dict[str, str] = {}
    for change in changes:
        name = change.path.removeprefix(f"{root}/")
        if name == change.path or not (name in _PLAN_FILES or _SPEC_FILE.fullmatch(name)):
            raise RoadmapStageError(
                texts.stage_publish_path_refused.format(path=mask_secrets(change.path), folder=root)
            )
        if change.status == _DELETED:
            continue
        if change.new_mode != _TEXT_MODE:
            raise RoadmapStageError(
                texts.stage_publish_mode_refused.format(path=change.path, mode=change.new_mode)
            )
        try:
            files[change.path] = (repo / change.path).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise RoadmapStageError(texts.stage_publish_not_text.format(path=change.path)) from None
    return files


class _BudgetStop(Exception):
    """The only finding of the checks of `publish` is a group over the budget (#6705)."""


@dataclass
class _Findings:
    """The findings of the checks of `publish`, by what they say."""

    plan: list[str]
    ci_infra: list[str]
    budget: list[str]

    def raise_any(self) -> None:
        """Raise for the findings, as the module says: a plan finding first, then a finding of the
        `ci_infra` list, then the budget."""
        texts = MESSAGES.roadmap
        if self.plan:
            raise RoadmapStageError(
                texts.stage_publish_findings.format(findings=" ".join(self.plan))
            )
        if self.ci_infra:
            raise DevOpsCLIError(
                texts.stage_publish_checks_unavailable.format(findings=" ".join(self.ci_infra))
            )
        if self.budget:
            raise _BudgetStop(" ".join(self.budget))


class _Publish:
    """One run of `publish`, as `publish_stage_job` says."""

    def __init__(
        self,
        store: RoadmapStore,
        folders: RunFolders,
        state: StageState,
        target: StageTarget,
        *,
        settings: RoadmapStageConfig,
        budget: RequestBudget,
        now: datetime | None,
    ) -> None:
        self.store = store
        self.folders = folders
        self.state = state
        self.target = target
        self.settings = settings
        self.budget = budget
        self.now = now
        self.plan = StagePlan(
            state.repo,
            state.base,
            settings.step_tokens,
            rejections=(state.rejection,) if state.rejection is not None else (),
        )
        self.attempt = StageAttempt(state.item)
        self.patch = b""
        self.candidate: str | None = None

    @property
    def root(self) -> str:
        return f"{CONST_OPENSPEC_CHANGES_DIR}/{self.state.change}"

    def finish(self, result: PlanResult | None, writer: StageWriter) -> StageJobRun:
        plan = self.plan
        if result is not None:
            plan = _with_result(plan, result, self.attempt.seconds)
        return finish_stage_job(
            self.store,
            repo=self.state.repo,
            item=self.state.item,
            job=self.state.job,
            budget=self.budget,
            plan=replace(plan, attempts=(self.attempt,)),
            applied=writer.applied(),
            now=self.now,
            known=self.state.known,
        )

    def writer(self, source: Path) -> StageWriter:
        writer = StageWriter(self.store, source, now=self.now, push=self.push)
        writer.resume(self.plan, {self.state.item}, self.state.begun)
        return writer

    def failure(self, failure_class: FailureClass, reason: str) -> StageFailure:
        item = self.target.item
        error = (
            RoadmapStageError.__name__ if failure_class is FailureClass.PLAN_DEFECT else "AgentEnd"
        )
        return StageFailure(
            item.number,
            item.title,
            error,
            mask_secrets(reason),
            item,
            failure_class=failure_class,
            step=StepName.PLAN,
        )

    def refuse(self, failure: StageFailure, source: Path | None = None) -> StageJobRun:
        writer = self.writer(source or self.folders.root)
        writer.settle(self.target, failure)
        return self.finish(failure, writer)

    def run(self) -> StageJobRun:
        texts = MESSAGES.roadmap
        try:
            outcome = StageOutcome.model_validate_json(
                read_output(
                    self.folders,
                    CONST_ROADMAP_PHASE_OUTCOME_FILE,
                    limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
                )
            )
        except (PhaseOutputError, ValidationError) as exc:
            error = exc if isinstance(exc, PhaseOutputError) else f"{exc.error_count()} error(s)"
            reason = texts.stage_publish_outcome_refused.format(error=error)
            return self.refuse(self.failure(FailureClass.PLAN_DEFECT, reason))
        self.attempt = StageAttempt(
            self.state.item,
            plan_calls=outcome.requests,
            tokens=outcome.input_tokens + outcome.output_tokens,
            seconds=outcome.seconds,
        )
        at = self.now or datetime.now(UTC)
        end = outcome.end
        deadline = self.state.deadline
        if end is StageEnd.TIMEOUT and deadline is not None and datetime.now(UTC) >= deadline:
            return deadline_end(
                self.store,
                self.state.repo,
                self.state.item,
                self.state.job,
                self.budget,
                None,
                self.now,
                known=self.state.known,
            )
        reason = texts.stage_publish_agent_end.format(end=end.value)
        if end in (StageEnd.PROVIDER, StageEnd.SPEND_LIMIT):
            return self.refuse(self.failure(FailureClass(end.value), reason))
        if end is StageEnd.CI_INFRA:
            return self.agent_ci_infra(at)
        return self.stage()

    def agent_ci_infra(self, at: datetime) -> StageJobRun:
        """Count a `ci_infra` end of the agent toward the split limit, in the marks of the
        check-in: the end that reaches the limit is `plan_defect`, which returns the item for a
        split (#6705)."""
        count, body = plan_defects(self.target.item)
        at_limit = count >= self.settings.plan_defect_limit
        check_in(
            self.store,
            self.state.item,
            repo=self.state.repo,
            job=self.state.job,
            result=StageEnd.CI_INFRA.value,
            now=at,
            failure=FailureClass.PLAN_DEFECT if at_limit else FailureClass.CI_INFRA,
            marks=None
            if at_limit
            else {StageRecordKey.PLAN_DEFECTS: str(count), StageRecordKey.PLAN_DEFECTS_BODY: body},
        )
        return StageJobRun(StageJobExit.FAILURE, StageEnd.CI_INFRA.value, self.budget)

    def stage(self) -> StageJobRun:
        """Read the plan of the agent in a clone of its own, build the change, and settle it with
        the writer of `--phase all`, whose push checks the new tree."""
        texts = MESSAGES.roadmap
        try:
            self.patch = read_output(
                self.folders,
                CONST_ROADMAP_STAGE_PLAN_PATCH_FILE,
                limit=CONST_ROADMAP_PHASE_PATCH_MAX_BYTES,
            )
        except PhaseOutputError as exc:
            reason = texts.stage_publish_patch_refused.format(error=exc)
            return self.refuse(self.failure(FailureClass.PLAN_DEFECT, reason))
        self.candidate = self.read_candidate()
        home = Path(tempfile.mkdtemp(prefix="devops-stage-publish-"))
        try:
            source = clone_at_base(
                home / "source", self.state.repo, self.state.base, self.state.identity
            )
            try:
                change = self.change(source)
            except (RoadmapStageError, PublishRefusedError) as exc:
                failure = self.failure(FailureClass.PLAN_DEFECT, str(exc))
                return self.refuse(failure, source)
            writer = self.writer(source)
            try:
                writer.settle(self.target, change)
            except _BudgetStop:
                stopped = OverBudget(self.target, change.groups, self.settings.step_tokens)
                writer.settle(self.target, stopped)
                held = self.store.item(self.state.item)
                if held is not None:
                    self.store.set_marks(held, {StageRecordKey.PENDING: None})
                return self.finish(stopped, writer)
            return self.finish(change, writer)
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def read_candidate(self) -> str | None:
        """The body candidate of the agent as text, or None when it gave none that publish reads."""
        try:
            data = read_output(
                self.folders,
                CONST_ROADMAP_STAGE_CANDIDATE_OUT_FILE,
                limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
            )
            return data.decode("utf-8")
        except PhaseOutputError, UnicodeDecodeError:
            return None

    def change(self, source: Path) -> StagedChange:
        """The change of the plan of the agent, built in the clone `source` at the base: the
        files read from the patch, the texts of `stage_candidate`, cleaned, and the measure of the
        groups. The clone is at the base again after the read."""
        patch = source.parent / CONST_ROADMAP_STAGE_PLAN_PATCH_FILE
        patch.write_bytes(self.patch)
        try:
            git_call(source, "apply", "--index", "--binary", str(patch))
        except GitOperationError as exc:
            raise PublishRefusedError(f"git apply refused the patch: {exc}") from exc
        try:
            changes = _raw_changes(source, "--cached", self.state.base)
            files = _plan_texts(source, changes, self.root)
        finally:
            git_call(source, "reset", "--hard", "--quiet", self.state.base)
        try:
            proposal = read_change(files)
        except PlanReadError as exc:
            raise RoadmapStageError(f"{exc.path}: {exc.reason}") from exc
        item = self.target.item
        candidate = None if self.candidate is None else read_candidate(self.candidate)
        texts = plan_texts(item.number, self.state.change, item.title, candidate, proposal.why)
        if texts.problems:
            raise RoadmapStageError(" ".join(texts.problems))
        measured = measure_groups(
            source, proposal.groups, shared=shared_texts(item.title, item.body, files)
        )
        groups = tuple(
            MeasuredGroup(
                m.group.model_copy(update={"title": clean_text(m.group.title)}), m.tokens, m.files
            )
            for m in measured
        )
        change = StagedChange(
            self.target,
            clean_text(texts.title),
            clean_text(texts.body),
            files,
            groups,
            True,
            self.settings.step_tokens,
            proposal,
        )
        return fit_plan_state(change)

    def push(
        self,
        repo: str,
        *,
        issue: int,
        branch: str,
        files: Mapping[str, str],
        staged: str,
        message: str,
        lease: str | None,
        identity: tuple[str, str],
    ) -> str:
        """The one push of `publish`: the patch of the agent on the base, with the checks in
        `before_push`."""
        texts = MESSAGES.roadmap
        if lease is not None and lease != self.state.lease:
            raise GitOperationError(
                texts.stage_restage_moved.format(
                    branch=branch, recorded=lease, tip=self.state.lease or "none"
                ),
                operation=_GIT_OPERATION,
            )
        target = target_of(
            repo,
            branch,
            base=self.state.base,
            lease=self.state.lease if lease is None else lease,
            identity=identity,
        )
        try:
            published = publish_patch(target, [(self.patch, message)], before_push=self.check)
        except PublishRefusedError as exc:
            raise RoadmapStageError(texts.stage_publish_patch_refused.format(error=exc)) from exc
        if published is None:
            raise RoadmapStageError(texts.stage_push_no_change.format(number=issue))
        return published.commit

    def check(self, tree: NewTree) -> None:
        """The checks of the new tree before the push, as the module says."""
        changes = _raw_changes(tree.repo, self.state.base, "HEAD", home=tree.home)
        files = _plan_texts(tree.repo, changes, self.root)
        self.check_content(files)
        findings = _Findings([], [], [])
        self.check_gate(tree.repo, findings)
        try:
            with openspec_tool() as tool:
                if tool is None:
                    findings.ci_infra.append(MESSAGES.openspec.missing_hint)
                else:
                    if problem := validate_change(tool, tree.repo, self.state.change, files):
                        findings.plan.append(" ".join(problem.split()))
                    self.check_recheck(tree.repo, tool, findings)
        except _CI_INFRA_ERRORS as exc:
            findings.ci_infra.append(mask_secrets(str(exc)))
        except ToolExecutionError as exc:
            findings.plan.append(mask_secrets(str(exc)))
        findings.raise_any()

    def check_content(self, files: Mapping[str, str]) -> None:
        """Refuse a secret and a date of the change other than the date of `prepare`."""
        texts = MESSAGES.roadmap
        for path, text in files.items():
            if redact_text(text) != text:
                raise RoadmapStageError(texts.stage_secret.format(path=path))
        meta = files.get(f"{self.root}/.openspec.yaml")
        found = _CREATED.search(meta or "")
        created = self.state.created.isoformat() if self.state.created is not None else ""
        if meta is not None and (found is None or found.group(1) != created):
            raise RoadmapStageError(
                texts.stage_publish_date_refused.format(
                    found=found.group(1) if found else "none", created=created
                )
            )

    def check_gate(self, root: Path, findings: _Findings) -> None:
        """`devops openspec check` on the new tree."""
        try:
            gate = check_openspec(root)
        except _CI_INFRA_ERRORS as exc:
            findings.ci_infra.append(mask_secrets(str(exc)))
            return
        for finding in gate:
            line = mask_secrets(finding.line())
            (findings.ci_infra if finding.check in _CI_INFRA_CHECKS else findings.plan).append(line)

    def check_recheck(self, root: Path, tool: Any, findings: _Findings) -> None:
        """The recheck with the base of `prepare` on the new tree, with the listing of `state/`."""
        listing = ListingIssues.parse(
            read_run_file(
                self.folders,
                self.folders.state,
                CONST_ROADMAP_STAGE_ISSUES_FILE,
                limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
            )
        )
        recheck = recheck_plans(
            root,
            listing,
            tool=tool,
            branch="HEAD",
            base=self.state.base,
            default=self.state.default,
            candidate=self.candidate,
        )
        for record in recheck.branch.records if recheck.branch is not None else ():
            if record.result is RecheckResult.OK:
                continue
            if not record.refusals:
                findings.plan.append(f"{record.folder}: {record.result.value}")
            for refusal in record.refusals:
                line = mask_secrets(f"{record.folder} [{refusal.gate}] {refusal.message}")
                (findings.budget if refusal.gate == _BUDGET_RULE else findings.plan).append(line)


def read_stage_state(folders: RunFolders, *, repo: str, item: int) -> StageState:
    """The state file of the run, read as data. It must name item `item` of `repo`."""
    data = read_run_file(
        folders,
        folders.state,
        CONST_ROADMAP_PHASE_STATE_FILE,
        limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    )
    try:
        state = StageState.model_validate_json(data)
    except ValidationError as exc:
        raise PhaseOutputError(
            f"The state file of the run is not of its model: {exc.error_count()} error(s)"
        ) from None
    if (state.repo, state.item) != (repo, item):
        raise PhaseOutputError("The state file of the run names another item")
    return state


def publish_stage_job(
    store: RoadmapStore,
    folders: RunFolders,
    *,
    repo: str,
    item: int,
    now: datetime | None = None,
) -> StageJobRun:
    """`publish` of the stage Job of item `item` of `repo` on the run folder `folders` (#6705).

    It counts the GitHub requests of `prepare` in its budget. A run that `prepare` ended ends
    with that end and writes nothing. Else it trusts no end that the agent reports: it reads the
    outcome as data, and

    - an outcome outside its model, or a state, a patch or a plan file that it refuses, is
      `plan_defect`;
    - `timeout` after the end time of the budget checks in the deadline; before it, it is `ended`;
    - `provider` and `spend_limit` record their class and their wait, with no count;
    - `ci_infra` counts toward `roadmap.stage.plan_defect_limit` in the marks of the check-in;
    - `ended` and `unverified` give the plan to the writer of `--phase all`, on a clone of
      `publish` at the base. The one push applies the patch of the agent and runs the checks in
      `before_push`: a plan finding is `plan_defect`, a finding of the `ci_infra` list only is
      `ci_infra`, and a plan whose only finding is a group over the budget stops with the owner
      question of the budget.
    """
    require_job_token_scope(repo)
    settings = load_settings().roadmap.stage
    budget = install_request_budget(settings.github_requests_per_hour)
    try:
        state = read_stage_state(folders, repo=repo, item=item)
    except PhaseOutputError as exc:
        return _unread(store, folders, repo, item, settings, budget, now, exc)
    for _ in range(state.requests):
        budget.admit()
    if state.ended or state.target is None:
        return StageJobRun(state.end or StageJobExit.FAILURE, state.result, budget)
    held = store.item(item)
    target = state.target if held is None else replace(state.target, item=held)
    run = _Publish(store, folders, state, target, settings=settings, budget=budget, now=now)
    return run.run()


def _unread(
    store: RoadmapStore,
    folders: RunFolders,
    repo: str,
    item: int,
    settings: RoadmapStageConfig,
    budget: RequestBudget,
    now: datetime | None,
    error: PhaseOutputError,
) -> StageJobRun:
    """The end of a `publish` that cannot read its state file: `plan_defect` on the item."""
    held = store.item(item)
    if held is None:
        raise error
    known = known_job(store, item, settings.job)
    state = StageState(repo=repo, item=item, job=settings.job, known=known)
    run = _Publish(
        store,
        folders,
        state,
        StageTarget(held, "", ""),
        settings=settings,
        budget=budget,
        now=now,
    )
    reason = MESSAGES.roadmap.stage_publish_unread.format(error=error)
    return run.refuse(run.failure(FailureClass.PLAN_DEFECT, reason))


__all__ = [
    "AgentComment",
    "PlanResult",
    "StageAgentInput",
    "StageCheck",
    "StageEnd",
    "StageOutcome",
    "StageState",
    "check_commands",
    "clean_text",
    "fit_plan_state",
    "issue_listing",
    "prepare_stage_job",
    "publish_stage_job",
    "read_stage_state",
    "run_stage_agent",
    "scaffold_files",
]
