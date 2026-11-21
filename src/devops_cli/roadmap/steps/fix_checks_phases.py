"""The step `fix-checks` on the phases `prepare`, `agent` and `publish` (#3702, #6601).

The fix-checks Job is the first step on the phases (`roadmap/phases`). Each phase reads and writes
the run folder:

- `prepare` (App key, no agent code) judges the round (`judge_round`): the bounds, the claim, the
  checks, the caps and the failed log. A round that ends there writes its report to the state file.
  A round that needs a repair clones the repository into `work/` and takes over the head branch in
  a worktree (`Repair.checkout`), reads the workflow files that the merged plan names on the
  default branch, and writes the state file (`state/`) and the inputs of the agent
  (`work/input.json`). It runs git and GitHub calls
  only: no `uv`, no hook and no fixer.
- `agent` (model key only) reads its inputs, runs tier 1, the scope check and the model fix in the
  checkout, and writes the patch from the judged head, `outcome.json` and `summary.json`. It makes
  no GitHub call: the model fix reads the item from the inputs.
- `publish` (App key) reads the state file, and the outputs of the agent as data. It checks the
  claim (`check_preconditions`), applies the patch to a fresh clone, writes one commit of the bot,
  checks the claim again, and pushes with a lease on the judged head (`publish_patch`). Then it
  writes the record of the round and the comment that names the files, as the step did before.

The base and the lease are the judged head: fix-checks makes no rebase, so the agent phase needs no
network git call (#6601). `repair_round` runs the three phases in one process, which `--phase all`
and the current Job template use. #3700 runs each phase in its own container.
"""

from __future__ import annotations

import dataclasses
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_PATCH_FILE,
    CONST_ROADMAP_PHASE_PATCH_MAX_BYTES,
    CONST_ROADMAP_PHASE_STATE_FILE,
    CONST_ROADMAP_PHASE_SUMMARY_FILE,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import process_hardening
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import PhaseOutputError, PublishRefusedError
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.implement.implement_pull import DraftKind, kind_of
from devops_cli.roadmap.phases.files import (
    AgentOutcome,
    AgentSummary,
    OutcomeFile,
    OutcomeKind,
    RunFolders,
    read_outcome,
    read_output,
    write_json,
)
from devops_cli.roadmap.phases.publish import Published, PublishTarget
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.steps.fix_checks import (
    MARKER,
    FixChecksReport,
    FixRound,
    PullCheckout,
    Repair,
    check_preconditions,
    end_round,
    head_moved,
    judge_round,
    named_files,
    record_outcome,
)
from devops_cli.roadmap.stores.store import FixChecksResult, Item, RoadmapStore
from devops_cli.security.sanitizer import mask_secrets

# The most characters of a reason of the agent that the report keeps.
_REASON_CHARS = 500
# The results that an outcome of the agent phase may give.
_AGENT_RESULTS = frozenset(
    {FixChecksResult.REPAIRED, FixChecksResult.FAILED, FixChecksResult.STOPPED}
)


class FixTier(StrEnum):
    """The fixer that repaired the check: tier 1 or the model."""

    TIER1 = "tier1"
    MODEL = "model"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FixState(_Model):
    """`state/state.json`, which `prepare` writes and `publish` reads: the report of a round that
    ended in `prepare`, or the facts of the round and the target of the push."""

    repo: str
    pull: int
    item: int = 0
    report: dict[str, Any] | None = None
    status: dict[str, Any] | None = None
    heads: tuple[str, ...] = ()
    check: str = ""
    rounds: int = 0
    errors: int = 0
    target: PublishTarget | None = None


class AgentInput(_Model):
    """`work/input.json`, the inputs of the agent phase: the checkout, the judged head, the item,
    the failed check and its log, and whether the pull request is a plan."""

    checkout: str
    base: str
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
    """A reason of the agent for the report: masked, on one line, cut to `_REASON_CHARS`."""
    return mask_secrets(" ".join(text.split()))[:_REASON_CHARS]


