"""The stage Job on the phases `prepare`, `agent` and `publish` of one run folder (#6813).

The stage Job of one item (`stage_job.py`) works on the run folder of `roadmap/phases`, as the
implement and fix-checks jobs do (#3702, #6601):

- `prepare` (App key, no model call) reads the round of the item and makes the writes that need
  no model (`begin_stage`). It reads the CI job-time premise of the item (`premise_before_plan`),
  which can decide the item: the phase then writes its result and ends the run. Else it clones
  the staged commit into `work/` (`clone_staged`), and writes the state file in `state/` and the
  inputs of the agent in `work/`: the item, the reads of the planner from the store, the clone and
  the staged commit.
- `agent` (model key only) reads its inputs, plans the item in the clone with the stage engine
  (`plan_targets`), and hands over only what the model made (`HandedResult`): the proposal, the
  shorter text of the body, the review findings, a compact trace and the counts of the attempt, or
  the stop, the paths of a return for blockers, the evidence of a false premise or the failure. It
  reads no store. The GitHub reads of the planner (`read_issue`, `find_issues`, the files of a
  pull request that the plan names and the open pull requests that meet a cited path) use the
  session of the process. An agent phase in a process of its own holds no GitHub credential, so
  each of these reads answers that GitHub cannot be read, as a failed read does (#3240). #6705
  replaces the engine.
- `publish` (App key) reads the state file and the outcome as data (`read_run_file`), each text of
  the outcome masked. It builds the result from the state of `prepare` and what the model made,
  with the functions that the planner runs after the model answers (`build_plan`): the title, the
  body, the files rendered from the proposal, the secret check and the checks of the files, on
  the staged commit. The blockers of a return come from the paths that the open plans create, as
  `prepare` read them, and each other text of the agent phase goes through `safe_text`. The review
  findings are the review of the agent phase: the person who reviews the plan pull request checks
  them. Then it writes the result as the stage job does (`StageWriter.settle`): `push_plan` pushes
  the plan commit, and the draft pull request is opened or updated.

`stage_job.run_stage_job` runs the three in one process (`--phase all`): the state of `prepare`
stays in memory, and the run folder goes when the Job ends.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.config.constants import (
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_STATE_FILE,
)
from devops_cli.core import clock
from devops_cli.exceptions import RoadmapStageError
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.roadmap.agent_run import RunTrace, ToolCallRecord, ToolOutcome
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.phases.files import RunFolders, read_output, read_run_file, write_json
from devops_cli.roadmap.pull_form import measured_body_text
from devops_cli.roadmap.refine.refine import body_dependencies
from devops_cli.roadmap.stage.stage import (
    ITEM_ERRORS,
    Blocked,
    FalsePremise,
    OverBudget,
    PlannedTargets,
    PlannerReads,
    PlanResult,
    PremiseKind,
    StageApplied,
    StageAttempt,
    StagedChange,
    StageFailure,
    StagePlan,
    StageTarget,
    StageWriter,
    begin_stage,
    build_plan,
    item_failure,
    parse_filters,
    plan_targets,
    premise_before_plan,
    store_reads,
)
from devops_cli.roadmap.stage.stage_change import (
    MeasuredGroup,
    StageGroup,
    StageProposal,
    safe_text,
)
from devops_cli.roadmap.stage.stage_phases import clone_staged
from devops_cli.roadmap.stage.stage_probe import blocked_by
from devops_cli.roadmap.stage.stage_verify import Finding
from devops_cli.roadmap.stores.store import IssueComment, RoadmapStore
from devops_cli.security.sanitizer import mask_dict_secrets

if TYPE_CHECKING:
    from devops_cli.ai.client import LLMClient
    from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
    from devops_cli.roadmap.time_budget import TimeBudget

_SHA = r"^[0-9a-f]{40}$"
_PLAN: TypeAdapter[StagePlan] = TypeAdapter(StagePlan)
_APPLIED: TypeAdapter[StageApplied] = TypeAdapter(StageApplied)
_TARGET: TypeAdapter[StageTarget] = TypeAdapter(StageTarget)
# The file of the change folder that holds the date of the change.
_CHANGE_META = ".openspec.yaml"
_COMMENTS: TypeAdapter[tuple[IssueComment, ...]] = TypeAdapter(tuple[IssueComment, ...])


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageJobState(_Model):
    """`state/state.json`, which `prepare` writes and a separate `publish` reads: the item and its
    repository, the Job that the settings name and whether the check-out of the item named it at
    the start of the Job (`known`), the plan of the reads, what `StageWriter.begin` wrote, and the
    target of the item, and the paths that the open plans create, each with its item, which give
    the blockers of a return. `end` and `result` are the exit code and the result of a run that
    `prepare` ended: the agent phase then has no inputs, and `publish` writes nothing."""

    repo: str
    item: int
    job: str | None = None
    known: bool = False
    plan: dict[str, Any] = Field(default_factory=dict)
    begun: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] | None = None
    creates: dict[str, int] = Field(default_factory=dict)
    end: int | None = None
    result: str = ""


class StageAgentInput(_Model):
    """`work/input.json`, the inputs of the agent phase: the repository, the clone and its staged
    commit, the step budget, the target, and the reads of the planner from the store that
    `prepare` made: the reason of each rejected plan, the comments of the item, the title of each
    dependency that its body names, and the paths that the open plans create."""

    repo: str
    checkout: str
    sha: str = Field(pattern=_SHA)
    budget: int
    target: dict[str, Any]
    rejected: dict[int, str] = Field(default_factory=dict)
    comments: list[dict[str, Any]] = Field(default_factory=list)
    titles: dict[int, str] = Field(default_factory=dict)
    creates: dict[str, int] = Field(default_factory=dict)


class StageAgentEnd(StrEnum):
    """How the agent phase ended: with the result of the plan, at the end of its time budget, or
    with an error that the planner makes into no result."""

    PLANNED = "planned"
    DEADLINE = "deadline"
    FAILED = "failed"


class HandedCall(_Model):
    """One tool call of a plan run: the tool, its argument as the run masked and cut it, and how
    it ended."""

    name: str
    argument: str = ""
    outcome: ToolOutcome = ToolOutcome.OK


class HandedTrace(_Model):
    """What `publish` reads of the trace of the plan runs, for the report of the comment: each tool
    call, the requests, the tokens and the tools that each request offered. It holds no answer and
    no match of a tool, so the size of the outcome grows only with the calls."""

    calls: tuple[HandedCall, ...] = ()
    requests: NonNegativeInt = 0
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    offered: tuple[tuple[str, ...], ...] = ()

    @classmethod
    def of(cls, trace: RunTrace) -> Self:
        return cls(
            calls=tuple(
                HandedCall(name=call.name, argument=call.argument, outcome=call.outcome)
                for call in trace.tool_calls
            ),
            requests=trace.requests,
            input_tokens=trace.input_tokens,
            output_tokens=trace.output_tokens,
            offered=tuple(trace.offered),
        )

    def trace(self) -> RunTrace:
        """The trace of the report, with each text on one line as `safe_text` writes it."""
        return RunTrace(
            tool_calls=[
                ToolCallRecord(safe_text(call.name), safe_text(call.argument), call.outcome)
                for call in self.calls
            ],
            requests=self.requests,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            offered=[tuple(safe_text(name) for name in names) for names in self.offered],
        )


class HandedPlan(_Model):
    """A plan that the model made: the proposal, the text of the body (the shorter text that the
    model wrote when the text of the proposal is over its room), the date of the change folder,
    the findings of the review and the open ones, the reads of the open pull requests, the
    warnings of the plan, the comments of the item that the request held, and the trace."""

    proposal: StageProposal
    text: str
    created: date
    findings: tuple[Finding, ...] = ()
    open_findings: tuple[Finding, ...] = ()
    pulls_requests: NonNegativeInt = 0
    warnings: tuple[str, ...] = ()
    comments: tuple[str, ...] = ()
    trace: HandedTrace = Field(default_factory=HandedTrace)


class HandedGroup(_Model):
    """A task group of a stop on the budget, with the tokens and the files that the step reads."""

    group: StageGroup
    tokens: NonNegativeInt
    files: NonNegativeInt


class HandedPremise(_Model):
    """A false premise: the evidence of the probe and its kind."""

    evidence: tuple[str, ...]
    kind: PremiseKind = PremiseKind.ABSENT_FIELD


class HandedFailure(_Model):
    """A failure of the plan: the class name of the error, the reason, the class and the step,
    whether the reply was a placeholder, the problems of the refused replies, and whether the
    checks refused the last reply."""

    error: str
    reason: str = ""
    failure_class: FailureClass
    step: StepName
    degenerate: bool = False
    problems: tuple[str, ...] = ()
    stopped_by_checks: bool = False


class HandedAttempt(_Model):
    """The counts of the attempt (`StageAttempt`)."""

    plan_calls: NonNegativeInt | None = 0
    gate_returns: NonNegativeInt = 0
    verify_rounds: NonNegativeInt = 0
    tokens: NonNegativeInt = 0
    seconds: NonNegativeInt = 0


class HandedResult(_Model):
    """What the agent phase hands over of the plan of the item: one of a plan, the groups of a stop
    on the budget, the cited paths of a return for blockers, a false premise or a failure, and the
    counts of the attempt."""

    plan: HandedPlan | None = None
    over_budget: tuple[HandedGroup, ...] | None = None
    blocked: tuple[str, ...] | None = None
    premise: HandedPremise | None = None
    failure: HandedFailure | None = None
    attempt: HandedAttempt = Field(default_factory=HandedAttempt)

    @model_validator(mode="after")
    def _one_result(self) -> Self:
        kinds = (self.plan, self.over_budget, self.blocked, self.premise, self.failure)
        if sum(kind is not None for kind in kinds) != 1:
            raise ValueError("the result holds no one kind")
        return self


class StageAgentOutcome(_Model):
    """`out/outcome.json` of the agent phase: its end, the result of the plan for `planned`, and
    the masked message and the failure class of the error for `failed`."""

    end: StageAgentEnd
    result: HandedResult | None = None
    error: str = ""
    failure: FailureClass | None = None


def _state(folders: RunFolders, state: StageJobState) -> StageJobState:
    write_json(folders.state / CONST_ROADMAP_PHASE_STATE_FILE, state)
    return state


def end_state(
    folders: RunFolders, *, repo: str, item: int, job: str | None, end: int, result: str
) -> StageJobState:
    """Write the state file of a run that `prepare` ended with the exit code `end` and `result`."""
    return _state(folders, StageJobState(repo=repo, item=item, job=job, end=end, result=result))


def prepare_stage(
    store: RoadmapStore,
    writer: StageWriter,
    folders: RunFolders,
    *,
    repo: str,
    item: int,
    source: Path,
    job: str | None,
    known: bool,
    now: datetime | None = None,
) -> StagePlan | StageJobState:
    """`prepare` of item `item` in the clone `source` of the Job, as the module says: the plan,
    with the result of the item, when the phase decided the run, or the state that hands the run
    to the agent phase. `writer` makes the writes of the round."""
    read = begin_stage(
        store,
        repo=repo,
        source=source,
        filters=parse_filters(()),
        item_number=item,
        now=now,
        writer=writer,
        named=False,
        job=job,
    )
    plan = read.plan
    if not read.selected:
        return plan
    target = read.selected[0]
    reads = store_reads(store, plan, read.selected, source, read.planned)
    started = clock.monotonic()
    decided = premise_before_plan(repo, target)
    comments: list[dict[str, Any]] = []
    titles: dict[int, str] = {}
    creates: dict[str, int] = {}
    if decided is None:
        # The planner made these reads in its plan of the item, so an error of one fails the item,
        # as `_plan_each` fails it, and a refused key of the provider stops the run.
        try:
            comments = [c.model_dump(mode="json") for c in reads.comments_on(item)]
            titles = {
                number: title
                for number in body_dependencies(target.item.body)
                if (title := reads.dependency_title(number)) is not None
            }
            creates = dict(reads.open_creates())
        except AICredentialsError:
            raise
        except ITEM_ERRORS as exc:
            decided = item_failure(target, exc)
    if decided is not None:
        writer.settle(target, decided)
        attempt = StageAttempt(target.item.number, seconds=round(clock.monotonic() - started))
        return PlannedTargets.of([decided], [attempt]).into(plan)
    checkout = clone_staged(folders.work, repo, plan.sha)
    inputs = StageAgentInput(
        repo=repo,
        checkout=str(checkout),
        sha=plan.sha,
        budget=plan.budget,
        target=_TARGET.dump_python(target, mode="json"),
        rejected=dict(reads.rejected),
        comments=comments,
        titles=titles,
        creates=creates,
    )
    write_json(folders.work / CONST_ROADMAP_PHASE_INPUT_FILE, inputs)
    return _state(
        folders,
        StageJobState(
            repo=repo,
            item=item,
            job=job,
            known=known,
            plan=_PLAN.dump_python(plan, mode="json"),
            begun=_APPLIED.dump_python(writer.applied(), mode="json"),
            target=_TARGET.dump_python(target, mode="json"),
            creates=creates,
        ),
    )


def has_inputs(folders: RunFolders) -> bool:
    """Whether `prepare` handed the run of `folders` to the agent phase."""
    return (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).is_file()


def write_agent_end(folders: RunFolders, outcome: StageAgentOutcome) -> None:
    """Write `outcome` to `out/`, which the agent phase made at its start."""
    write_json(folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE, outcome)


def _created(change: StagedChange) -> date:
    """The date of the change folder of `change`, which the planner wrote in `.openspec.yaml`."""
    for path, text in change.files.items():
        if path.endswith(f"/{_CHANGE_META}"):
            for line in text.splitlines():
                key, _, value = line.partition(":")
                if key.strip() == "created":
                    return date.fromisoformat(value.strip())
    raise RoadmapStageError(f"The change {change.target.change} holds no date")


def handed_result(result: PlanResult, attempt: StageAttempt | None) -> HandedResult:
    """What the agent phase hands over of `result`, the result of the plan, and of its `attempt`:
    what the model made, and no part that `publish` builds itself."""
    counts = (
        HandedAttempt()
        if attempt is None
        else HandedAttempt(
            plan_calls=attempt.plan_calls,
            gate_returns=attempt.gate_returns,
            verify_rounds=attempt.verify_rounds,
            tokens=attempt.tokens,
            seconds=attempt.seconds,
        )
    )
    if isinstance(result, StagedChange):
        plan = HandedPlan(
            proposal=result.proposal,
            text=measured_body_text(result.body, "Plans"),
            created=_created(result),
            findings=result.findings,
            open_findings=result.open_findings,
            pulls_requests=result.pulls_requests,
            warnings=result.warnings,
            comments=result.comments,
            trace=HandedTrace.of(result.trace),
        )
        return HandedResult(plan=plan, attempt=counts)
    if isinstance(result, OverBudget):
        groups = tuple(
            HandedGroup(group=m.group, tokens=m.tokens, files=m.files) for m in result.groups
        )
        return HandedResult(over_budget=groups, attempt=counts)
    if isinstance(result, Blocked):
        return HandedResult(blocked=result.paths, attempt=counts)
    if isinstance(result, FalsePremise):
        premise = HandedPremise(evidence=result.evidence, kind=result.kind)
        return HandedResult(premise=premise, attempt=counts)
    failure = HandedFailure(
        error=result.error,
        reason=result.reason,
        failure_class=result.failure_class,
        step=result.step,
        degenerate=result.degenerate,
        problems=result.problems,
        stopped_by_checks=result.stopped_by_checks,
    )
    return HandedResult(failure=failure, attempt=counts)


def agent_stage(
    folders: RunFolders,
    *,
    model: LLMClient | ToolboxModel | None = None,
    verifier: ToolboxModel | None = None,
    time_budget: TimeBudget | None = None,
) -> None:
    """The agent phase of the run of `folders`: plan the target of the inputs in the clone of
    `prepare`, and write the outcome. It makes `out/` first, so an output folder that is there
    already stops the phase before the plan. A run folder whose `prepare` ended the run holds no
    inputs, and the phase writes nothing. It reads no store. `model`, `verifier` and
    `time_budget` are those of `plan_stage`."""
    if not has_inputs(folders):
        return
    folders.make_out()
    inputs = StageAgentInput.model_validate_json(
        (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).read_text(encoding="utf-8")
    )
    target = _TARGET.validate_python(inputs.target)
    comments = _COMMENTS.validate_python(inputs.comments)
    number = target.item.number
    reads = PlannerReads(
        rejected=inputs.rejected,
        comments_on=lambda asked: comments if asked == number else (),
        dependency_title=inputs.titles.get,
        open_creates=lambda: inputs.creates,
    )
    planned = plan_targets(
        [target],
        repo=inputs.repo,
        checkout=Path(inputs.checkout),
        sha=inputs.sha,
        budget=inputs.budget,
        reads=reads,
        model=model,
        verifier=verifier,
        time_budget=time_budget,
    )
    (result,) = planned.results()
    attempt = planned.attempts[0] if planned.attempts else None
    write_agent_end(
        folders,
        StageAgentOutcome(end=StageAgentEnd.PLANNED, result=handed_result(result, attempt)),
    )


def read_stage_state(folders: RunFolders, *, repo: str, item: int) -> StageJobState:
    """The state file of the run, read as data. It must name item `item` of `repo`."""
    data = read_run_file(
        folders,
        folders.state,
        CONST_ROADMAP_PHASE_STATE_FILE,
        limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    )
    try:
        state = StageJobState.model_validate_json(data)
    except ValidationError as exc:
        raise PhaseOutputError(
            f"The state file of the run is not of its model: {exc.error_count()} error(s)"
        ) from None
    if (state.repo, state.item) != (repo, item):
        raise PhaseOutputError("The state file of the run names another item")
    return state


def read_stage_outcome(folders: RunFolders) -> StageAgentOutcome:
    """`outcome.json` of the agent phase, read as data, with each text masked."""
    data = read_output(
        folders, CONST_ROADMAP_PHASE_OUTCOME_FILE, limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES
    )
    try:
        return StageAgentOutcome.model_validate(mask_dict_secrets(json.loads(data)))
    except (ValueError, ValidationError, RecursionError) as exc:
        raise PhaseOutputError("The output `outcome.json` is not of its model") from exc


def staged_commit(state: StageJobState) -> str:
    """The staged commit of the run of `state`: the commit that the planner read."""
    return _PLAN.validate_python(state.plan).sha


def _finding(finding: Finding) -> Finding:
    """`finding`, a finding of the review of the agent phase, with each text as `safe_text`
    writes it."""
    where = finding.where.model_copy(update={"section": safe_text(finding.where.section)})
    return finding.model_copy(
        update={
            "problem": safe_text(finding.problem),
            "quote": safe_text(finding.quote),
            "where": where,
        }
    )


def _staged(
    handed: HandedPlan, target: StageTarget, plan: StagePlan, checkout: Path
) -> StagedChange | OverBudget:
    """The change that the plan of the model gives, built as the planner builds it."""
    try:
        built = build_plan(
            target,
            handed.proposal,
            text=handed.text,
            created=handed.created,
            checkout=checkout,
            sha=plan.sha,
            budget=plan.budget,
        )
    except RoadmapStageError as exc:
        raise PhaseOutputError(f"A check of the plan refuses it: {safe_text(str(exc))}") from exc
    if isinstance(built, OverBudget):
        return built
    return StagedChange(
        target,
        built.title,
        built.body,
        built.files,
        built.groups,
        built.validated,
        plan.budget,
        handed.proposal,
        trace=handed.trace.trace(),
        findings=tuple(_finding(finding) for finding in handed.findings),
        open_findings=tuple(_finding(finding) for finding in handed.open_findings),
        pulls_requests=handed.pulls_requests,
        warnings=tuple(
            dict.fromkeys((*(safe_text(text) for text in handed.warnings), *built.warnings))
        ),
        comments=tuple(safe_text(name) for name in handed.comments),
    )


def _over_budget(
    groups: tuple[HandedGroup, ...], target: StageTarget, plan: StagePlan
) -> OverBudget:
    measured = tuple(MeasuredGroup(m.group, m.tokens, m.files) for m in groups)
    if not any(m.tokens > plan.budget for m in measured):
        raise PhaseOutputError("The stop on the budget holds no group over the budget")
    return OverBudget(target, measured, plan.budget)


def _blocked(paths: tuple[str, ...], target: StageTarget, creates: dict[str, int]) -> Blocked:
    """The return for blockers: the cited paths that the open plans create, as `prepare` read
    them, and the items of those plans."""
    known = tuple(path for path in paths if path in creates)
    blockers = blocked_by(known, creates)
    if not blockers:
        raise PhaseOutputError("The return for blockers names no path that an open plan creates")
    return Blocked(target, blockers, known)


def _result(
    handed: HandedResult, target: StageTarget, plan: StagePlan, state: StageJobState, checkout: Path
) -> PlanResult:
    if handed.plan is not None:
        return _staged(handed.plan, target, plan, checkout)
    if handed.over_budget is not None:
        return _over_budget(handed.over_budget, target, plan)
    if handed.blocked is not None:
        return _blocked(handed.blocked, target, state.creates)
    if handed.premise is not None:
        evidence = tuple(safe_text(text) for text in handed.premise.evidence)
        return FalsePremise(target, evidence, handed.premise.kind)
    failure = handed.failure
    if failure is None:
        raise PhaseOutputError("The outcome of the agent phase holds no result of the item")
    return StageFailure(
        target.item.number,
        target.item.title,
        safe_text(failure.error),
        safe_text(failure.reason),
        target.item,
        failure_class=failure.failure_class,
        step=failure.step,
        degenerate=failure.degenerate,
        problems=tuple(safe_text(problem) for problem in failure.problems),
        stopped_by_checks=failure.stopped_by_checks,
    )


def planned_of(
    outcome: StageAgentOutcome, state: StageJobState, *, checkout: Path
) -> PlannedTargets:
    """The result of the plan of the item of `state`, from an outcome that ended `planned`, built
    from the state of `prepare` and what the model made, in the clone `checkout` at the staged
    commit. Raises `PhaseOutputError` for an outcome with no result and for a plan that a check
    refuses."""
    if outcome.result is None:
        raise PhaseOutputError("The outcome of the agent phase holds no result of the item")
    try:
        plan = _PLAN.validate_python(state.plan)
        target = _TARGET.validate_python(state.target)
    except ValidationError as exc:
        raise PhaseOutputError("The state file of the run is not of its model") from exc
    handed = outcome.result
    attempt = StageAttempt(target.item.number, **handed.attempt.model_dump())
    result = _result(handed, target, plan, state, checkout)
    return PlannedTargets.of([result], [attempt])


def publish_stage(
    store: RoadmapStore,
    state: StageJobState,
    planned: PlannedTargets,
    *,
    source: Path,
    now: datetime | None = None,
) -> tuple[StagePlan, StageApplied]:
    """`publish` of the result `planned` of the item of `state`, in the clone `source` of the Job:
    the writes of the result as the stage job makes them, after the writes of `prepare`. It gives
    the plan with the result and what the round wrote."""
    plan = _PLAN.validate_python(state.plan)
    target = _TARGET.validate_python(state.target)
    writer = StageWriter(store, source, now=now)
    writer.resume(plan, {target.item.number}, _APPLIED.validate_python(state.begun))
    writer.settle(target, planned.results()[0])
    return planned.into(plan), writer.applied()


__all__ = [
    "HandedAttempt",
    "HandedCall",
    "HandedFailure",
    "HandedGroup",
    "HandedPlan",
    "HandedPremise",
    "HandedResult",
    "HandedTrace",
    "StageAgentEnd",
    "StageAgentInput",
    "StageAgentOutcome",
    "StageJobState",
    "agent_stage",
    "end_state",
    "handed_result",
    "has_inputs",
    "planned_of",
    "prepare_stage",
    "publish_stage",
    "read_stage_outcome",
    "read_stage_state",
    "staged_commit",
    "write_agent_end",
]
