"""The step `fix-checks` on the phases `prepare`, `agent` and `publish` (#3702, #6601).

The fix-checks Job is the first step on the phases (`roadmap/phases`). Each phase reads and writes
the run folder:

- `prepare` (App key, no agent code) judges the round (`judge_round`): the bounds, the claim, the
  checks, the caps and the failed log. A round that ends there gives its report for the Job, and
  writes a state file that says so.
  A round that needs a repair clones the repository into `work/` on the head branch
  (`Repair.checkout`), and writes the state file (`state/`) and the inputs of the agent
  (`work/input.json`). It runs git and GitHub calls only: no `uv`, no hook and no fixer.
- `agent` (model key only) reads its inputs, rebases a branch that is behind the default branch
  onto the tip that `prepare` read (#6639), runs tier 1, the scope check and the model fix in the
  checkout, and writes the patches, `outcome.json` and `summary.json`. It makes no GitHub call: the
  model fix reads the item from the inputs.
- `publish` (App key) reads the outputs of the agent as data (`read_run_file`). It checks the
  judged round against the pull request as GitHub holds it: the head branch, the item and the
  judged head. It builds the target of the push from GitHub and `prepare`: the head branch and the
  judged head of the pull request, the base (the judged head, or the `onto` that `prepare`
  recorded), the bot of the App, the workflow files that the merged plan of the item names on the
  default branch (`Repair.workflows`), and the repository on GitHub. A separate `publish` reads the
  state file as data, and takes the failed check and its count of errors from GitHub. It checks
  the claim (`check_preconditions`), applies the patches in a new repository, writes one commit of
  the bot for each patch that is not empty, checks the claim again, and pushes with a lease on the
  judged head (`publish_patch`). Then it writes the record of the round and the
  comment that names the files, as the step did before.

The lease is the judged head. A branch that holds the tip of the default branch needs no rebase:
the base is the judged head, and the fix is one commit on it. A branch that is behind it is rebased
onto that tip, which `prepare` records as `onto`, so `publish` replaces the branch: the base is
`onto`, and the patches are the work of the branch up to its archive commit, the archive commit
alone, the commits after it, and the fix, each one commit. When only main causes the failure, the
round pushes the rebased branch with no fix, with the result `rebased`, so the new head gets new
checks. The agent phase needs no network git call: the clone of `prepare` holds `onto` (#6601). `repair_round` runs the three phases in one process, which `--phase all`
uses: the state of `prepare` stays in memory, so `publish` reads no file of the run but the
outputs of the agent, and the run folder goes when the round ends. The runner template runs each
phase in its own container (#3700).
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
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
    CONST_ROADMAP_PHASE_PATCH_FILE,
    CONST_ROADMAP_PHASE_PATCH_MAX_BYTES,
    CONST_ROADMAP_PHASE_STATE_FILE,
    CONST_ROADMAP_PHASE_SUMMARY_FILE,
    CONST_ROADMAP_PHASE_WORK_PATCH_FILE,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import process_hardening
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import (
    PhaseOutputError,
    PublishRefusedError,
)
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.check_verdict import CheckBucket, read_check_runs
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.implement.implement_pull import DraftKind, failed_log, kind_of
from devops_cli.roadmap.phases.files import (
    AgentOutcome,
    AgentSummary,
    OutcomeFile,
    OutcomeKind,
    RunFolders,
    read_outcome,
    read_output,
    read_run_file,
    write_json,
)
from devops_cli.roadmap.phases.patch import write_patch
from devops_cli.roadmap.phases.publish import NewTree, Published, PublishTarget
from devops_cli.roadmap.phases.rebase import ARCHIVE_MESSAGE, archive_commit, holds
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.steps.fix_checks import (
    MARKER,
    FixChecksReport,
    FixRound,
    PullCheckout,
    Repair,
    check_preconditions,
    count_errors,
    end_round,
    head_moved,
    judge_round,
    named_files,
    record_outcome,
    shown_check,
)
from devops_cli.roadmap.stores.store import FixChecksRecordKey, FixChecksResult, Item, RoadmapStore
from devops_cli.security.sanitizer import mask_secrets

# The most characters of a reason of the agent that the report keeps: the head names the cause,
# and the tail holds the error line, so a longer reason loses its middle.
_REASON_HEAD = 500
_REASON_TAIL = 1500
# The operation that a failed git call of the step names.
_OPERATION = "roadmap.fix_checks"
# A commit, or empty for a branch that needs no rebase.
_ONTO = r"^([0-9a-f]{40})?$"
# The patches of the work of a rebased branch, in the order of their commits: the work up to the
# archive commit, the archive commit alone, and the commits after it. The fix follows them.
_BRANCH_PATCHES = (
    CONST_ROADMAP_PHASE_WORK_PATCH_FILE,
    CONST_ROADMAP_PHASE_ARCHIVE_PATCH_FILE,
    CONST_ROADMAP_PHASE_AFTER_PATCH_FILE,
)
# The message of a commit of the work of a rebased branch, from the title of the item.
_WORK_MESSAGE = "{title} (#{number})"
# The results that an outcome of the agent phase may give.
_AGENT_RESULTS = frozenset(
    {
        FixChecksResult.REPAIRED,
        FixChecksResult.REBASED,
        FixChecksResult.FAILED,
        FixChecksResult.STOPPED,
    }
)
# The reason of a round that pushed the rebased branch with no fix (#6639).
_REBASED = (
    "Rebased onto main with no fix: the change of the branch does not cause the failure, so the "
    "new head gets new checks"
)


class FixTier(StrEnum):
    """The fixer that repaired the check: tier 1 or the model."""

    TIER1 = "tier1"
    MODEL = "model"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FixState(_Model):
    """`state/state.json`, which `prepare` writes and a separate `publish` reads: that the round
    ended in `prepare`, or the facts of the round that `prepare` judged. `publish` builds the
    target of the push from the pull request as GitHub holds it then, and checks these facts
    against it: the state names no branch, author or workflow file that `publish` pushes."""

    repo: str
    pull: int
    item: int = 0
    ended: bool = False
    status: dict[str, Any] | None = None
    check: str = ""
    onto: str = Field(default="", pattern=_ONTO)


@dataclass(frozen=True)
class JudgedRound:
    """What `publish` takes from `prepare`: the pull request, the item, the judged status, the
    failed check, the count of errors of its log, and `onto`, the tip of the default branch that
    the agent rebased the branch onto, or empty. `--phase all` keeps it in memory; a separate
    `publish` builds it from the state file and checks each part against GitHub
    (`_judged_from_state`)."""

    repo: str
    pull: int
    item: int
    status: PullStatus
    check: str
    errors: int
    onto: str = ""


class AgentInput(_Model):
    """`work/input.json`, the inputs of the agent phase: the checkout, the judged head, the tip of
    the default branch to rebase onto (empty for a branch that holds it), the item, the failed
    check and its log, and whether the pull request is a plan."""

    checkout: str
    base: str
    onto: str = Field(default="", pattern=_ONTO)
    item_num: int
    item: dict[str, Any] | None
    check: str
    log: str
    is_plan: bool


@dataclass(frozen=True)
class _OneItem:
    """The item of the inputs, as the model fix reads it: the agent phase reads no store."""

    held: Item | None

    def item(self, number: int) -> Item | None:
        return self.held if self.held is not None and number == self.held.number else None


class _ClaimedError(Exception):
    """The claim check before the push found that the round must stop: `report` says why."""

    def __init__(self, report: FixChecksReport) -> None:
        super().__init__(report.reason)
        self.report = report


def _text(text: str) -> str:
    """A reason of the agent for the report: masked, on one line, with its head and its tail when
    it is long."""
    line = mask_secrets(" ".join(text.split()))
    if len(line) <= _REASON_HEAD + _REASON_TAIL:
        return line
    return f"{line[:_REASON_HEAD]} ... {line[-_REASON_TAIL:]}"


def _read_state(folders: RunFolders) -> FixState:
    """The state file of the run, read as data (`read_run_file`). Its text never reaches an error."""
    data = read_run_file(
        folders,
        folders.state,
        CONST_ROADMAP_PHASE_STATE_FILE,
        limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    )
    try:
        return FixState.model_validate_json(data)
    except ValidationError as exc:
        raise PhaseOutputError(
            f"The state file of the run is not of its model: {exc.error_count()} error(s)"
        ) from None


def _is_plan(item: Item | None, pull: int, status: PullStatus) -> bool:
    return kind_of(item, pull, status.title) == DraftKind.STAGE_PLAN


def prepare_round(
    facts: FixRound, repair: Repair, folders: RunFolders
) -> tuple[PullCheckout, JudgedRound]:
    """The part of `prepare` after the judgment: the checkout, the state file and the inputs of
    the agent. Gives the checkout and the judged round, which `--phase all` keeps in memory."""
    folders.make()
    checkout = repair.checkout(facts.status, facts.item_num, folders.work)
    is_plan = _is_plan(facts.item, facts.pull, facts.status)
    head = facts.status.head_sha
    behind = checkout.base and not holds(checkout.path, checkout.base, head, operation=_OPERATION)
    onto = checkout.base if behind else ""
    state = FixState(
        repo=facts.repo,
        pull=facts.pull,
        item=facts.item_num,
        status=facts.status.model_dump(mode="json"),
        check=facts.check,
        onto=onto,
    )
    write_json(folders.state / CONST_ROADMAP_PHASE_STATE_FILE, state)
    inputs = AgentInput(
        checkout=str(checkout.path),
        base=head,
        onto=onto,
        item_num=facts.item_num,
        item=facts.item.model_dump(mode="json") if facts.item is not None else None,
        check=facts.check,
        log=facts.log,
        is_plan=is_plan,
    )
    write_json(folders.work / CONST_ROADMAP_PHASE_INPUT_FILE, inputs)
    return checkout, JudgedRound(
        facts.repo,
        facts.pull,
        facts.item_num,
        facts.status,
        facts.check,
        facts.errors,
        onto,
    )


def prepare_phase(
    store: RoadmapStore,
    client: Any,
    repo: str,
    pull: int,
    *,
    head: str | None,
    check: str | None,
    repair: Repair,
    folders: RunFolders,
) -> FixChecksReport | None:
    """`--phase prepare`: judge the round, and write its state and the inputs of the agent to the
    run folder. A round that ends here gives its report, which the command prints for the Job,
    and a state that says so."""
    judged = judge_round(store, client, repo, pull, head=head, check=check, confirm=True)
    if isinstance(judged, FixChecksReport):
        folders.make()
        write_json(
            folders.state / CONST_ROADMAP_PHASE_STATE_FILE,
            FixState(repo=repo, pull=pull, ended=True),
        )
        return judged
    prepare_round(judged, repair, folders)
    return None


def _fix(
    path: Path, inputs: AgentInput, item: Item | None, repair: Repair
) -> tuple[AgentOutcome, str]:
    """The rebase of a branch that is behind the default branch, then tier 1, the scope check and
    the model fix, in the checkout `path`. Gives the outcome and the head of the branch before the
    fixers: the rebased head, or the judged head."""
    tip = inputs.base
    if inputs.onto:
        rebased = repair.rebase(path, inputs.onto, inputs.item_num)
        if not rebased.done:
            stopped = AgentOutcome(
                kind=OutcomeKind.STOPPED, result=FixChecksResult.STOPPED, reason=rebased.reason
            )
            return stopped, tip
        tip = git(path, "rev-parse", "HEAD", operation=_OPERATION)
    return _fixers(path, inputs, item, repair), tip


def _fixers(path: Path, inputs: AgentInput, item: Item | None, repair: Repair) -> AgentOutcome:
    """Tier 1, then the scope check and the model fix, in the checkout `path`."""
    number = inputs.item_num
    tier1 = repair.tier1(path, number, inputs.check, inputs.log)
    if tier1.done:
        return AgentOutcome(
            kind=OutcomeKind.DONE,
            result=FixChecksResult.REPAIRED,
            detail=FixTier.TIER1,
            files=tuple(OutcomeFile(path=name, reason="") for name in tier1.files),
        )
    verdict = repair.scope(path, number, inputs.log, inputs.is_plan)
    if not verdict.in_scope:
        if inputs.onto:
            # Only main causes the failure: the rebase is the repair, as an update of the branch.
            return AgentOutcome(
                kind=OutcomeKind.DONE, result=FixChecksResult.REBASED, reason=verdict.stop_reason()
            )
        return AgentOutcome(
            kind=OutcomeKind.STOPPED, result=FixChecksResult.STOPPED, reason=verdict.stop_reason()
        )
    model = repair.model(_OneItem(item))(
        path, number, inputs.check, inputs.log, verdict.extra_paths
    )
    if not model.done:
        reason = "Model repair failed" + (f": {model.reason}" if model.reason else "")
        return AgentOutcome(kind=OutcomeKind.STOPPED, result=FixChecksResult.FAILED, reason=reason)
    return AgentOutcome(
        kind=OutcomeKind.DONE,
        result=FixChecksResult.REPAIRED,
        detail=FixTier.MODEL,
        files=tuple(OutcomeFile(path=cause.path, reason=cause.reason) for cause in verdict.caused),
    )


def _write_patches(
    path: Path, inputs: AgentInput, tip: str, out: Path, repair: Repair, *, fix: bool
) -> None:
    """The patches of the agent. For a rebased branch: the work from `onto` up to the archive
    commit of the item, the archive commit alone, and the commits after it up to `tip`, the rebased
    head. Then the fix from `tip`, or an empty fix when `fix` is False. A branch that needs no
    rebase has no work patch, and its fix goes on the judged head."""
    if inputs.onto:
        archived = archive_commit(path, inputs.onto, inputs.item_num, operation=_OPERATION)
        ends = [f"{archived}^", archived, tip] if archived else [tip, tip, tip]
        starts = [inputs.onto, *ends[:2]]
        for start, end, name in zip(starts, ends, _BRANCH_PATCHES, strict=True):
            write_patch(path, start, out / name, head=end)
    else:
        for name in _BRANCH_PATCHES:
            (out / name).write_bytes(b"")
    if fix:
        repair.patch(path, tip, out / CONST_ROADMAP_PHASE_PATCH_FILE)
    else:
        (out / CONST_ROADMAP_PHASE_PATCH_FILE).write_bytes(b"")


def agent_phase(folders: RunFolders, repair: Repair) -> None:
    """`--phase agent`: the fixers in the checkout, then the patch and the outcome. A run folder
    whose `prepare` ended the round holds no inputs, and the phase writes nothing."""
    inputs_file = folders.work / CONST_ROADMAP_PHASE_INPUT_FILE
    if not inputs_file.is_file():
        return
    inputs = AgentInput.model_validate_json(inputs_file.read_text(encoding="utf-8"))
    item = Item.model_validate(inputs.item) if inputs.item is not None else None
    path = Path(inputs.checkout)
    outcome, tip = _fix(path, inputs, item, repair)
    if load_settings().roadmap.implement.in_runner:
        process_hardening.end_leftover_processes()
    out = folders.make_out()
    if outcome.kind is OutcomeKind.DONE:
        fix = outcome.result != FixChecksResult.REBASED
        _write_patches(path, inputs, tip, out, repair, fix=fix)
    write_json(out / CONST_ROADMAP_PHASE_OUTCOME_FILE, outcome)
    write_json(out / CONST_ROADMAP_PHASE_SUMMARY_FILE, AgentSummary())


def _result(outcome: AgentOutcome) -> tuple[FixChecksResult, FixTier | None]:
    """The result and the tier of `outcome`, from the enums of the step only."""
    try:
        result = FixChecksResult(outcome.result)
        tier = FixTier(outcome.detail) if outcome.detail else None
    except ValueError as exc:
        raise PhaseOutputError(
            "The outcome of the agent phase names no result of the step"
        ) from exc
    if result not in _AGENT_RESULTS or (result is FixChecksResult.REPAIRED) != (tier is not None):
        raise PhaseOutputError("The outcome of the agent phase names no result of the step")
    return result, tier


def _claim(client: Any, store: RoadmapStore, facts: FixRound) -> FixChecksReport | None:
    """The claim check of `publish`: the bounds of the step on the pull request and the item as
    GitHub holds them now, with the judged head (`check_preconditions`)."""
    status: PullStatus = client.get_pull_status(facts.repo, facts.pull)
    item = store.item(facts.item_num)
    return check_preconditions(status, facts.status.head_sha, item, facts.repo, facts.pull)


def _message(facts: FixRound, tier: FixTier) -> str:
    """The message of the commit that `publish` writes, from the facts of the round only, with the
    name of the check on one line and masked, so the message is one line."""
    check = mask_secrets(" ".join(facts.check.split()))
    if tier is FixTier.TIER1:
        return f"style: apply the fixers of tier 1 for check {check} (#{facts.item_num})"
    return f"fix: make check {check} pass (#{facts.item_num})"


def _live_round(
    store: RoadmapStore, client: Any, judged: JudgedRound
) -> FixRound | FixChecksReport:
    """The facts of the round from the pull request and the item as GitHub holds them now, checked
    against the judged round: the head branch, the item and the judged head. The report of a round
    that the check ends."""
    live: PullStatus = client.get_pull_status(judged.repo, judged.pull)
    parsed = parse_branch(live.head_ref)
    item_num = parsed.issue if parsed else judged.pull
    item = store.item(item_num)
    if claimed := check_preconditions(live, judged.status.head_sha, item, judged.repo, judged.pull):
        return claimed
    record = item.job_record if item is not None else {}
    heads = [head for head in (record.get(FixChecksRecordKey.HEADS) or "").split(",") if head]
    if live.head_sha not in heads:
        heads.append(live.head_sha)
    facts = FixRound(
        judged.repo,
        judged.pull,
        live,
        item_num,
        item,
        heads,
        judged.check,
        "",
        int(record.get(FixChecksRecordKey.ROUNDS) or 0),
        judged.errors,
    )
    if live.head_ref != judged.status.head_ref or item_num != judged.item:
        return facts.report(
            FixChecksResult.STOPPED,
            "The head branch of the pull request is not the branch that prepare judged",
        )
    return facts


def _target(repair: Repair, facts: FixRound, base: str) -> PublishTarget:
    """The target of the push, from the pull request as GitHub holds it now and from what
    `publish` reads itself: the repository on GitHub, the bot, and the workflow files that the
    merged plan of the item names on the default branch. A plan draft writes no workflow file.
    `base` is the judged head, or the tip of the default branch of a rebased branch, which the
    push replaces; the lease is the judged head."""
    status = facts.status
    author, email = repair.author()
    workflows = (
        ()
        if _is_plan(facts.item, facts.pull, status)
        else repair.workflows(facts.repo, status.default_branch or status.base_ref, facts.item_num)
    )
    return PublishTarget(
        url=CONST_GITHUB_CLONE_URL.format(repo=facts.repo),
        branch=status.head_ref,
        base=base,
        lease=status.head_sha,
        author=author,
        email=email,
        workflow_paths=workflows,
    )


def _push(
    store: RoadmapStore,
    client: Any,
    facts: FixRound,
    repair: Repair,
    patches: Sequence[tuple[bytes, str]],
    base: str,
) -> Published | FixChecksReport:
    """The publish of the patches on `base`, with the claim check right before the push: the
    commit, or the report of a round that the claim, a refusal, a move of the head or an empty
    patch ends."""

    def before_push(_tree: NewTree) -> None:
        if report := _claim(client, store, facts):
            raise _ClaimedError(report)

    try:
        published = repair.publish(_target(repair, facts, base), patches, before_push)
    except _ClaimedError as claim:
        return claim.report
    except PublishRefusedError as exc:
        end_round(store, facts, FixChecksResult.STOPPED)
        return facts.report(FixChecksResult.STOPPED, str(exc))
    except GitOperationError:
        if not head_moved(client, facts):
            raise
        return facts.report(FixChecksResult.SKIPPED, "Head has moved: the lease refused the push")
    if published is None:
        end_round(store, facts, FixChecksResult.FAILED)
        return facts.report(FixChecksResult.FAILED, "The repair made no commit to push")
    return published


def _read_patch(folders: RunFolders, name: str = CONST_ROADMAP_PHASE_PATCH_FILE) -> bytes:
    return read_output(folders, name, limit=CONST_ROADMAP_PHASE_PATCH_MAX_BYTES)


def _branch_patches(folders: RunFolders, facts: FixRound, onto: str) -> list[tuple[bytes, str]]:
    """The patches of the work of a branch that the agent rebased onto `onto`, each with the
    message of its commit, the empty ones left out. A round with no rebase takes none, whatever
    the agent wrote."""
    if not onto:
        return []
    title = facts.item.title if facts.item is not None else facts.status.title
    work = _WORK_MESSAGE.format(title=mask_secrets(" ".join(title.split())), number=facts.item_num)
    messages = (work, ARCHIVE_MESSAGE.format(number=facts.item_num), work)
    patches = [
        (_read_patch(folders, name), message)
        for name, message in zip(_BRANCH_PATCHES, messages, strict=True)
    ]
    return [(patch, message) for patch, message in patches if patch.strip()]


def _publish_rebase(
    store: RoadmapStore,
    client: Any,
    facts: FixRound,
    folders: RunFolders,
    repair: Repair,
    onto: str,
) -> FixChecksReport:
    """The publish of a branch that the agent rebased with no fix (#6639): its work, archive and
    later commits on `onto`, with a lease on the judged head, as an update of the branch. An
    outcome that says rebased for a round with no rebase is refused."""
    if not onto:
        raise PhaseOutputError("The outcome says rebased, and the round made no rebase")
    published = _push(store, client, facts, repair, _branch_patches(folders, facts, onto), onto)
    if isinstance(published, FixChecksReport):
        return published
    rounds = facts.rounds + 1
    record_outcome(
        store,
        facts.item,
        facts.status.head_sha,
        facts.check,
        FixChecksResult.REBASED,
        facts.heads,
        rounds=rounds,
        errors=facts.errors,
    )
    return facts.report(FixChecksResult.REBASED, _REBASED, head=published.commit, rounds=rounds)


def publish_round(
    store: RoadmapStore,
    client: Any,
    judged: JudgedRound,
    folders: RunFolders,
    repair: Repair,
) -> FixChecksReport:
    """The publish of the outcome of the agent phase for the judged round, as the module text
    says."""
    facts = _live_round(store, client, judged)
    if isinstance(facts, FixChecksReport):
        return facts
    outcome = read_outcome(folders)
    result, tier = _result(outcome)
    if result is FixChecksResult.REBASED:
        return _publish_rebase(store, client, facts, folders, repair, judged.onto)
    if tier is None:
        end_round(store, facts, result)
        return facts.report(result, _text(outcome.reason))
    patches = [
        *_branch_patches(folders, facts, judged.onto),
        (_read_patch(folders), _message(facts, tier)),
    ]
    base = judged.onto or facts.status.head_sha
    published = _push(store, client, facts, repair, patches, base)
    if isinstance(published, FixChecksReport):
        return published
    rounds = facts.rounds + 1
    record_outcome(
        store,
        facts.item,
        facts.status.head_sha,
        facts.check,
        FixChecksResult.REPAIRED,
        facts.heads,
        rounds=rounds,
        errors=facts.errors,
    )
    tier1 = tier is FixTier.TIER1
    # A rebased branch pushes its work too, so tier 1 names the files of its own commit.
    fixed = [held.path for held in outcome.files] if judged.onto else published.paths
    named = (
        [(path, "") for path in fixed]
        if tier1
        else [(held.path, held.reason) for held in outcome.files]
    )
    if body := named_files(facts.check, tier1=tier1, files=named):
        post(
            Target(facts.repo, facts.pull, client=client),
            MARKER,
            shown_check(facts.check),
            body,
        )
    done = "Tier 1 resolved check with 0 model requests" if tier1 else "Tier 2 model repaired check"
    return facts.report(FixChecksResult.REPAIRED, done, head=published.commit, rounds=rounds)


def _judged_from_state(
    client: Any, state: FixState, repo: str, pull: int
) -> JudgedRound | FixChecksReport:
    """The judged round of a separate `publish`, from the state file, with each part that GitHub
    can say taken from GitHub: the check must be a failed check of the judged head, by the name
    that GitHub gives, and the count of errors comes from the log of that check, which `publish`
    reads itself."""
    if (state.repo, state.pull) != (repo, pull) or state.status is None:
        raise PhaseOutputError("The state file of the run names another pull request")
    judged = PullStatus.model_validate(state.status)
    owner, name = repo.split("/", 1)
    failed = [
        run
        for run in read_check_runs(owner, name, judged.head_sha).items
        if run.bucket is CheckBucket.FAIL and run.name == state.check
    ]
    if not failed:
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.SKIPPED,
            head=judged.head_sha,
            reason="The check of the state file is no failed check of the judged head",
        )
    errors = count_errors(failed_log(repo, failed[0]))
    return JudgedRound(repo, pull, state.item, judged, failed[0].name, errors, state.onto)


def publish_phase(
    store: RoadmapStore,
    client: Any,
    folders: RunFolders,
    repair: Repair,
    *,
    repo: str,
    pull: int,
    head: str | None = None,
    check: str | None = None,
) -> FixChecksReport | None:
    """`--phase publish` on the pull request `pull` of `repo`: the state file, read as data, must
    name that pull request. A round that `prepare` ended gives no report here, as `prepare`
    printed it; a judgment with no write refuses a state that says so while a repair or a ready
    mark is due. A round with an outcome goes to `publish_round`."""
    state = _read_state(folders)
    if (state.repo, state.pull) != (repo, pull):
        raise PhaseOutputError("The state file of the run names another pull request")
    if state.ended:
        judged = judge_round(store, client, repo, pull, head=head, check=check, confirm=False)
        if isinstance(judged, FixRound) or judged.result is FixChecksResult.PLANNED:
            raise PhaseOutputError(
                "The state file says that the round ended, and the round has a step due"
            )
        return None
    from_state = _judged_from_state(client, state, repo, pull)
    if isinstance(from_state, FixChecksReport):
        return from_state
    return publish_round(store, client, from_state, folders, repair)


def repair_round(
    store: RoadmapStore, client: Any, facts: FixRound, repair: Repair
) -> FixChecksReport:
    """The three phases in one process, on a new run folder in `Repair.scratch` (`--phase all`):
    the round of `run_fix_checks` with `confirm`. The state of `prepare` stays in memory, so
    `publish` reads no file of the run but the outputs of the agent. The run folder, with its
    clone, goes when the round ends."""
    with tempfile.TemporaryDirectory(prefix="devops-fix-checks-", dir=repair.scratch) as root:
        folders = RunFolders(Path(root))
        _checkout, judged = prepare_round(facts, repair, folders)
        agent_phase(folders, repair)
        return publish_round(store, client, judged, folders, repair)


__all__ = [
    "AgentInput",
    "FixState",
    "FixTier",
    "agent_phase",
    "prepare_phase",
    "prepare_round",
    "publish_phase",
    "publish_round",
    "repair_round",
]