def _report_of(data: dict[str, Any]) -> FixChecksReport:
    return FixChecksReport(**{**data, "result": FixChecksResult(data["result"])})


def _state(folders: RunFolders) -> FixState:
    return FixState.model_validate_json(
        (folders.state / CONST_ROADMAP_PHASE_STATE_FILE).read_text(encoding="utf-8")
    )


def prepare_round(facts: FixRound, repair: Repair, folders: RunFolders) -> PullCheckout:
    """The part of `prepare` after the judgment: the checkout, the workflow files of the plan, the
    state file and the inputs of the agent. Gives the checkout."""
    folders.make()
    checkout = repair.checkout(facts.status, facts.item_num, folders.work)
    is_plan = kind_of(facts.item, facts.pull, facts.status.title) == DraftKind.STAGE_PLAN
    workflows = () if is_plan else repair.workflows(checkout.path, facts.item_num)
    author, email = repair.author()
    target = PublishTarget(
        url=checkout.url,
        branch=facts.status.head_ref,
        base=facts.status.head_sha,
        lease=facts.status.head_sha,
        author=author,
        email=email,
        workflow_paths=workflows,
    )
    state = FixState(
        repo=facts.repo,
        pull=facts.pull,
        item=facts.item_num,
        status=facts.status.model_dump(mode="json"),
        heads=tuple(facts.heads),
        check=facts.check,
        rounds=facts.rounds,
        errors=facts.errors,
        target=target,
    )
    write_json(folders.state / CONST_ROADMAP_PHASE_STATE_FILE, state)
    inputs = AgentInput(
        checkout=str(checkout.path),
        base=facts.status.head_sha,
        item_num=facts.item_num,
        item=facts.item.model_dump(mode="json") if facts.item is not None else None,
        check=facts.check,
        log=facts.log,
        is_plan=is_plan,
    )
    write_json(folders.work / CONST_ROADMAP_PHASE_INPUT_FILE, inputs)
    return checkout


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
) -> None:
    """`--phase prepare`: judge the round, and write its report, or its state and the inputs of
    the agent, to the run folder."""
    judged = judge_round(store, client, repo, pull, head=head, check=check, confirm=True)
    if isinstance(judged, FixChecksReport):
        folders.make()
        report = dataclasses.asdict(judged) | {"result": judged.result.value}
        ended = FixState(repo=repo, pull=pull, report=report)
        write_json(folders.state / CONST_ROADMAP_PHASE_STATE_FILE, ended)
        return
    prepare_round(judged, repair, folders)


def _fix(path: Path, inputs: AgentInput, item: Item | None, repair: Repair) -> AgentOutcome:
    """Tier 1, then the scope check and the model fix, in the checkout `path`."""
    number = inputs.item_num
    tier1 = repair.tier1(path, number, inputs.check, inputs.log)
    if tier1.done:
        return AgentOutcome(
            kind=OutcomeKind.DONE, result=FixChecksResult.REPAIRED, detail=FixTier.TIER1
        )
    verdict = repair.scope(path, number, inputs.log, inputs.is_plan)
    if not verdict.in_scope:
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


def agent_phase(folders: RunFolders, repair: Repair) -> None:
    """`--phase agent`: the fixers in the checkout, then the patch and the outcome. A run folder
    whose `prepare` ended the round holds no inputs, and the phase writes nothing."""
    inputs_file = folders.work / CONST_ROADMAP_PHASE_INPUT_FILE
    if not inputs_file.is_file():
        return
    inputs = AgentInput.model_validate_json(inputs_file.read_text(encoding="utf-8"))
    item = Item.model_validate(inputs.item) if inputs.item is not None else None
    path = Path(inputs.checkout)
    outcome = _fix(path, inputs, item, repair)
    if load_settings().roadmap.implement.in_runner:
        process_hardening.end_leftover_processes()
    if outcome.kind is OutcomeKind.DONE:
        repair.patch(path, inputs.base, folders.out / CONST_ROADMAP_PHASE_PATCH_FILE)
    write_json(folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE, outcome)
    write_json(folders.out / CONST_ROADMAP_PHASE_SUMMARY_FILE, AgentSummary())


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
    """The message of the commit that `publish` writes, from the facts of the round only."""
    if tier is FixTier.TIER1:
        return f"style: apply the fixers of tier 1 for check {facts.check} (#{facts.item_num})"
    return f"fix: make check {facts.check} pass (#{facts.item_num})"


