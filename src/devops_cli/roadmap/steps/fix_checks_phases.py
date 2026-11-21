"""The step `fix-checks` on the phases `prepare`, `agent` and `publish` (#3702, #6601).

The fix-checks Job is the first step on the phases (`roadmap/phases`). Each phase reads and writes
the run folder:

- `prepare` (App key, no agent code) judges the round (`judge_round`): the bounds, the claim, the
  checks, the caps and the failed log. A round that ends there gives its report for the Job, and
  writes a state file that says so.
  A round that needs a repair clones the repository into `work/` and takes over the head branch in
  a worktree (`Repair.checkout`), and writes the state file (`state/`) and the inputs of the agent
  (`work/input.json`). It runs git and GitHub calls only: no `uv`, no hook and no fixer.
- `agent` (model key only) reads its inputs, runs tier 1, the scope check and the model fix in the
  checkout, and writes the patch from the judged head, `outcome.json` and `summary.json`. It makes
  no GitHub call: the model fix reads the item from the inputs.
- `publish` (App key) reads the outputs of the agent as data (`read_run_file`). It checks the
  judged round against the pull request as GitHub holds it: the head branch, the item and the
  judged head. It builds the target of the push from GitHub alone: the head branch and the
  judged head of the pull request, the bot of the App, the workflow files that the merged plan of
  the item names on the default branch (`Repair.workflows`), and the URL of `origin` that
  `prepare` read before any agent code ran. A separate `publish` reads the state file as data, takes
  its URL only when it is the URL of the repository on GitHub, and takes the failed check and its
  count of errors from GitHub. It checks the claim (`check_preconditions`), applies the
  patch to a fresh clone, writes one commit of the bot, checks the claim again, and pushes with a
  lease on the judged head (`publish_patch`). Then it writes the record of the round and the
  comment that names the files, as the step did before.

The base and the lease are the judged head: fix-checks makes no rebase, so the agent phase needs no
network git call (#6601). `repair_round` runs the three phases in one process, which `--phase all`
and the current Job template use: the state of `prepare` stays in memory, so `publish` reads no
file of the run but the outputs of the agent. #3700 runs each phase in its own container.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.config.constants import (
    CONST_GITHUB_CLONE_URL,
    CONST_ROADMAP_PHASE_INPUT_FILE,
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_PATCH_FILE,
    CONST_ROADMAP_PHASE_PATCH_MAX_BYTES,
    CONST_ROADMAP_PHASE_STATE_FILE,
    CONST_ROADMAP_PHASE_SUMMARY_FILE,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import process_hardening
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import (
    PhaseOutputError,
    PublishRefusedError,
    RoadmapImplementError,
)
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.check_verdict import CheckBucket, read_check_runs
from devops_cli.github.client import PullStatus
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
from devops_cli.roadmap.phases.publish import Published, PublishTarget
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
    """`state/state.json`, which `prepare` writes and a separate `publish` reads: that the round
    ended in `prepare`, or the facts of the round that `prepare` judged. `publish` builds the
    target of the push from the pull request as GitHub holds it then, and checks these facts
    against it: the state names no branch, author or workflow file that `publish` pushes, and
    `publish` takes its URL only when it is the URL of the repository on GitHub."""

    repo: str
    pull: int
    item: int = 0
    ended: bool = False
    status: dict[str, Any] | None = None
    check: str = ""
    url: str = ""


@dataclass(frozen=True)
class JudgedRound:
    """What `publish` takes from `prepare`: the pull request, the item, the judged status, the
    failed check, the count of errors of its log, and the URL of `origin` that `prepare` read
    before any agent code ran. `--phase all` keeps it in memory; a separate `publish` builds it
    from the state file and checks each part against GitHub (`_judged_from_state`)."""

    repo: str
    pull: int
    item: int
    status: PullStatus
    check: str
    errors: int
    url: str


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
    the agent. Gives the checkout and the judged round, which `--phase all` keeps in memory. A
    clone whose `origin` is not the repository on GitHub gets no round, so no run pushes to
    another URL."""
    folders.make()
    checkout = repair.checkout(facts.status, facts.item_num, folders.work)
    if checkout.url != CONST_GITHUB_CLONE_URL.format(repo=facts.repo):
        repair.release(checkout)
        raise RoadmapImplementError(
            f"The origin of the clone is not the repository {facts.repo} on GitHub, so the "
            "round pushes nothing"
        )
    is_plan = _is_plan(facts.item, facts.pull, facts.status)
    state = FixState(
        repo=facts.repo,
        pull=facts.pull,
        item=facts.item_num,
        status=facts.status.model_dump(mode="json"),
        check=facts.check,
        url=checkout.url,
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
    return checkout, JudgedRound(
        facts.repo,
        facts.pull,
        facts.item_num,
        facts.status,
        facts.check,
        facts.errors,
        checkout.url,
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


def _target(repair: Repair, facts: FixRound, url: str) -> PublishTarget:
    """The target of the push, from the pull request as GitHub holds it now and from what
    `publish` reads itself: the URL of `origin`, the bot, and the workflow files that the merged
    plan of the item names on the default branch. A plan draft writes no workflow file."""
    status = facts.status
    author, email = repair.author()
    workflows = (
        ()
        if _is_plan(facts.item, facts.pull, status)
        else repair.workflows(facts.repo, status.default_branch or status.base_ref, facts.item_num)
    )
    return PublishTarget(
        url=url,
        branch=status.head_ref,
        base=status.head_sha,
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
    pushed: tuple[bytes, str, str],
) -> Published | FixChecksReport:
    """The publish of the patch, with the claim check right before the push: the commit, or the
    report of a round that the claim, a refusal, a move of the head or an empty patch ends."""
    patch, message, url = pushed

    def before_push() -> None:
        if report := _claim(client, store, facts):
            raise _ClaimedError(report)

    try:
        published = repair.publish(_target(repair, facts, url), patch, message, before_push)
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
    if tier is None:
        end_round(store, facts, result)
        return facts.report(result, _text(outcome.reason))
    patch = read_output(
        folders, CONST_ROADMAP_PHASE_PATCH_FILE, limit=CONST_ROADMAP_PHASE_PATCH_MAX_BYTES
    )
    published = _push(store, client, facts, repair, (patch, _message(facts, tier), judged.url))
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
    can say taken from GitHub: the URL must be the URL of the repository on GitHub; the check must
    be a failed check of the judged head, by the name that GitHub gives; and the count of errors
    comes from the log of that check, which `publish` reads itself."""
    if (state.repo, state.pull) != (repo, pull) or state.status is None:
        raise PhaseOutputError("The state file of the run names another pull request")
    if state.url != CONST_GITHUB_CLONE_URL.format(repo=repo):
        raise PhaseOutputError("The state file of the run names another origin")
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
    return JudgedRound(repo, pull, state.item, judged, failed[0].name, errors, state.url)


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
    `publish` reads no file of the run but the outputs of the agent. The worktree goes when the
    round ends."""
    with tempfile.TemporaryDirectory(prefix="devops-fix-checks-", dir=repair.scratch) as root:
        folders = RunFolders(Path(root))
        checkout, judged = prepare_round(facts, repair, folders)
        try:
            agent_phase(folders, repair)
            return publish_round(store, client, judged, folders, repair)
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
    "publish_round",
    "repair_round",
]
