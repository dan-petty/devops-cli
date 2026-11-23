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
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, NonNegativeInt
from pydantic_ai import capture_run_messages
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.client.models import AIClientError, AICredentialsError, spend_limit_error
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_GITHUB_AGENT_REFUSED_ENV,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
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
from devops_cli.exceptions import DevOpsCLIError, RoadmapStageError, RoadmapTimeBudgetError
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.scaffold import scaffold_design, scaffold_proposal, scaffold_tasks
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled, kill_of, sigterm_raises
from devops_cli.roadmap.item_comments import HeldComment, held_comments
from devops_cli.roadmap.phases.files import RunFolders, read_run_file, write_json
from devops_cli.roadmap.phases.patch import write_patch
from devops_cli.roadmap.phases.publish import git_call
from devops_cli.roadmap.plan_recheck import ListingIssues
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
    parse_filters,
    read_stage_round,
)
from devops_cli.roadmap.stage.stage_agent import STAGE_CHECKS, StageRunLog, build_stage_agent
from devops_cli.roadmap.stage.stage_change import body_room
from devops_cli.roadmap.stage.stage_job import (
    BUDGET_SETTING,
    StageJobExit,
    StageJobRun,
    deadline_end,
    finish_stage_job,
    install_request_budget,
    job_clone,
    job_time_budget,
    known_job,
    require_job_token_scope,
    stage_error_end,
)
from devops_cli.roadmap.stage.stage_phases import clone_for_agent
from devops_cli.roadmap.stage.stage_probe import Probe, blocked_by, probe_premise
from devops_cli.roadmap.stage.stage_rejected import reasons_of
from devops_cli.roadmap.stores.store import IssueRecord, Item, RoadmapStore
from devops_cli.roadmap.time_budget import TimeBudget
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


__all__ = [
    "AgentComment",
    "PlanResult",
    "StageAgentInput",
    "StageCheck",
    "StageEnd",
    "StageOutcome",
    "StageState",
    "check_commands",
    "issue_listing",
    "prepare_stage_job",
    "run_stage_agent",
    "scaffold_files",
]