def _facts(state: FixState, store: RoadmapStore) -> FixRound:
    """The facts of the round that `prepare` recorded, with the item as the store holds it now."""
    if state.status is None:
        raise PhaseOutputError("The state file of the run holds no round")
    return FixRound(
        state.repo,
        state.pull,
        PullStatus.model_validate(state.status),
        state.item,
        store.item(state.item),
        list(state.heads),
        state.check,
        "",
        state.rounds,
        state.errors,
    )


def _push(
    store: RoadmapStore,
    client: Any,
    facts: FixRound,
    repair: Repair,
    pushed: tuple[PublishTarget, bytes, str],
) -> Published | FixChecksReport:
    """The publish of the patch, with the claim check right before the push: the commit, or the
    report of a round that the claim, a refusal, a move of the head or an empty patch ends."""
    target, patch, message = pushed

    def before_push() -> None:
        if report := _claim(client, store, facts):
            raise _ClaimedError(report)

    try:
        published = repair.publish(target, patch, message, before_push)
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


def publish_phase(
    store: RoadmapStore, client: Any, folders: RunFolders, repair: Repair
) -> FixChecksReport:
    """`--phase publish`: the report of a round that `prepare` ended, or the publish of the
    outcome of the agent phase, as the module text says."""
    state = _state(folders)
    if state.report is not None:
        return _report_of(state.report)
    if state.target is None:
        raise PhaseOutputError("The state file of the run holds no target")
    facts = _facts(state, store)
    if claimed := _claim(client, store, facts):
        return claimed
    outcome = read_outcome(folders)
    result, tier = _result(outcome)
    if tier is None:
        end_round(store, facts, result)
        return facts.report(result, _text(outcome.reason))
    patch = read_output(
        folders, CONST_ROADMAP_PHASE_PATCH_FILE, limit=CONST_ROADMAP_PHASE_PATCH_MAX_BYTES
    )
    published = _push(store, client, facts, repair, (state.target, patch, _message(facts, tier)))
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
    named = (
        [(path, "") for path in published.paths]
        if tier1
        else [(held.path, held.reason) for held in outcome.files]
    )
    if body := named_files(facts.check, tier1=tier1, files=named):
        post(Target(facts.repo, facts.pull, client=client), MARKER, facts.check, body)
    done = "Tier 1 resolved check with 0 model requests" if tier1 else "Tier 2 model repaired check"
    return facts.report(FixChecksResult.REPAIRED, done, head=published.commit, rounds=rounds)


def repair_round(
    store: RoadmapStore, client: Any, facts: FixRound, repair: Repair
) -> FixChecksReport:
    """The three phases in one process, on a new run folder (`--phase all`): the round of
    `run_fix_checks` with `confirm`. The worktree goes when the round ends."""
    with tempfile.TemporaryDirectory(prefix="devops-fix-checks-") as root:
        folders = RunFolders(Path(root))
        checkout = prepare_round(facts, repair, folders)
        try:
            agent_phase(folders, repair)
            return publish_phase(store, client, folders, repair)
        finally:
            repair.release(checkout)


__all__ = [
    "AgentInput",
    "FixState",
    "FixTier",
    "agent_phase",
    "prepare_phase",
    "prepare_round",
    "publish_phase",
    "repair_round",
]
