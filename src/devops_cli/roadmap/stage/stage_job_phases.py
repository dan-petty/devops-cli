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
  (`plan_targets`), and writes the result and the counts of the attempt to `out/outcome.json`.
  It reads no store. The GitHub reads of the planner (`read_issue`, `find_issues`, the files of a
  pull request that the plan names and the open pull requests that meet a cited path) use the
  session of the process. An agent phase in a process of its own holds no GitHub credential, so
  each of these reads answers that GitHub cannot be read, as a failed read does (#3240). #6705
  replaces the engine.
- `publish` (App key) reads the state file and the outcome as data (`read_run_file`), each text of
  the outcome masked. It refuses a result of another item and a change with a file outside the
  change folder of the item. Then it writes the result as the stage job does
  (`StageWriter.settle`): `push_plan` pushes the plan commit, and the draft pull request is opened
  or updated.

`stage_job.run_stage_job` runs the three in one process (`--phase all`): the state of `prepare`
stays in memory, and the run folder goes when the Job ends.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_STATE_FILE,
)
from devops_cli.core import clock
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.phases.files import RunFolders, read_output, read_run_file, write_json
from devops_cli.roadmap.refine.refine import body_dependencies
from devops_cli.roadmap.stage.stage import (
    PlannedTargets,
    PlannerReads,
    PlanResult,
    StageApplied,
    StageAttempt,
    StagedChange,
    StageFailure,
    StagePlan,
    StageTarget,
    StageWriter,
    begin_stage,
    parse_filters,
    plan_targets,
    premise_before_plan,
    store_reads,
)
from devops_cli.roadmap.stage.stage_phases import clone_staged
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
_PLANNED: TypeAdapter[PlannedTargets] = TypeAdapter(PlannedTargets)
_COMMENTS: TypeAdapter[tuple[IssueComment, ...]] = TypeAdapter(tuple[IssueComment, ...])


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageJobState(_Model):
    """`state/state.json`, which `prepare` writes and a separate `publish` reads: the item and its
    repository, the Job that the settings name and whether the check-out of the item named it at
    the start of the Job (`known`), the plan of the reads, what `StageWriter.begin` wrote, and the
    target of the item. `end` and `result` are the exit code and the result of a run that
    `prepare` ended: the agent phase then has no inputs, and `publish` writes nothing."""

    repo: str
    item: int
    job: str | None = None
    known: bool = False
    plan: dict[str, Any] = Field(default_factory=dict)
    begun: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] | None = None
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


class StageAgentOutcome(_Model):
    """`out/outcome.json` of the agent phase: its end, the results of the plan (`PlannedTargets`)
    for `planned`, and the masked message and the failure class of the error for `failed`."""

    end: StageAgentEnd
    planned: dict[str, Any] | None = None
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
    started = clock.monotonic()
    decided = premise_before_plan(repo, target)
    if decided is not None:
        writer.settle(target, decided)
        attempt = StageAttempt(target.item.number, seconds=round(clock.monotonic() - started))
        return PlannedTargets.of([decided], [attempt]).into(plan)
    reads = store_reads(store, plan, read.selected, source, read.planned)
    checkout = clone_staged(folders.work, repo, plan.sha)
    titles = {
        number: title
        for number in body_dependencies(target.item.body)
        if (title := reads.dependency_title(number)) is not None
    }
    inputs = StageAgentInput(
        repo=repo,
        checkout=str(checkout),
        sha=plan.sha,
        budget=plan.budget,
        target=_TARGET.dump_python(target, mode="json"),
        rejected=dict(reads.rejected),
        comments=[comment.model_dump(mode="json") for comment in reads.comments_on(item)],
        titles=titles,
        creates=dict(reads.open_creates()),
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
        ),
    )


def has_inputs(folders: RunFolders) -> bool:
    """Whether `prepare` handed the run of `folders` to the agent phase."""
    return (folders.work / CONST_ROADMAP_PHASE_INPUT_FILE).is_file()


def write_agent_end(folders: RunFolders, outcome: StageAgentOutcome) -> None:
    """Write `outcome` to `out/`, which the agent phase made at its start."""
    write_json(folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE, outcome)


def _without_answers(result: PlanResult) -> PlanResult:
    """`result` with no text of the tool answers in its trace: `publish` reads the counts and the
    calls of the trace only, and the answers would fill the outcome."""
    if isinstance(result, StagedChange):
        return replace(result, trace=replace(result.trace, tool_answers=[]))
    return result


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
    kept = PlannedTargets.of(
        (_without_answers(result) for result in planned.results()), planned.attempts
    )
    write_agent_end(
        folders,
        StageAgentOutcome(
            end=StageAgentEnd.PLANNED, planned=_PLANNED.dump_python(kept, mode="json")
        ),
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
    except (ValueError, ValidationError) as exc:
        raise PhaseOutputError("The output `outcome.json` is not of its model") from exc


def _in_change(path: str, change: str) -> bool:
    """Whether `path` is a file of the change folder `change`."""
    parts = PurePosixPath(path).parts
    folder = (*PurePosixPath(CONST_OPENSPEC_CHANGES_DIR).parts, change)
    return parts[: len(folder)] == folder and len(parts) > len(folder) and ".." not in parts


def _for_target(result: PlanResult, target: StageTarget) -> PlanResult:
    """`result` for `target`, the target that `prepare` read: the agent writes no target, no item
    and no record that `publish` uses. A change must hold only files of its change folder."""
    if isinstance(result, StageFailure):
        return replace(result, number=target.item.number, title=target.item.title, item=target.item)
    if isinstance(result, StagedChange):
        outside = [path for path in result.files if not _in_change(path, target.change)]
        if outside:
            raise PhaseOutputError(
                f"The change of the agent phase holds {len(outside)} file(s) outside its folder"
            )
    return replace(result, target=target)


def planned_of(outcome: StageAgentOutcome, state: StageJobState) -> PlannedTargets:
    """The result of the plan of the item of `state`, from an outcome that ended `planned`: one
    result, for the target that `prepare` read."""
    try:
        planned = _PLANNED.validate_python(outcome.planned)
        target = _TARGET.validate_python(state.target)
    except ValidationError as exc:
        raise PhaseOutputError("The output `outcome.json` is not of its model") from exc
    results = planned.results()
    if len(results) != 1:
        raise PhaseOutputError("The outcome of the agent phase holds no one result of the item")
    attempts = tuple(replace(attempt, number=target.item.number) for attempt in planned.attempts)
    return PlannedTargets.of([_for_target(results[0], target)], attempts[:1])


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
    "StageAgentEnd",
    "StageAgentInput",
    "StageAgentOutcome",
    "StageJobState",
    "agent_stage",
    "end_state",
    "has_inputs",
    "planned_of",
    "prepare_stage",
    "publish_stage",
    "read_stage_outcome",
    "read_stage_state",
    "write_agent_end",
]
