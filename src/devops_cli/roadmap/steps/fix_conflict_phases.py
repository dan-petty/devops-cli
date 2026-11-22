"""The step `fix-conflict` on the phases `prepare`, `agent` and `publish` (#6703, #3702).

Each phase reads and writes the run folder (`roadmap/phases`), as the phases of implement and
fix-checks do:

- `prepare` (App key, no code of the pull request) takes the round that `run_fix_conflict` admitted.
  It clones the repository plainly into `work/` on the head branch (`clone_branch`), which fails
  the round on a commit past main that the App did not write, and records `onto`, the tip of main that the clone
  read, and the lease, the judged head. It finds the conflicted files and the release rule with
  `git merge-tree`, which runs no code of the pull request. A round that ends there gives its
  report: no conflict, a cap, or the plan without `--confirm`, whose clone makes no check of the
  authors, which needs the App. Else it adds one to the rounds of the record, as each round that
  reaches the agent counts (#6620), also when the agent phase ends with no outcome, and writes the
  state file and the inputs of the agent.
- `agent` (model key only, no GitHub call) runs tier 1: it rebases onto `onto` and settles each stop
  with the shared rules (`rebase_onto`). A skipped archive commit is archived again, and the
  generated documents and `uv.lock` take the side of main and are made again, which runs code of
  the pull request. Then the strict validation of the specs, and the check that a commit is past
  main. It writes the patches from `onto`: the work up to the archive commit, the archive commit
  alone, and the commits after it. A round that does not end settled, also on an error, aborts the
  rebase and gives the branch back the judged head: one cleanup path.
- `publish` (App key) reads the outcome as data, checks the admission bounds again with the judged
  head, and pushes the patches as commits of the bot on `onto` with a lease on the judged head
  (`publish_patch`). It works in a new repository that no code of the pull request touched, so a
  hook or a setting that tier 1 wrote into the clone changes nothing. `publish` writes the result
  of the round into the record, a refusal too, and adds no round.

`repair_round` runs the three phases in one process (`--phase all`); the state stays in memory.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from devops_cli.config.constants import (
    CONST_GITHUB_CLONE_URL,
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
from devops_cli.exceptions import DevOpsCLIError, GitOperationError
from devops_cli.exceptions.roadmap import PhaseOutputError, PublishRefusedError
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.phases.checkout import clone_branch
from devops_cli.roadmap.phases.files import (
    AgentOutcome,
    AgentSummary,
    OutcomeKind,
    RunFolders,
    read_outcome,
    read_output,
    read_run_file,
    write_json,
)
from devops_cli.roadmap.phases.patch import write_patch
from devops_cli.roadmap.phases.publish import NewTree, PublishTarget, publish_patch
from devops_cli.roadmap.phases.rebase import (
    ARCHIVE_MESSAGE,
    archive_change,
    archive_commit,
    commit_changed,
    rebase_in_progress,
    rebase_onto,
)
from devops_cli.roadmap.project_profile import resolve_profile
from devops_cli.roadmap.steps import fix_conflict
from devops_cli.roadmap.steps.fix_checks_repair import merged_workflows
from devops_cli.roadmap.steps.fix_conflict import (
    ConflictRound,
    FixConflictReport,
    FixConflictResult,
)
from devops_cli.roadmap.stores.store import RoadmapStore
from devops_cli.security.sanitizer import mask_secrets

# The operation that a failed git call of the phases names.
_OPERATION = "roadmap fix-conflict"
_SHA = r"^[0-9a-f]{40}$"
# The patches of the agent phase, in the order of their commits: the work up to the archive
# commit, the archive commit alone, and the commits after it.
_PATCH_FILES = (
    CONST_ROADMAP_PHASE_WORK_PATCH_FILE,
    CONST_ROADMAP_PHASE_ARCHIVE_PATCH_FILE,
    CONST_ROADMAP_PHASE_AFTER_PATCH_FILE,
)
# The message of a commit of the work of the branch, from the title of the item.
_WORK_MESSAGE = "{title} (#{number})"
# The results that an outcome of the agent phase may give.
_AGENT_RESULTS = frozenset(
    {FixConflictResult.RESOLVED, FixConflictResult.STOPPED, FixConflictResult.FAILED}
)
_RELEASE = "Conflict on a release path"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConflictState(_Model):
    """`state/state.json`, which `prepare` writes and a separate `publish` reads: that the round
    ended in `prepare`, or the facts of the round: the judged status, the item, `onto`, the
    conflicted files, the key of the record and the rounds that `prepare` recorded."""

    repo: str
    pull: int
    item: int = 0
    rounds: int = 0
    ended: bool = False
    status: dict[str, Any] | None = None
    onto: str = Field(default="", pattern=r"^([0-9a-f]{40})?$")
    files: tuple[str, ...] = ()
    key: str = ""


class ConflictInput(_Model):
    """`work/input.json`, the inputs of the agent phase: the clone, `onto`, the judged head, the
    item, whether the release rule stops the round, and whether tier 1 settles a stop."""

    checkout: str
    onto: str = Field(pattern=_SHA)
    lease: str = Field(pattern=_SHA)
    item: int
    release: bool = False
    tier1: bool = True


@dataclass(frozen=True)
class PreparedRound:
    """What `publish` takes from `prepare`: the admitted round, `onto`, the conflicted files, the
    key of the record and the rounds that `prepare` recorded."""

    round: ConflictRound
    onto: str
    files: tuple[str, ...]
    key: str
    rounds: int


# ── prepare ──


def _end(
    folders: RunFolders, judged: ConflictRound, report: FixConflictReport
) -> FixConflictReport:
    """End the round in `prepare`: a state that says so, and the report for the Job."""
    write_json(
        folders.state / CONST_ROADMAP_PHASE_STATE_FILE,
        ConflictState(repo=judged.repo, pull=judged.pull, ended=True),
    )
    return report


def prepare_round(
    store: RoadmapStore, judged: ConflictRound, folders: RunFolders, *, confirm: bool
) -> PreparedRound | FixConflictReport:
    """The part of `prepare` after the admission: the clone, the conflicted files, the caps, the
    release rule and, with `confirm`, the round in the record, the state file and the inputs of
    the agent. The report of a round that ends here, or the prepared round."""
    folders.make()
    status = judged.status
    try:
        clone = clone_branch(
            folders.work,
            url=CONST_GITHUB_CLONE_URL.format(repo=judged.repo),
            issue=judged.item_num or judged.pull,
            branch=status.head_ref,
            authors=confirm,
        )
    except GitOperationError as exc:
        return _end(
            folders, judged, judged.report(FixConflictResult.FAILED, mask_secrets(str(exc)))
        )
    if clone.lease != status.head_sha:
        reason = f"The head branch is at {clone.lease[:12]}, not at the judged head"
        return _end(folders, judged, judged.report(FixConflictResult.FAILED, reason))
    has_conflict, files = fix_conflict.check_merge_tree_conflict(
        clone.path, clone.base, clone.lease
    )
    if not has_conflict:
        report = judged.report(FixConflictResult.NO_CONFLICT, "No merge conflict detected")
        return _end(folders, judged, report)
    settings = judged.settings
    if cap := fix_conflict.check_conflict_caps(judged.rounds, files, judged.prev_files, settings):
        report = judged.report(FixConflictResult.STOPPED, cap, files=files)
        return _end(folders, judged, report)
    release = fix_conflict.release_conflict(clone.path, clone.base, clone.lease)
    if not confirm:
        reason = fix_conflict.plan_reason(files, settings.tier1_mode, release)
        return _end(folders, judged, judged.report(FixConflictResult.PLANNED, reason, files=files))
    key = f"{clone.base}:{status.head_sha}"
    rounds = judged.rounds + 1
    fix_conflict.record_fix_conflict_marks(
        store, judged.item, key=key, rounds=rounds, files=files, result=FixConflictResult.FAILED
    )
    state = ConflictState(
        repo=judged.repo,
        pull=judged.pull,
        item=judged.item_num or 0,
        rounds=rounds,
        status=status.model_dump(mode="json"),
        onto=clone.base,
        files=tuple(files),
        key=key,
    )
    write_json(folders.state / CONST_ROADMAP_PHASE_STATE_FILE, state)
    inputs = ConflictInput(
        checkout=str(clone.path),
        onto=clone.base,
        lease=clone.lease,
        item=judged.item_num or judged.pull,
        release=release,
        tier1=settings.tier1_mode == "on",
    )
    write_json(folders.work / CONST_ROADMAP_PHASE_INPUT_FILE, inputs)
    return PreparedRound(judged, clone.base, tuple(files), key, rounds)


def prepare_phase(
    store: RoadmapStore,
    client: Any,
    repo: str,
    pull: int,
    *,
    head: str | None,
    folders: RunFolders,
) -> FixConflictReport | None:
    """`--phase prepare` of a confirmed round: the admission, then `prepare_round`. A round that
    ends here gives its report, which the command prints for the Job."""
    judged = fix_conflict.admit_round(store, client, repo, pull, head=head)
    if isinstance(judged, FixConflictReport):
        folders.make()
        write_json(
            folders.state / CONST_ROADMAP_PHASE_STATE_FILE,
            ConflictState(repo=repo, pull=pull, ended=True),
        )
        return judged
    prepared = prepare_round(store, judged, folders, confirm=True)
    return prepared if isinstance(prepared, FixConflictReport) else None


# ── agent ──


def _program(path: Path, argv: Sequence[str]) -> None:
    """Run a program of tier 1 in the checkout, which runs code of the pull request. Raises
    `RoadmapImplementError` with the reason of the round when it fails."""
    done = fix_conflict.run_program(path, argv)
    if done.returncode != 0:
        raise fix_conflict.tier1_failure(argv, done)


def _rebase(path: Path, inputs: ConflictInput) -> AgentOutcome | None:
    """The rebase onto `onto`: with tier 1, each stop settled by the shared rules and a skipped
    archive commit archived again; without it, any stop ends the round. None when the branch sits
    on `onto`, else the outcome of the stop."""
    if not inputs.tier1:
        try:
            git(path, "rebase", "--quiet", inputs.onto, operation=_OPERATION)
        except GitOperationError:
            return _stopped(fix_conflict.NOT_SETTLED)
        return None
    preset = resolve_profile(path, inputs.onto).preset

    def generate(argv: Sequence[str]) -> None:
        _program(path, argv)

    def commit(message: str) -> None:
        commit_changed(path, message, operation=_OPERATION)

    ended = rebase_onto(
        path, inputs.onto, inputs.item, generate, docs=preset.docs_step, operation=_OPERATION
    )
    if not ended.started:
        return _stopped(mask_secrets(str(ended.error)))
    if ended.error is not None:
        return _stopped(mask_secrets(str(ended.error)) if ended.stuck else fix_conflict.NOT_SETTLED)
    if ended.skipped:
        archive_change(path, inputs.item, preset, generate, commit, docs=preset.docs_step)
    return None


def _settle(path: Path, inputs: ConflictInput) -> AgentOutcome:
    """Tier 1 on the clone: the release rule, the rebase (`_rebase`), the strict validation and
    the check that a commit is past main."""
    if inputs.release:
        return _stopped(_RELEASE)
    if (stopped := _rebase(path, inputs)) is not None:
        return stopped
    if not fix_conflict.validate_strict_specs(path):
        return _failed("openspec validate --specs --strict failed")
    if git(path, "rev-list", "--count", f"{inputs.onto}..HEAD", operation=_OPERATION) == "0":
        # Never push the tip of the default branch over the pull request.
        return _failed("The rebase left no commit past the tip of the default branch")
    return AgentOutcome(kind=OutcomeKind.DONE, result=FixConflictResult.RESOLVED)


def _stopped(reason: str) -> AgentOutcome:
    return AgentOutcome(kind=OutcomeKind.STOPPED, result=FixConflictResult.STOPPED, reason=reason)


def _failed(reason: str) -> AgentOutcome:
    return AgentOutcome(kind=OutcomeKind.STOPPED, result=FixConflictResult.FAILED, reason=reason)


def _round(path: Path, inputs: ConflictInput) -> AgentOutcome:
    """One round of tier 1 with one cleanup path (#6620): a round that does not end settled, also
    on an error, aborts the rebase and gives the branch back the judged head. A failed git call or
    a failed program of tier 1 is a stop; any other error goes on after the cleanup."""
    outcome = _failed("The round ended with an error")
    try:
        outcome = _settle(path, inputs)
    except DevOpsCLIError as exc:
        outcome = _stopped(mask_secrets(str(exc)))
    finally:
        if outcome.kind is not OutcomeKind.DONE:
            if rebase_in_progress(path, operation=_OPERATION):
                git(path, "rebase", "--abort", operation=_OPERATION)
            git(path, "reset", "-q", "--hard", inputs.lease, operation=_OPERATION)
    return outcome


def _write_patches(path: Path, inputs: ConflictInput, out: Path) -> None:
    """The patches from `onto`: the work up to the archive commit of the item, the archive commit
    alone, and the commits after it."""
    archived = archive_commit(path, inputs.onto, inputs.item, operation=_OPERATION)
    ends = [f"{archived}^", archived, "HEAD"] if archived else ["HEAD", "HEAD", "HEAD"]
    for start, end, name in zip([inputs.onto, *ends[:2]], ends, _PATCH_FILES, strict=True):
        write_patch(path, start, out / name, head=end)


def agent_phase(folders: RunFolders) -> None:
    """`--phase agent`: the round of tier 1 in the clone, then the patches and the outcome. A run
    folder whose `prepare` ended the round holds no inputs, and the phase writes nothing."""
    inputs_file = folders.work / CONST_ROADMAP_PHASE_INPUT_FILE
    if not inputs_file.is_file():
        return
    inputs = ConflictInput.model_validate_json(inputs_file.read_text(encoding="utf-8"))
    path = Path(inputs.checkout)
    outcome = _round(path, inputs)
    if load_settings().roadmap.implement.in_runner:
        process_hardening.end_leftover_processes()
    out = folders.make_out()
    if outcome.kind is OutcomeKind.DONE:
        _write_patches(path, inputs, out)
    else:
        for name in _PATCH_FILES:
            (out / name).write_bytes(b"")
    write_json(out / CONST_ROADMAP_PHASE_OUTCOME_FILE, outcome)
    write_json(out / CONST_ROADMAP_PHASE_SUMMARY_FILE, AgentSummary())


# ── publish ──


def _result(outcome: AgentOutcome) -> FixConflictResult:
    """The result of `outcome`, from the enum of the step only."""
    try:
        result = FixConflictResult(outcome.result)
    except ValueError as exc:
        raise PhaseOutputError(
            "The outcome of the agent phase names no result of the step"
        ) from exc
    if result not in _AGENT_RESULTS or (result is FixConflictResult.RESOLVED) != (
        outcome.kind is OutcomeKind.DONE
    ):
        raise PhaseOutputError("The outcome of the agent phase names no result of the step")
    return result


def _text(text: str) -> str:
    """A reason of the agent for the report: masked and on one line."""
    return mask_secrets(" ".join(text.split()))


class _AdmissionError(Exception):
    """The admission bounds, checked again right before the push, end the round."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _patches(folders: RunFolders, title: str, number: int) -> list[tuple[bytes, str]]:
    """The patches of the agent, each with the message of its commit, the empty ones left out."""
    work = _WORK_MESSAGE.format(title=mask_secrets(" ".join(title.split())), number=number)
    messages = (work, ARCHIVE_MESSAGE.format(number=number), work)
    patches = [
        (read_output(folders, name, limit=CONST_ROADMAP_PHASE_PATCH_MAX_BYTES), message)
        for name, message in zip(_PATCH_FILES, messages, strict=True)
    ]
    return [(patch, message) for patch, message in patches if patch.strip()]


def publish_round(
    store: RoadmapStore, client: Any, prepared: PreparedRound, folders: RunFolders
) -> FixConflictReport:
    """The publish of the outcome of the agent phase for the prepared round, as the module text
    says. It writes the result into the record with the rounds of `prepare`, a refusal too."""
    judged = prepared.round
    status = judged.status
    outcome = read_outcome(folders)
    result = _result(outcome)
    number = judged.item_num or judged.pull
    item = store.item(judged.item_num) if judged.item_num else None
    rounds = prepared.rounds

    def record(result: FixConflictResult) -> None:
        resolved = result is FixConflictResult.RESOLVED
        fix_conflict.record_fix_conflict_marks(
            store,
            item,
            key=prepared.key,
            rounds=rounds,
            files=[] if resolved else prepared.files,
            result=result,
        )

    if result is not FixConflictResult.RESOLVED:
        record(result)
        return judged.report(result, _text(outcome.reason), rounds=rounds, files=prepared.files)

    def before_push(_tree: NewTree) -> None:
        live: PullStatus = client.get_pull_status(judged.repo, judged.pull)
        fresh = store.item(judged.item_num) if judged.item_num else None
        if bounds := fix_conflict.admission_bounds(live, fresh, expected_head=status.head_sha):
            raise _AdmissionError(bounds)

    session = get_github_session()
    default = status.default_branch or status.base_ref
    title = item.title if item is not None else status.title
    target = PublishTarget(
        url=CONST_GITHUB_CLONE_URL.format(repo=judged.repo),
        branch=status.head_ref,
        base=prepared.onto,
        lease=status.head_sha,
        author=session.login,
        email=session.commit_email,
        workflow_paths=merged_workflows(judged.repo, default, number) if item is not None else (),
    )
    try:
        published = publish_patch(
            target, _patches(folders, title, number), before_push=before_push, scratch=folders.root
        )
    except _AdmissionError as exc:
        record(FixConflictResult.REFUSED)
        reason = exc.reason
        return judged.report(FixConflictResult.REFUSED, reason, rounds=rounds, files=prepared.files)
    except (GitOperationError, PublishRefusedError) as exc:
        record(FixConflictResult.STOPPED)
        reason = mask_secrets(str(exc))
        return judged.report(FixConflictResult.STOPPED, reason, rounds=rounds, files=prepared.files)
    if published is None:
        record(FixConflictResult.FAILED)
        reason = "The rebase made no change to push"
        return judged.report(FixConflictResult.FAILED, reason, rounds=rounds, files=prepared.files)
    record(FixConflictResult.RESOLVED)
    return judged.report(FixConflictResult.RESOLVED, "", head=published.commit, rounds=rounds)


def _read_state(folders: RunFolders) -> ConflictState:
    """The state file of the run, read as data (`read_run_file`). Its text never reaches an error."""
    data = read_run_file(
        folders,
        folders.state,
        CONST_ROADMAP_PHASE_STATE_FILE,
        limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    )
    try:
        return ConflictState.model_validate_json(data)
    except ValidationError as exc:
        raise PhaseOutputError(
            f"The state file of the run is not of its model: {exc.error_count()} error(s)"
        ) from None


def publish_phase(
    store: RoadmapStore,
    client: Any,
    folders: RunFolders,
    *,
    repo: str,
    pull: int,
    head: str | None = None,
) -> FixConflictReport | None:
    """`--phase publish` on the pull request `pull` of `repo`: the state file, read as data, must
    name that pull request. A round that `prepare` ended gives no report here, as `prepare`
    printed it. Else the round is admitted again on the judged head, with no cap, as `prepare`
    counted the round, and goes to `publish_round`. A refusal goes into the record."""
    state = _read_state(folders)
    if (state.repo, state.pull) != (repo, pull):
        raise PhaseOutputError("The state file of the run names another pull request")
    if state.ended:
        return None
    if state.status is None:
        raise PhaseOutputError("The state file of the run names no judged pull request")
    judged_head = PullStatus.model_validate(state.status).head_sha
    if head is not None and head != judged_head:
        raise PhaseOutputError("The state file of the run names another head")
    judged = fix_conflict.admit_round(store, client, repo, pull, head=judged_head, cap=False)
    if isinstance(judged, FixConflictReport):
        fix_conflict.record_fix_conflict_marks(
            store,
            state.item or None,
            key=state.key,
            rounds=state.rounds,
            files=state.files,
            result=judged.result,
        )
        return replace(judged, rounds=state.rounds, files=state.files)
    prepared = PreparedRound(judged, state.onto, state.files, state.key, state.rounds)
    return publish_round(store, client, prepared, folders)


def repair_round(
    store: RoadmapStore, client: Any, judged: ConflictRound, *, confirm: bool
) -> FixConflictReport:
    """The three phases in one process, on a new run folder (`--phase all`). Without `confirm` the
    round ends in `prepare` with its plan: no code of the pull request runs."""
    with tempfile.TemporaryDirectory(prefix="devops-fix-conflict-") as root:
        folders = RunFolders(Path(root))
        prepared = prepare_round(store, judged, folders, confirm=confirm)
        if isinstance(prepared, FixConflictReport):
            return prepared
        agent_phase(folders)
        return publish_round(store, client, prepared, folders)


__all__ = [
    "ConflictInput",
    "ConflictState",
    "PreparedRound",
    "agent_phase",
    "prepare_phase",
    "prepare_round",
    "publish_phase",
    "publish_round",
    "repair_round",
]
