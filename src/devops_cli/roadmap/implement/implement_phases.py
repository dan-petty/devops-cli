"""The implement job on the phases `prepare`, `agent` and `publish` (#3702).

The phases work the issue branch as a developer does, on the run folder of `roadmap/phases`:

- `prepare` (App token, no code of the pull request) checks the claim, makes a plain clone of the
  repository on GitHub in `work/`, switches to the issue branch, sets Status In Progress and
  records the base and the lease: the base is the tip of the default branch, or the lease when
  the run makes no rebase of a pushed branch. It records `implement.base`, where the branch stood
  before the first Job of the item, and the summary of the plan once. It writes the state file in
  `state/` and the inputs of the agent in `work/`: the item, its comments, the clone and the
  rebase choice.
- `agent` (no GitHub credential) reads its inputs, rebases onto the base and settles each stop as a
  developer does, runs the steps of the open groups, the documents, the archive and the scoped
  checks, and writes the why of the body. It ends its leftover processes and writes the patches
  from the base: `work.patch` up to the archive commit, `archive.patch` with the archive commit
  alone and `after.patch` with the commits after it, so the archive stays its own commit. `outcome.json` holds the end of the run (done, returned,
  question or stopped) and the data of the run for the writes of `publish`.
- `publish` (App token, no code of the pull request) reads the outputs as data, masks each text of
  them, checks the claim, and makes the GitHub writes of the outcome (`RunReport`). For a run that
  pushes, it applies the patches in a new repository as commits of the bot and pushes with a lease
  on the old tip (`publish_patch`); it reads the title and the body from the new tree. It then
  opens or updates the draft, comments the run and sets the Status. It never marks the draft ready.
  A return to New first takes back what earlier Jobs of the item pushed (`_withdraw`).

`implement_round` runs the three phases in one process, which `--phase all` and the current Job
template use: the state of `prepare` stays in memory. #3700 runs each phase in its own container.
The marks of the run come at its end, from `publish`.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.config.constants import (
    CONST_GITHUB_CLONE_URL,
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_IMPLEMENT_RUNS_DIR,
    CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR,
    CONST_ROADMAP_PHASE_AFTER_PATCH_FILE,
    CONST_ROADMAP_PHASE_ARCHIVE_PATCH_FILE,
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_PATCH_MAX_BYTES,
    CONST_ROADMAP_PHASE_STATE_FILE,
    CONST_ROADMAP_PHASE_SUMMARY_FILE,
    CONST_ROADMAP_PHASE_WORK_PATCH_FILE,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import process_hardening
from devops_cli.core.repo import resolve_data_path
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubUnauthenticatedError,
    GitOperationError,
    RoadmapImplementError,
    ServiceStoppingError,
)
from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.exceptions.validation import ValidationError as BodyFormError
from devops_cli.github.client import PullRequestFile
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.openspec.project import uses_openspec
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.failure import FailureAction, FailureClass, StepName
from devops_cli.roadmap.implement.implement import GIT_OPERATION, ImplementTarget
from devops_cli.roadmap.implement.implement_amend import Amendment
from devops_cli.roadmap.implement.implement_comments import StepComments
from devops_cli.roadmap.implement.implement_disk import log_disk_use
from devops_cli.roadmap.implement.implement_pull import (
    Answer,
    ChangeFacts,
    Draft,
    DraftKind,
    draft_readiness,
)
from devops_cli.roadmap.implement.implement_report import RunReport, StopFacts
from devops_cli.roadmap.implement.implement_run import (
    _ARCHIVE_MESSAGE,
    _error_stop,
    _ItemRun,
    _RecordedSpend,
    _StopError,
    plan_commit_type,
    proposal_summary,
)
from devops_cli.roadmap.implement.implement_scoped_ci import ScopedResult
from devops_cli.roadmap.implement.implement_step import StepOutcome
from devops_cli.roadmap.implement.implement_strength import StrengthReport
from devops_cli.roadmap.implement.implement_trace import ImplementTrace, TraceDecodeError, decode
from devops_cli.roadmap.phases.checkout import clone_branch
from devops_cli.roadmap.phases.files import (
    AgentSummary,
    OutcomeKind,
    RunFolders,
    read_output,
    read_run_file,
    write_json,
)
from devops_cli.roadmap.phases.patch import write_patch
from devops_cli.roadmap.phases.publish import (
    NewTree,
    Published,
    PublishTarget,
    delete_branch,
    git_call,
    publish_patch,
    reset_branch,
)
from devops_cli.roadmap.project_profile import ProjectStep, resolve_profile
from devops_cli.roadmap.pull_form import BODY_MAX_CHARS, build_body, title_problems
from devops_cli.roadmap.pull_labels import declared_labels
from devops_cli.roadmap.stage.stage_change import (
    closing_keyword_in,
    delivery_title,
    plan_summary,
    safe_text,
)
from devops_cli.roadmap.status_sync import StatusFacts, write_status
from devops_cli.roadmap.step_metrics import observe_implement
from devops_cli.roadmap.steps.fix_checks_repair import merged_workflows
from devops_cli.roadmap.stores.store import ImplementRecordKey, ImplementResult, Item, RoadmapStore
from devops_cli.security.sanitizer import mask_secrets

_SHA = r"^[0-9a-f]{40}$"
_LEASE = r"^([0-9a-f]{40})?$"
_TARGET: TypeAdapter[ImplementTarget] = TypeAdapter(ImplementTarget)
_COMMENTS: TypeAdapter[StepComments] = TypeAdapter(StepComments)
# The message of the commit of the work of the run, which `publish` writes. The archive keeps
# its own message (`_ARCHIVE_MESSAGE`).
_WORK_MESSAGE = "{title} (#{number})"
# The patches of the agent phase, in the order of their commits: the work, the archive commit
# alone, and what follows the archive (#6670).
_PATCH_FILES = (
    CONST_ROADMAP_PHASE_WORK_PATCH_FILE,
    CONST_ROADMAP_PHASE_ARCHIVE_PATCH_FILE,
    CONST_ROADMAP_PHASE_AFTER_PATCH_FILE,
)
# The base of a branch that the first Job of the item made (`implement.base`).
_NEW_BRANCH = "new"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImplementState(_Model):
    """`state/state.json`, which `prepare` writes and a separate `publish` reads: the item, its
    branch and draft, the base of the patches, the lease, the default branch, the summary of the
    plan from the git log, and whether the target archives a change. `ended` says that `prepare`
    ended the run and wrote its end."""

    repo: str
    item: int
    branch: str = ""
    pull: int | None = None
    base: str = Field(default="", pattern=r"^([0-9a-f]{40})?$")
    lease: str = Field(default="", pattern=_LEASE)
    default: str = ""
    plan_summary: str | None = None
    archive_required: bool = False
    ended: bool = False


class AgentInput(_Model):
    """`work/input.json`, the inputs of the agent phase: the clone, the base of the patches, the
    tip of the default branch that the rebase goes onto, whether the run rebases, as `prepare`
    chose it with the base, the item and its comments."""

    repo: str
    checkout: str
    base: str
    onto: str
    rebase: bool = True
    default: str
    target: dict[str, Any]
    comments: dict[str, Any]


class ReturnKind(StrEnum):
    """Why a run returns its item to New (#5881): a premise that a step found false, or an `Adds:`
    line that names an identifier that the branch defines."""

    PREMISE_FAILED = "premise_failed"
    PREMISE_DEFINED = "premise_defined"


class RunData(_Model):
    """What the steps of the run did, for the comments and the record that `publish` writes."""

    outcomes: tuple[StepOutcome, ...] = ()
    amendments: tuple[Amendment, ...] = ()
    scoped: tuple[ScopedResult, ...] = ()
    scoped_notes: tuple[str, ...] = ()
    skipped_steps: tuple[ProjectStep, ...] = ()
    trace: str = ""
    strength: StrengthReport | None = None
    conflict_files: tuple[str, ...] = ()


class ImplementOutcome(_Model):
    """`out/outcome.json` of the implement agent phase: the end of the run, the data of the run,
    the stop or the return with its evidence, and the why of the body of the pull request."""

    kind: OutcomeKind
    run: RunData = RunData()
    stop: StopFacts | None = None
    returned: ReturnKind | None = None
    evidence: str = ""
    why: str = ""

    @model_validator(mode="after")
    def _complete(self) -> ImplementOutcome:
        if self.kind in (OutcomeKind.STOPPED, OutcomeKind.QUESTION) and self.stop is None:
            raise ValueError("a stopped outcome names its stop")
        if self.kind is OutcomeKind.RETURNED and self.returned is None:
            raise ValueError("a returned outcome names its return")
        return self


@dataclass(frozen=True)
class AgentTools:
    """What the agent phase runs with: the model and its window, the models of the tiers, the
    splitter of a group over the window, the rewriter of the body, and whether it rebases."""

    model: Any
    window: int
    model_for_tier: Callable[[str], Any] | None = None
    splitter: Any = None
    rewriter: Any = None
    rebase: bool = True


@dataclass(frozen=True)
class _Facts:
    """What `publish` reads from the new tree: the folder of the change, the title, the body and
    the tasks of the change, and the changed paths."""

    change: str
    archived: bool
    title: str
    body: str | None
    tasks: str
    changed: tuple[str, ...]


class _PublishStop(Exception):
    """`publish` stops the item: the facts of the stop."""

    def __init__(self, stop: StopFacts) -> None:
        super().__init__(stop.reason)
        self.stop = stop


class _Claimed(Exception):
    """An agent or a person holds the item at the claim check before the push."""

    def __init__(self, owner: str) -> None:
        super().__init__(owner)
        self.owner = owner


def _runs() -> Path:
    """The folder of the run folders of `--phase all`, in the data folder of the Job."""
    folder = resolve_data_path(load_settings().data.dir) / CONST_ROADMAP_IMPLEMENT_RUNS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _fresh(store: RoadmapStore, number: int) -> Item:
    held = store.item(number)
    if held is None:
        raise RoadmapImplementError(MESSAGES.roadmap.item_left_not_item)
    return held


# ── prepare ──


def prepare_implement(
    store: RoadmapStore,
    repo: str,
    target: ImplementTarget,
    folders: RunFolders,
    *,
    rebase: bool = True,
) -> ImplementState | ImplementResult:
    """`prepare` of one item: the state of the run, or how the run ended here. It runs git calls
    and GitHub calls only, and no program of the branch."""
    number = target.item.number
    report = RunReport(store, repo, target, target.pull)
    folders.make()
    if (owner := claimed_by(_fresh(store, number))) is not None:
        report.yield_to(owner, MESSAGES.roadmap.implement_boundary_start)
        write_json(
            folders.state / CONST_ROADMAP_PHASE_STATE_FILE,
            ImplementState(repo=repo, item=number, ended=True),
        )
        return ImplementResult.YIELDED
    clone = clone_branch(
        folders.work,
        url=CONST_GITHUB_CLONE_URL.format(repo=repo),
        issue=number,
        branch=target.branch,
    )
    (clone.path / CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR).mkdir(parents=True, exist_ok=True)
    marks: dict[Any, str | None] = {
        ImplementRecordKey.BRANCH: target.branch,
        ImplementRecordKey.TRACE: None,
        ImplementRecordKey.RESULT: None,
        ImplementRecordKey.CHECK_LOG: None,
        ImplementRecordKey.CONFLICT: None,
        ImplementRecordKey.PUBLISHED_SHA: None,
        ImplementRecordKey.REPAIR_ROUNDS: None,
    }
    if target.pull is not None:
        marks[ImplementRecordKey.PR] = str(target.pull)
    record = target.item.job_record
    if not record.get(ImplementRecordKey.BASE):
        # Where the branch stood before the first Job of the item pushed, for a return (#3677).
        marks[ImplementRecordKey.BASE] = clone.lease or _NEW_BRANCH
    if target.retry:
        for key in (
            ImplementRecordKey.STOPPED,
            ImplementRecordKey.FAILURE,
            ImplementRecordKey.LEFT_ACTION,
            ImplementRecordKey.CHECK,
            ImplementRecordKey.SPEND,
            ImplementRecordKey.SPEND_COUNTED,
        ):
            marks[key] = None
    write_status(store, _fresh(store, number), StatusFacts(job_active=True), marks=marks)
    try:
        proposal = f":(glob){CONST_OPENSPEC_CHANGES_DIR}/{number}-*/proposal.md"
        subject = git_call(
            clone.path,
            "log",
            "-1",
            "--diff-filter=A",
            "--format=%s",
            "HEAD",
            "--",
            proposal,
            home=folders.state,
        )
        preset = resolve_profile(clone.path, f"origin/{clone.default}").preset
        archive = bool(
            preset.archive_argv
            and uses_openspec(clone.path, f"origin/{clone.default}", operation=GIT_OPERATION)
        )
        comments = StepComments.read(store, number, clone.path)
    except (DevOpsCLIError, subprocess.TimeoutExpired) as exc:
        stop = _error_stop(MESSAGES.roadmap.implement_step_names["rebase"], exc)
        report.stop(_facts(stop), "")
        write_json(
            folders.state / CONST_ROADMAP_PHASE_STATE_FILE,
            ImplementState(repo=repo, item=number, ended=True),
        )
        return ImplementResult.STOPPED
    base = clone.lease if clone.lease and not rebase else clone.base
    summary = record.get(ImplementRecordKey.PLAN_SUMMARY) or plan_summary(subject.strip(), number)
    if summary and not record.get(ImplementRecordKey.PLAN_SUMMARY):
        store.set_marks(_fresh(store, number), {ImplementRecordKey.PLAN_SUMMARY: summary})
    state = ImplementState(
        repo=repo,
        item=number,
        branch=target.branch,
        pull=target.pull,
        base=base,
        lease=clone.lease,
        default=clone.default,
        plan_summary=summary,
        archive_required=archive,
    )
    write_json(folders.state / CONST_ROADMAP_PHASE_STATE_FILE, state)
    inputs = AgentInput(
        repo=repo,
        checkout=str(clone.path),
        base=base,
        onto=clone.base,
        rebase=rebase,
        default=clone.default,
        target=_TARGET.dump_python(target, mode="json"),
        comments=_COMMENTS.dump_python(comments, mode="json"),
    )
    write_json(folders.work / CONST_ROADMAP_PHASE_INPUT_FILE, inputs)
    return state


def _facts(stop: _StopError) -> StopFacts:
    """The facts of the stop of a step."""
    return StopFacts(
        step=stop.step,
        reason=stop.reason,
        last_message=stop.last_message,
        push=stop.push,
        kept_branch=stop.kept_branch,
        diff=stop.diff,
        diff_cut=stop.diff_cut,
        status=stop.status,
        check=stop.check,
        check_log=stop.check_log,
        repair_rounds=stop.repair_rounds,
        tier_changes=stop.tier_changes,
        failure_class=stop.failure_class,
        action_left=stop.action_left,
        conflict_files=stop.conflict_files,
    )


# ── agent ──


@dataclass(frozen=True)
class _OneItem:
    """The item of the inputs, as the steps read it: the agent phase reads no store."""

    held: Item

    def item(self, number: int) -> Item | None:
        return self.held if number == self.held.number else None


def _run_data(run: _ItemRun) -> RunData:
    return RunData(
        outcomes=tuple(run.outcomes),
        amendments=tuple(run.amendments),
        scoped=tuple(run.scoped),
        scoped_notes=tuple(run.scoped_notes),
        skipped_steps=tuple(run.skipped_steps),
        trace=run.trace.encode(),
        strength=run.strength,
        conflict_files=run.conflict_files,
    )


def _agent_outcome(run: _ItemRun) -> tuple[ImplementOutcome, bool]:
    """Run the item: the outcome, and whether its commits go to `publish`."""
    try:
        run.execute()
    except _StopError as stop:
        return _stopped(run, stop), stop.push
    except AICredentialsError, GitHubUnauthenticatedError, ServiceStoppingError:
        raise
    except (DevOpsCLIError, AIClientError, subprocess.TimeoutExpired) as exc:
        error = _error_stop(run.step, exc)
        return _stopped(run, error), error.push
    if run.returned:
        kind = (
            ReturnKind.PREMISE_DEFINED
            if run.returned == MESSAGES.roadmap.implement_comment_premise_defined
            else ReturnKind.PREMISE_FAILED
        )
        return (
            ImplementOutcome(
                kind=OutcomeKind.RETURNED, run=_run_data(run), returned=kind, evidence=run.evidence
            ),
            False,
        )
    return ImplementOutcome(kind=OutcomeKind.DONE, run=_run_data(run), why=run.why), True


def _stopped(run: _ItemRun, stop: _StopError) -> ImplementOutcome:
    """The outcome of a stop. The disk use of the home volume at the step goes to the log of the
    Job first (#6076)."""
    log_disk_use(run.path, stop.step)
    question = stop.failure_class is FailureClass.PLAN_DEFECT and (
        stop.action_left is FailureAction.WAIT
    )
    return ImplementOutcome(
        kind=OutcomeKind.QUESTION if question else OutcomeKind.STOPPED,
        run=_run_data(run),
        stop=_facts(stop),
    )


def agent_implement(folders: RunFolders, tools: AgentTools) -> None:
    """The agent phase of one item: the run in the clone of `prepare`, then the patches and the
    outcome. A run folder whose `prepare` ended the run holds no inputs, and the phase writes
    nothing. It reads no store and makes no GitHub call."""
    inputs_file = folders.work / CONST_ROADMAP_PHASE_INPUT_FILE
    if not inputs_file.is_file():
        return
    inputs = AgentInput.model_validate_json(inputs_file.read_text(encoding="utf-8"))
    target = _TARGET.validate_python(inputs.target)
    run = _ItemRun(
        _OneItem(target.item),
        inputs.repo,
        Path(inputs.checkout),
        target,
        tools.model,
        tools.window,
        inputs.default,
        onto=inputs.onto,
        model_for_tier=tools.model_for_tier,
        splitter=tools.splitter,
        rewriter=tools.rewriter,
        rebase=inputs.rebase,
        comments=_COMMENTS.validate_python(inputs.comments),
    )
    outcome, push = _agent_outcome(run)
    if push and outcome.kind is not OutcomeKind.DONE:
        run._drop_uncommitted()
    if load_settings().roadmap.implement.in_runner:
        process_hardening.end_leftover_processes()
    out = folders.make_out()
    patches = [out / name for name in _PATCH_FILES]
    if push:
        # The work up to the archive commit, the archive commit alone, and what follows it.
        archived = run.archive_commit(inputs.base)
        ends = [f"{archived}^", archived, "HEAD"] if archived else ["HEAD", "HEAD", "HEAD"]
        for start, end, patch in zip([inputs.base, *ends[:2]], ends, patches, strict=True):
            write_patch(run.path, start, patch, head=end)
    else:
        for patch in patches:
            patch.write_bytes(b"")
    write_json(out / CONST_ROADMAP_PHASE_OUTCOME_FILE, outcome)
    write_json(out / CONST_ROADMAP_PHASE_SUMMARY_FILE, AgentSummary())


# ── publish ──


def _masked(value: Any) -> Any:
    """`value`, a value of JSON, with each text masked."""
    if isinstance(value, str):
        return mask_secrets(value)
    if isinstance(value, list):
        return [_masked(item) for item in value]
    if isinstance(value, dict):
        # A key names a tool or a tier in a line of a comment, so it goes on one line too.
        return {safe_text(mask_secrets(str(key))): _masked(item) for key, item in value.items()}
    return value


def read_implement_outcome(folders: RunFolders) -> ImplementOutcome:
    """`outcome.json` of the agent phase, read as data, with each text masked."""
    data = read_output(
        folders, CONST_ROADMAP_PHASE_OUTCOME_FILE, limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES
    )
    try:
        outcome = ImplementOutcome.model_validate(_masked(json.loads(data)))
        if outcome.run.trace:
            decode(outcome.run.trace)
    except (ValueError, ValidationError, TraceDecodeError) as exc:
        raise PhaseOutputError("The output `outcome.json` is not of its model") from exc
    if outcome.stop is not None:
        # The step names a line of a comment and the mark `implement.stopped`.
        stop = replace(outcome.stop, step=safe_text(outcome.stop.step))
        outcome = outcome.model_copy(update={"stop": stop})
    return outcome


def _report(store: RoadmapStore, state: ImplementState, outcome: ImplementOutcome) -> RunReport:
    item = _fresh(store, state.item)
    target = ImplementTarget(item=item, branch=state.branch, pull=state.pull)
    run = outcome.run
    held = item.job_record.get(ImplementRecordKey.SPEND)
    return RunReport(
        store,
        state.repo,
        target,
        state.pull,
        outcomes=list(run.outcomes),
        amendments=list(run.amendments),
        scoped=list(run.scoped),
        scoped_notes=list(run.scoped_notes),
        skipped_steps=list(run.skipped_steps),
        trace=decode(run.trace) if run.trace else ImplementTrace(),
        strength=run.strength,
        conflict_files=run.conflict_files,
        earlier=_RecordedSpend.model_validate_json(held) if held else _RecordedSpend(),
    )


def _change(tree: NewTree, number: int) -> tuple[str, bool] | None:
    """The folder of the change of item `number` in the new tree, and whether it is archived."""
    archived = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}-{number}-")
    if names := [name for name in tree.names(CONST_OPENSPEC_ARCHIVE_DIR) if archived.match(name)]:
        return f"{CONST_OPENSPEC_ARCHIVE_DIR}/{names[0]}", True
    if names := [n for n in tree.names(CONST_OPENSPEC_CHANGES_DIR) if n.startswith(f"{number}-")]:
        return f"{CONST_OPENSPEC_CHANGES_DIR}/{names[0]}", False
    return None


def _title(
    store: RoadmapStore, item: Item, summary: str | None, changed: tuple[str, ...], step: str
) -> str:
    """The title of the pull request (#2714, #4127, #5341): the type of the changed paths, a
    declared scope and the summary of the plan; else, or when that title holds a closing keyword,
    the summary of the title of the issue. A title that the form refuses stops the item before the
    push (#3292)."""
    declared = declared_labels(store, ref=None)
    if summary is not None:
        issue_kind = commit_type(item.title)
        kind = plan_commit_type(changed, issue_kind) if (changed and issue_kind) else issue_kind
        candidate = delivery_title(item.title, declared, summary, kind)
        # The squash merge takes the title as its subject, so a closing keyword would close
        # another issue (#6670).
        if not title_problems(candidate, declared) and closing_keyword_in(candidate) is None:
            return candidate
    title = delivery_title(item.title, declared)
    if problems := title_problems(title, declared):
        raise _PublishStop(
            StopFacts(
                step=step,
                reason=MESSAGES.roadmap.implement_stop_title_refused.format(
                    problems=" ".join(problems), title=title
                ),
                push=False,
            )
        )
    return title


def _body(item: Item, change: str, why: str) -> str:
    """The body of the pull request from the why of the agent, checked again (#3215): masked, on
    one line, short enough, and with no closing keyword; else the title of the item."""
    room = BODY_MAX_CHARS - len(f"\n\nCloses #{item.number}\n\nChange: `{change}/`")
    for text in (safe_text(mask_secrets(why)), safe_text(item.title)):
        if not text or len(text) > room or closing_keyword_in(text) is not None:
            continue
        try:
            return build_body(why=text, issue=item.number, change=change)
        except BodyFormError:
            continue
    raise _PublishStop(
        StopFacts(
            step=MESSAGES.roadmap.implement_step_names["pull_request"],
            reason=MESSAGES.roadmap.implement_stop_body_refused.format(problems=change),
            failure_class=FailureClass.REFUSED_REPLY,
            push=False,
        )
    )


def _describe(
    store: RoadmapStore, state: ImplementState, item: Item, tree: NewTree, why: str
) -> _Facts:
    """The facts of the new tree: the change, the title, the body and the tasks."""
    found = _change(tree, state.item)
    proposal = tree.text(f"{found[0]}/proposal.md") if found else None
    summary = proposal_summary(proposal, "summary") or state.plan_summary
    summary = summary or proposal_summary(proposal, "changes")
    # The title of a draft that exists is a write of the pull request; a new branch gets it at
    # its first push.
    step = MESSAGES.roadmap.implement_step_names["pull_request" if state.pull else "push"]
    title = _title(store, item, summary, tree.changed, step)
    if found is None:
        return _Facts("", False, title, None, "", tree.changed)
    change, archived = found
    tasks = tree.text(f"{change}/tasks.md") or ""
    return _Facts(change, archived, title, _body(item, change, why), tasks, tree.changed)


def _push(
    store: RoadmapStore,
    state: ImplementState,
    outcome: ImplementOutcome,
    report: RunReport,
    folders: RunFolders,
    *,
    metadata: bool,
) -> tuple[Published | None, _Facts | None]:
    """The publish of the patches: the commit and the facts of the new tree.
    The claim check runs right before the push; for a draft that exists, `metadata` writes its
    title and body first (#3991)."""
    number = state.item
    item = _fresh(store, number)
    patches = [
        (
            read_output(folders, name, limit=CONST_ROADMAP_PHASE_PATCH_MAX_BYTES),
            message.format(title=safe_text(item.title), number=number),
        )
        for name, message in zip(
            _PATCH_FILES, (_WORK_MESSAGE, _ARCHIVE_MESSAGE, _WORK_MESSAGE), strict=True
        )
    ]
    session = get_github_session()
    target = PublishTarget(
        url=CONST_GITHUB_CLONE_URL.format(repo=state.repo),
        branch=state.branch,
        base=state.base,
        lease=item.job_record.get(ImplementRecordKey.PUBLISHED_SHA) or state.lease,
        author=session.login,
        email=session.commit_email,
        workflow_paths=merged_workflows(state.repo, state.default, number),
    )
    held: list[_Facts] = []

    def before_push(tree: NewTree) -> None:
        if (owner := claimed_by(_fresh(store, number))) is not None:
            raise _Claimed(owner)
        facts = _describe(store, state, item, tree, outcome.why)
        if metadata and state.pull is not None and facts.body is not None:
            report.delivery_metadata(state.pull, facts.title, facts.body)
        held.append(facts)

    published = publish_patch(target, patches, before_push=before_push, scratch=folders.root)
    if published is not None:
        store.set_marks(_fresh(store, number), {ImplementRecordKey.PUBLISHED_SHA: published.commit})
    return published, (held[0] if held else None)


def _open_draft(
    store: RoadmapStore, state: ImplementState, published: Published, title: str
) -> int:
    """Open the draft pull request of a new branch and record it. A draft that GitHub refuses
    takes the branch off `origin` again when this run made it (`prepare` found no branch), so no
    branch stays without a pull request."""
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    try:
        opened = open_or_update(
            OpenRequest(
                repo=state.repo,
                head=state.branch,
                base=state.default,
                title=title,
                body=MESSAGES.roadmap.implement_pull_body_draft.format(number=state.item),
                kind="delivery",
                item=state.item,
                store=store,
                lookup_existing=False,
                retry_refused=False,
            )
        )
    except DevOpsCLIError as exc:
        if not state.lease:
            delete_branch(
                PublishTarget(
                    url=CONST_GITHUB_CLONE_URL.format(repo=state.repo),
                    branch=state.branch,
                    base=published.commit,
                    lease=published.commit,
                    author="",
                    email="",
                )
            )
        raise _PublishStop(
            StopFacts(
                step=MESSAGES.roadmap.implement_step_names["push"],
                reason=MESSAGES.roadmap.implement_stop_draft_failed.format(
                    branch=state.branch, output=mask_secrets(str(exc))
                ),
                push=False,
            )
        ) from exc
    store.set_marks(_fresh(store, state.item), {ImplementRecordKey.PR: str(opened.number)})
    return opened.number


def _require_complete(store: RoadmapStore, state: ImplementState, pull: int, facts: _Facts) -> None:
    """Stop the item when `draft_readiness` refuses the draft `pull` with no check runs (#6559):
    the change is present, each group is ticked, it is archived where the target requires it, and
    a change of the stage prompt holds its eval scores. The facts come from the new tree."""
    status = get_github_session().client.get_pull_status(state.repo, pull)
    change: ChangeFacts | None = None
    if facts.change and facts.archived:
        change = ChangeFacts(archived=True, tasks_text=facts.tasks)
    elif facts.change:
        change = ChangeFacts(
            archived=False, tasks_text=facts.tasks, archive_required=state.archive_required
        )
    files = tuple(PullRequestFile(filename=name, status="modified") for name in facts.changed)
    draft = Draft(
        kind=DraftKind.IMPLEMENT,
        pull=status,
        item=_fresh(store, state.item),
        change=change,
        files=files,
    )
    readiness = draft_readiness(draft)
    if readiness.answer is not Answer.READY:
        raise _PublishStop(
            StopFacts(step=MESSAGES.roadmap.implement_step_names["ready"], reason=readiness.reason)
        )


def _publish_done(
    store: RoadmapStore,
    state: ImplementState,
    outcome: ImplementOutcome,
    report: RunReport,
    folders: RunFolders,
) -> ImplementResult:
    """The writes of a run that reached its end: the push, the draft, the comment of the run, the
    readiness of the draft and the end at the draft. The push and the draft are the sample of the
    step `publish` of the metrics."""
    with observe_implement(state.repo, StepName.PUBLISH):
        published, facts = _push(store, state, outcome, report, folders, metadata=True)
        if published is None or facts is None:
            raise _PublishStop(
                StopFacts(
                    step=MESSAGES.roadmap.implement_step_names["push"],
                    reason=MESSAGES.roadmap.implement_stop_publish_empty,
                    push=False,
                )
            )
        # The pushed tree passed the scoped checks (#4070).
        store.set_marks(
            _fresh(store, state.item), {ImplementRecordKey.CHECKED_SHA: published.commit}
        )
        pull = state.pull
        if pull is None:
            pull = _open_draft(store, state, published, facts.title)
            report.pull = pull
    if state.pull is None and facts.body is not None:
        report.delivery_metadata(pull, facts.title, facts.body)
    report.comment(pull)
    _require_complete(store, state, pull, facts)
    report.end_drafted(pull, published.commit)
    return ImplementResult.DRAFTED


def _publish_stop(
    store: RoadmapStore,
    state: ImplementState,
    outcome: ImplementOutcome,
    report: RunReport,
    folders: RunFolders,
) -> ImplementResult:
    """The writes of a stopped run: the push of the groups that passed, then the stop (#3645)."""
    stop = outcome.stop
    if stop is None:
        raise PhaseOutputError("The outcome of the agent phase names no stop")
    note = ""
    if stop.push:
        try:
            published, facts = _push(
                store, state, outcome, report, folders, metadata=stop.kept_branch
            )
            if published is not None and facts is not None and state.pull is None:
                report.pull = _open_draft(store, state, published, facts.title)
            if published is not None and stop.kept_branch:
                note = MESSAGES.roadmap.implement_stop_kept_branch.format(
                    branch=state.branch, sha=published.commit
                )
        except _Claimed:
            raise
        except _PublishStop as exc:
            note = MESSAGES.roadmap.implement_stop_push_failed.format(
                output=mask_secrets(exc.stop.reason)
            )
        except (DevOpsCLIError, GitOperationError) as exc:
            note = MESSAGES.roadmap.implement_stop_push_failed.format(output=mask_secrets(str(exc)))
    report.stop(stop, note)
    return ImplementResult.STOPPED


def publish_implement(
    store: RoadmapStore, state: ImplementState, folders: RunFolders
) -> ImplementResult | None:
    """`publish` of one item: the GitHub writes of the outcome of the agent phase. A run that
    `prepare` ended gets none, and a second `publish` of the same run, whose first one wrote a
    result, gets none either."""
    if state.ended:
        return None
    item = _fresh(store, state.item)
    record = item.job_record
    # `prepare` cleared the result: a result here is the end of an earlier `publish` of this run.
    if ended := record.get(ImplementRecordKey.RESULT):
        return ImplementResult(ended)
    if state.pull is None and (recorded := record.get(ImplementRecordKey.PR)):
        # An earlier `publish` of this run opened the draft of the new branch.
        state = state.model_copy(update={"pull": int(recorded)})
    outcome = read_implement_outcome(folders)
    report = _report(store, state, outcome)
    try:
        if (owner := claimed_by(item)) is not None:
            raise _Claimed(owner)
        return _publish_outcome(store, state, outcome, report, folders)
    except _Claimed as claimed:
        report.yield_to(claimed.owner, _boundary(outcome))
        return ImplementResult.YIELDED
    except _PublishStop as exc:
        report.stop(exc.stop, "")
        return ImplementResult.STOPPED
    except AICredentialsError, GitHubUnauthenticatedError, ServiceStoppingError:
        raise
    except (DevOpsCLIError, subprocess.TimeoutExpired) as exc:
        step = MESSAGES.roadmap.implement_step_names["push"]
        report.stop(replace(_facts(_error_stop(step, exc)), push=False), "")
        return ImplementResult.STOPPED


def _publish_outcome(
    store: RoadmapStore,
    state: ImplementState,
    outcome: ImplementOutcome,
    report: RunReport,
    folders: RunFolders,
) -> ImplementResult:
    """The GitHub writes of each kind of outcome: a return, a draft or a stop."""
    if outcome.kind is OutcomeKind.RETURNED:
        return _publish_return(state, outcome, report)
    if outcome.kind is OutcomeKind.DONE:
        return _publish_done(store, state, outcome, report, folders)
    return _publish_stop(store, state, outcome, report, folders)


def _boundary(outcome: ImplementOutcome) -> str:
    """Where the run was when an agent or a person claimed the item: the step of the stop, or the
    end of the run."""
    if outcome.stop is None:
        return MESSAGES.roadmap.implement_boundary_end
    return MESSAGES.roadmap.implement_boundary_stop.format(step=outcome.stop.step)


def _withdraw(state: ImplementState, base: str | None) -> None:
    """Take back what earlier Jobs of the item pushed, before a return to New (#3677). A branch that
    the first Job found goes back to `base`; a branch that it made (`new`) goes, with its draft.
    Each push has a lease on the tip that `prepare` found, so a push of a person stays."""
    if not base or not state.lease or state.lease == base:
        return
    target = PublishTarget(
        url=CONST_GITHUB_CLONE_URL.format(repo=state.repo),
        branch=state.branch,
        base=state.lease if base == _NEW_BRANCH else base,
        lease=state.lease,
        author="",
        email="",
    )
    if base != _NEW_BRANCH:
        reset_branch(target)
        return
    delete_branch(target)
    if state.pull is not None:
        get_github_session().client.close_pull(state.repo, state.pull)


def _publish_return(
    state: ImplementState, outcome: ImplementOutcome, report: RunReport
) -> ImplementResult:
    """The return of the item to New with the evidence of the agent (#5881), after the withdraw
    of the pushes of earlier Jobs. A withdraw that fails stops the item and returns nothing."""
    try:
        _withdraw(state, report.fresh().job_record.get(ImplementRecordKey.BASE))
    except DevOpsCLIError as exc:
        reason = MESSAGES.roadmap.implement_stop_withdraw_failed.format(
            branch=state.branch, output=mask_secrets(str(exc))
        )
        step = MESSAGES.roadmap.implement_step_names["push"]
        raise _PublishStop(StopFacts(step=step, reason=reason, push=False)) from exc
    texts = MESSAGES.roadmap
    defined = outcome.returned is ReturnKind.PREMISE_DEFINED
    template = (
        texts.implement_comment_premise_defined
        if defined
        else texts.implement_comment_premise_failed
    )
    report.return_to_new(template, outcome.evidence)
    return ImplementResult.RETURNED


def _read_state(folders: RunFolders) -> ImplementState:
    data = read_run_file(
        folders,
        folders.state,
        CONST_ROADMAP_PHASE_STATE_FILE,
        limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    )
    try:
        return ImplementState.model_validate_json(data)
    except ValidationError as exc:
        raise PhaseOutputError(
            f"The state file of the run is not of its model: {exc.error_count()} error(s)"
        ) from None


def publish_phase(
    store: RoadmapStore, folders: RunFolders, *, repo: str, item: int
) -> ImplementResult | None:
    """`--phase publish` for item `item` of `repo`: the state file, read as data, must name that
    item, and the branch that `prepare` recorded on the item."""
    state = _read_state(folders)
    if (state.repo, state.item) != (repo, item):
        raise PhaseOutputError("The state file of the run names another item")
    if state.ended:
        return None
    recorded = _fresh(store, item).job_record.get(ImplementRecordKey.BRANCH)
    if recorded != state.branch:
        raise PhaseOutputError("The state file of the run names another branch")
    return publish_implement(store, state, folders)


def implement_round(
    store: RoadmapStore, repo: str, target: ImplementTarget, tools: AgentTools
) -> ImplementResult:
    """The three phases of one item in one process, on a new run folder of the data folder
    (`--phase all`). The state of `prepare` stays in memory, and the run folder goes with its
    clone when the round ends."""
    with tempfile.TemporaryDirectory(prefix="devops-implement-", dir=_runs()) as root:
        folders = RunFolders(Path(root))
        prepared = prepare_implement(store, repo, target, folders, rebase=tools.rebase)
        if isinstance(prepared, ImplementResult):
            return prepared
        agent_implement(folders, tools)
        return publish_implement(store, prepared, folders) or ImplementResult.STOPPED


__all__ = [
    "AgentInput",
    "AgentTools",
    "ImplementOutcome",
    "ImplementState",
    "ReturnKind",
    "RunData",
    "agent_implement",
    "implement_round",
    "prepare_implement",
    "publish_implement",
    "publish_phase",
    "read_implement_outcome",
]
