"""The roadmap step `fix-checks`: repair a failed check on a pull request (#5023).

Enforces safety bounds:
- Bot pull requests only.
- Skip an item that a live implement Job holds: the Job owns its branch (#5983).
- Stop on an owner/* label but the Service's own `owner/service` (`claim_labels`, #5027).
- Skip when the head commit moved, also when the lease of the push finds that it moved (#5027).
- Skip a head and check whose last round ended failed, stopped or wait (#5983).
- Soft cap of 3 rounds (extendable when error count decreases).
- Hard cap of 5 rounds.
- At most 3 distinct heads per pull request with a failed check. A head whose checks pass goes to
  the ready path first, so the head that the third repair pushes can be marked ready (#5983).

The round repairs the check that `check` names, which the watch row gives the fix-checks Job, or
else the first failed check (#5027). A named check that does not fail on the head is skipped. With
`ready_only`, the watch row runs only the ready path in the Service pod: a head with a failed check
is skipped with no repair and no comment, and the next round of the row judges it (#6018).

Two tiers of repair:
- Tier 1 (deterministic, 0 model calls): ruff check --fix and format for a lint failure, devops docs
  generate for a lint, a docs or a snapshot failure, uv lock for a lockfile failure, and the snapshot
  update of each test whose snapshot differs (#6116). A docs, a lockfile or a snapshot failure
  starts tier 1 in a check of any class (#5983).
- Tier 2 (model): run_fix_step within the plan scope and the files outside the plan whose failure
  the change of the branch causes (`fix_checks_cause`, #6116). A failure that the change does not
  cause stops the round with a reason that names each file. A comment names the files of each
  pushed repair. A branch that is behind the default branch is rebased first (#6639); when only
  main causes its failure, the round pushes the rebase alone, with the result `rebased`.

The step writes only with `confirm` (#5971). Without it, the step returns `planned` with the action
that it would take, and writes nothing to GitHub, to the store or to the branch. With it, the
caller gives a `Repair`, and the round runs on the phases `prepare`, `agent` and `publish`
(`fix_checks_phases.py`, #6601): `judge_round` judges the bounds, the checks and the caps with no
agent code; the fixers run in the checkout with no GitHub call; and `publish` applies their patch
as one commit of the bot and pushes it once, with a lease on the judged head. The step does not wait for the checks after its push: a later call that finds the draft that
it repaired, or a draft that its implement Job left at the draft (#6559), with every check passing
marks the draft ready when `draft_readiness` allows it.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NamedTuple

from devops_cli.config.constants import CONST_ROADMAP_OWNER_SERVICE
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    PRCheckItem,
    read_check_runs,
)
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.claim import claim_labels
from devops_cli.roadmap.failure import FailureClass, FailureEvidence, classify_failure
from devops_cli.roadmap.fence import code_fence
from devops_cli.roadmap.fix_checks_row import OUTCOME_NONE, unit_records
from devops_cli.roadmap.implement.implement_fix_scope import repair_scope
from devops_cli.roadmap.implement.implement_pull import (
    Answer,
    DraftKind,
    failed_log,
    kind_of,
    read_draft,
)
from devops_cli.roadmap.implement.implement_step import ItemReader, find_change
from devops_cli.roadmap.phases.publish import NewTree, Published, PublishTarget
from devops_cli.roadmap.refine.refine import sanitize_text
from devops_cli.roadmap.status_sync import job_holds
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.steps.fix_checks_cause import (
    ScopeVerdict,
    checkout_reader,
    judge_scope,
    read_branch_change,
    snapshot_tests,
)
from devops_cli.roadmap.steps.ready import draft_readiness, mark_ready
from devops_cli.roadmap.stores.store import (
    FixChecksRecordKey,
    FixChecksResult,
    ImplementRecordKey,
    ImplementResult,
    Item,
    JobRecord,
    RoadmapStore,
)
from devops_cli.security.sanitizer import mask_secrets

logger = logging.getLogger(__name__)

_BOT_SUFFIX: Final[str] = "[bot]"
# The marker of the comment of the step on a pull request (ADR 0021 section 8).
MARKER: Final[str] = "<!-- devops roadmap fix-checks -->"
# The distinct heads with a failed check that the step repairs on one pull request.
_MAX_HEADS: Final[int] = 3
# The failures that tier 1 fixes in a check of any class (#5983): the report of `devops docs
# check`, and the refusal of `uv lock --check` or `uv sync --locked` (uv 0.13). `\S*` takes the
# backtick, and the color codes of a log with color, after the file name.
_DOCS_FAILURE: Final = re.compile(
    r"devops docs generate|Documentation is out of date|Missing documentation file"
)
_LOCK_FAILURE: Final = re.compile(r"uv\.lock\S*\s+needs to be updated")


@dataclass(frozen=True)
class FixChecksReport:
    """The outcome of the fix-checks step for a pull request."""

    repo: str
    pull: int
    result: FixChecksResult
    head: str = ""
    rounds: int = 0
    errors: int = 0
    reason: str = ""

    def to_json(self) -> str:
        data: dict[str, Any] = {
            "job": "fix_checks",
            "repo": self.repo,
            "pull": self.pull,
            "result": self.result.value,
        }
        if self.head:
            data["head"] = self.head
        if self.rounds:
            data["rounds"] = self.rounds
        if self.errors:
            data["errors"] = self.errors
        if self.reason:
            data["reason"] = self.reason
        return json.dumps(data)


def count_errors(log: str) -> int:
    """Count the errors reported in a failed check log."""
    if not log or not log.strip():
        return 0
    if match := re.search(r"(\d+)\s+failed", log):
        return int(match.group(1))
    if match := re.search(r"Found\s+(\d+)\s+error", log, re.IGNORECASE):
        return int(match.group(1))
    if match := re.search(r"(\d+)\s+error", log, re.IGNORECASE):
        return int(match.group(1))
    lines_with_errors = sum(
        1 for line in log.splitlines() if re.search(r"\b(ERROR|FAILED|FAIL|error:)\b", line)
    )
    return lines_with_errors if lines_with_errors > 0 else 1


@dataclass(frozen=True)
class Tier1Causes:
    """The failures in a failed check that tier 1 has a fixer for (#5983)."""

    lint: bool = False
    docs: bool = False
    lock: bool = False
    snapshots: tuple[str, ...] = ()

    @property
    def found(self) -> bool:
        return self.lint or self.docs or self.lock or bool(self.snapshots)


def tier1_causes(check: str, log: str) -> Tier1Causes:
    """The failures of check `check` that tier 1 has a fixer for: the class lint, and a docs, a
    lockfile or a snapshot failure in the log `log`, whatever the class of the check (#5983). The
    snapshots are the test files whose snapshot differs (#6116)."""
    return Tier1Causes(
        lint=classify_failure(FailureEvidence(check=check, log=log)) is FailureClass.LINT,
        docs=bool(_DOCS_FAILURE.search(log)),
        lock=bool(_LOCK_FAILURE.search(log)),
        snapshots=snapshot_tests(log),
    )


def dry_run_fix_checks(repo: str, pull: int) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Return empty request tuples for dry run (#5023)."""
    return (), ()


def is_bot_author(author: str) -> bool:
    """Check if the pull request author is a bot."""
    if not author:
        return False
    if author.endswith(_BOT_SUFFIX) or author.endswith("-bot"):
        return True
    if author == CONST_ROADMAP_OWNER_SERVICE:
        return True
    bot = load_settings().service.github_app.bot_login
    return bool(bot and author == bot)


def has_owner_label(labels: Sequence[str]) -> bool:
    """Whether `labels` hold an owner/* label that claims against the Service: `owner/agent`,
    `owner/human` or another of the family, but not `owner/service` (#5027)."""
    return bool(claim_labels(labels))


def check_scope(worktree: Path, item_num: int, log: str, is_stage_plan: bool) -> ScopeVerdict:
    """The scope verdict of the failed log for the item. A plan draft is in scope when the log
    names its change folder. An implement draft is in scope when the log names a path of the plan,
    or a file whose failure the change of the branch causes (`judge_scope`, #6116)."""
    try:
        if is_stage_plan:
            change = find_change(worktree, item_num, archived=False)
            folder = change.relative_to(worktree).as_posix()
            return ScopeVerdict(bool(re.search(rf"(?<![\w.-]){re.escape(folder)}/", log)))
        change = find_change(worktree, item_num, archived=True)
        tasks_file = change / "tasks.md"
        if not tasks_file.is_file():
            return ScopeVerdict(in_scope=False)
        groups = parse_task_groups(tasks_file.read_text(encoding="utf-8"))
    except RoadmapImplementError, OSError, ValueError:
        return ScopeVerdict(in_scope=False)
    scope = repair_scope(groups, change.relative_to(worktree).as_posix())
    return judge_scope(log, scope, lambda: read_branch_change(worktree), checkout_reader(worktree))


class Fixed(NamedTuple):
    """What a fixer did in the checkout (#5971): `done` when it made a commit and its check passes
    again, else why not. A tier 1 commit whose check still fails stays in the checkout, and the
    push of a model fix sends it too. `files` names the files of the commit of tier 1 (#6116)."""

    done: bool
    reason: str = ""
    files: tuple[str, ...] = ()


@dataclass(frozen=True)
class PullCheckout:
    """The clone on the head branch of a pull request, at the judged head (#5971, #3702): its
    path, in the work folder of the run, and `base`, the tip of the default branch that the clone
    read, or empty when the checkout reads none."""

    path: Path
    base: str = ""


# A fixer gets the worktree, the item, the name of the failed check and its log.
Fixer = Callable[[Path, int, str, str], Fixed]
# The model fix also gets the files outside the plan whose failure the change causes (#6116).
ModelFixer = Callable[[Path, int, str, str, tuple[str, ...]], Fixed]
# The push of patches as commits: the target, each patch with its message, and the claim check.
Publisher = Callable[
    [PublishTarget, Sequence[tuple[bytes, str]], Callable[[NewTree], None]], Published | None
]


@dataclass(frozen=True)
class Repair:
    """What a confirmed round of the step uses, by phase (#5971, #6601).

    - `prepare`: `checkout` clones the repository into the work folder, on the head branch of the
      pull request.
    - `agent`: `rebase` rebases a branch that is behind the default branch onto the tip that
      `prepare` read (#6639), then the deterministic fixers of tier 1, the scope check of the log,
      and `model`, which makes the model fix of tier 2 from the item that `prepare` read. A fixer
      commits in the checkout and does not push. `patch` writes the patch of the fix.
    - `publish`: `author` gives the name and the email of the bot, and `workflows` the workflow
      files that the merged plan of an item names on a branch of GitHub, each read by `publish`
      itself. `publish` applies the patch as data, writes one commit, calls the claim check and
      pushes with a lease on the judged head. `scratch` holds the run folder of `--phase all`.
    """

    checkout: Callable[[PullStatus, int, Path], PullCheckout]
    tier1: Fixer
    model: Callable[[ItemReader], ModelFixer]
    patch: Callable[[Path, str, Path], None]
    publish: Publisher
    author: Callable[[], tuple[str, str]]
    rebase: Callable[[Path, str, int], Fixed]
    scope: Callable[[Path, int, str, bool], ScopeVerdict] = check_scope
    workflows: Callable[[str, str, int], tuple[str, ...]] = lambda repo, ref, item: ()
    scratch: Path | None = None


@dataclass(frozen=True)
class FixRound:
    """The facts of one round: the pull request, its item, the failed check and its log, and the
    counts that the record holds."""

    repo: str
    pull: int
    status: PullStatus
    item_num: int
    item: Item | None
    heads: Sequence[str]
    check: str = ""
    log: str = ""
    rounds: int = 0
    errors: int = 0

    def report(
        self, result: FixChecksResult, reason: str, *, head: str = "", rounds: int | None = None
    ) -> FixChecksReport:
        return FixChecksReport(
            repo=self.repo,
            pull=self.pull,
            result=result,
            head=head or self.status.head_sha,
            rounds=self.rounds if rounds is None else rounds,
            errors=self.errors,
            reason=reason,
        )


def check_preconditions(
    status: PullStatus,
    head: str | None,
    item: Item | None,
    repo: str,
    pull: int,
) -> FixChecksReport | None:
    """Validate prerequisites before attempting any check repair."""
    if status.state != "open":
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.SKIPPED,
            head=status.head_sha,
            reason="Pull request is closed or merged",
        )
    if head is not None and status.head_sha != head:
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.SKIPPED,
            head=status.head_sha,
            reason="Head has moved",
        )
    if not is_bot_author(status.author):
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=status.head_sha,
            reason="Author is not a bot",
        )
    if item is not None and job_holds(item):
        # The implement Job owns its branch while the Job lives, as for `fix-plan` (#5983). The
        # record keeps the name of a Job that ended, with its state.
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.SKIPPED,
            head=status.head_sha,
            reason=f"A runner Job works on it: `{item.job_record.get(ImplementRecordKey.JOB)}`",
        )
    if has_owner_label(status.labels) or (item is not None and has_owner_label(item.labels)):
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=status.head_sha,
            reason="Item holds an owner label",
        )
    return None


# The results of a round that ended with no repair. The same head and check get no new round.
_ENDED: Final[frozenset[str]] = frozenset(
    {FixChecksResult.FAILED, FixChecksResult.STOPPED, FixChecksResult.WAIT}
)
# The results of a round that pushed a new head: a repair, or the rebased branch with no fix.
_PUSHED: Final[frozenset[str]] = frozenset({FixChecksResult.REPAIRED, FixChecksResult.REBASED})


def unit_ended(record: JobRecord, pull: int, head: str, check: str, extra: int) -> bool:
    """Whether the fix unit of `check` on head `head` of pull request `pull` ended with no repair
    (#6559): the last round of the step on that head and check ended (`_ENDED`), or the unit
    record holds an outcome that is no repair, or its attempts are spent (more than `extra` more
    attempts, as `fix_checks_row` counts them). No unit then repairs the check, so the watch row
    stops the item of a delivery draft."""
    if (
        record.get(FixChecksRecordKey.KEY) == f"{head}:{check}"
        and record.get(FixChecksRecordKey.RESULT) in _ENDED
    ):
        return True
    unit = unit_records(record.get(FixChecksRecordKey.UNITS)).get(f"{pull}:{head}:{check}")
    if unit is None:
        return False
    if unit.outcome == OUTCOME_NONE:
        return unit.attempt > extra
    return unit.outcome not in _PUSHED


def _check_failed_head(facts: FixRound, check: str) -> FixChecksReport | None:
    """The stop of the cap of heads, or the skip of a head and check whose last round ended with
    no repair, before the log of the check is read (#5983). A new head or another failed check
    starts a round."""
    if len(facts.heads) > _MAX_HEADS:
        return facts.report(
            FixChecksResult.STOPPED, f"Exceeded maximum of {_MAX_HEADS} heads per pull request"
        )
    record = facts.item.job_record if facts.item else {}
    ended = record.get(FixChecksRecordKey.RESULT)
    if record.get(FixChecksRecordKey.KEY) == f"{facts.status.head_sha}:{check}" and ended in _ENDED:
        return facts.report(
            FixChecksResult.SKIPPED,
            f"The last round on this head and check `{check}` ended {ended}; a new head or "
            "another failed check starts a round",
        )
    return None


def _check_caps(
    item: Item | None,
    current_rounds: int,
    errors: int,
    head_sha: str,
    repo: str,
    pull: int,
) -> FixChecksReport | None:
    """Check hard and soft caps on repair rounds."""
    if current_rounds >= 5:
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=head_sha,
            rounds=current_rounds,
            errors=errors,
            reason="Hard cap reached (5 rounds)",
        )
    soft_cap = load_settings().roadmap.implement.repair_rounds
    prev_errors_str = item.job_record.get(FixChecksRecordKey.ERRORS) if item else None
    if current_rounds >= soft_cap and not (
        prev_errors_str is not None and errors < int(prev_errors_str)
    ):
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=head_sha,
            rounds=current_rounds,
            errors=errors,
            reason=f"Soft cap reached ({soft_cap} rounds) without error reduction",
        )
    return None


def record_outcome(
    store: RoadmapStore,
    item: Item | None,
    head_sha: str,
    check_name: str,
    result: FixChecksResult,
    heads: Sequence[str],
    *,
    rounds: int | None = None,
    errors: int | None = None,
) -> None:
    """Record the step outcome in the item job record."""
    if item is None:
        return
    marks: dict[Any, str | None] = {
        FixChecksRecordKey.KEY: f"{head_sha}:{check_name}",
        FixChecksRecordKey.RESULT: result.value,
        FixChecksRecordKey.HEADS: ",".join(heads),
    }
    if rounds is not None:
        marks[FixChecksRecordKey.ROUNDS] = str(rounds)
    if errors is not None:
        marks[FixChecksRecordKey.ERRORS] = str(errors)
    store.set_marks(item, marks)


def end_round(store: RoadmapStore, facts: FixRound, result: FixChecksResult) -> None:
    """Record a round that ended with no repair."""
    record_outcome(store, facts.item, facts.status.head_sha, facts.check, result, facts.heads)


def head_moved(client: Any, facts: FixRound) -> bool:
    """Whether another writer moved the head of the pull request after the judgment: the cause of
    a push that the lease refuses (#5027)."""
    return bool(client.get_pull_status(facts.repo, facts.pull).head_sha != facts.status.head_sha)


def shown_check(check: str) -> str:
    """The name of a check as a comment shows it: on one line, masked, and with each handle, link
    and reference in a code span, so it pings no one and links nothing (#6601)."""
    return sanitize_text(mask_secrets(" ".join(check.split())), set())


def named_files(check: str, *, tier1: bool, files: Sequence[tuple[str, str]]) -> str:
    """The comment that names the files of a pushed repair (#6116): for tier 1 the files of the
    commit, and for the model the files outside the plan that the change of the branch causes,
    each with the reason. The agent phase wrote each path and reason, so the comment masks them
    and puts them in a fenced block, where no handle pings and no link opens (#6601). Empty when
    the repair names no file."""
    if not files:
        return ""
    shown = shown_check(check)
    if tier1:
        lead = (
            f"Tier 1 repaired check {shown} with the project commands and no model request. "
            "It wrote these files again:"
        )
    else:
        lead = (
            f"The model repaired check {shown}. The plan does not list these files, but the "
            "change of the branch causes their failure, so the repair could change them:"
        )
    lines = (
        mask_secrets(" ".join((f"{path}: {reason}" if reason else path).split()))
        for path, reason in files
    )
    block = "\n".join(lines)
    fence = code_fence(block)
    return "\n".join([MARKER, shown, "", lead, "", fence, block, fence])


def takes_ready_path(item: Item) -> bool:
    """Whether the ready path of the step takes the delivery draft of `item`: a fix Job repaired
    it (#5971), or its implement Job ended at the draft (`drafted`, #6559). A draft whose item
    holds a stop stays a draft: the implement Job or the watch row stopped it, and only a clear of
    the stop lets the path take it again."""
    record = item.job_record
    if record.get(ImplementRecordKey.STOPPED):
        return False
    return (
        record.get(FixChecksRecordKey.RESULT) in _PUSHED
        or record.get(ImplementRecordKey.RESULT) == ImplementResult.DRAFTED
    )


def _ready_after_repair(
    store: RoadmapStore,
    client: Any,
    facts: FixRound,
    checks: CheckVerdictSummary,
    *,
    confirm: bool,
) -> FixChecksReport:
    """A head with no failed check. A draft that the ready path takes (`takes_ready_path`), whose
    checks all pass, is marked ready when `draft_readiness` answers ready (#5971, #6559). Only an
    implement draft gets the mark here: a plan draft keeps the holds of its own ready path. Any
    other pull request is left to the watch row."""
    item = facts.item
    skipped = facts.report(FixChecksResult.SKIPPED, "No failed check on head")
    if not (
        facts.status.draft
        and checks.is_passing
        and item is not None
        and takes_ready_path(item)
        and kind_of(item, facts.pull, facts.status.title) is DraftKind.IMPLEMENT
    ):
        return skipped
    draft = read_draft(
        facts.repo, facts.pull, pull=facts.status, checks=checks, store=store, client=client
    )
    readiness = draft_readiness(draft)
    if readiness.answer is not Answer.READY:
        return facts.report(FixChecksResult.SKIPPED, f"Draft is not ready: {readiness.reason}")
    if not confirm:
        return facts.report(FixChecksResult.PLANNED, "Plan: mark the draft ready")
    mark_ready(facts.repo, facts.pull, expected_head=facts.status.head_sha, draft=draft)
    end_round(store, facts, FixChecksResult.READY)
    return facts.report(FixChecksResult.READY, "Marked the draft ready for review")


def _ready_path(
    store: RoadmapStore,
    client: Any,
    facts: FixRound,
    checks: CheckVerdictSummary,
    *,
    confirm: bool,
) -> FixChecksReport:
    """The ready path of a round: `_ready_after_repair` on a head with no failed check. A head with
    a failed check gives `skipped` with no repair and no comment: the watch row asked for the ready
    path only, and its next round judges the head (#6018)."""
    if any(item.bucket == CheckBucket.FAIL for item in checks.items) and not checks.is_passing:
        return facts.report(
            FixChecksResult.SKIPPED,
            "A check failed on the head after the read of the watch row; the next round judges it",
        )
    return _ready_after_repair(store, client, facts, checks, confirm=confirm)


def _selected(failed: Sequence[PRCheckItem], check: str | None) -> PRCheckItem | None:
    """The failed check of the round: the one that `check` names, or the first. None when `check`
    names no failed check of the head (#5027)."""
    if check is None:
        return failed[0]
    return next((item for item in failed if item.name == check), None)


def judge_round(
    store: RoadmapStore,
    client: Any,
    repo: str,
    pull: int,
    *,
    head: str | None = None,
    check: str | None = None,
    confirm: bool = False,
    ready_only: bool = False,
) -> FixChecksReport | FixRound:
    """Judge one round on pull request `pull` with no agent code: the bounds, the checks, the caps,
    the plan, the wait of a CI infrastructure failure and the ready path give the report of a round
    that ends here. A round that needs a repair gives its facts. The phase `prepare` and the round
    of `run_fix_checks` share it (#6601)."""
    status: PullStatus = client.get_pull_status(repo, pull)

    parsed = parse_branch(status.head_ref)
    item_num = parsed.issue if parsed else pull
    item = store.item(item_num)

    heads_str = (item.job_record.get(FixChecksRecordKey.HEADS) or "") if item else ""
    heads = [h for h in heads_str.split(",") if h]
    if status.head_sha not in heads:
        heads.append(status.head_sha)

    if stopped := check_preconditions(status, head, item, repo, pull):
        return stopped

    facts = FixRound(repo, pull, status, item_num, item, heads)
    owner, name = repo.split("/", 1)
    checks_summary = read_check_runs(owner, name, status.head_sha)
    failed_checks = [c for c in checks_summary.items if c.bucket == CheckBucket.FAIL]
    if checks_summary.is_passing or not failed_checks or ready_only:
        return _ready_path(store, client, facts, checks_summary, confirm=confirm)
    failed_check = _selected(failed_checks, check)
    if failed_check is None:
        return facts.report(FixChecksResult.SKIPPED, f"Check `{check}` does not fail on this head")
    if ended := _check_failed_head(facts, failed_check.name):
        return ended
    log = failed_log(repo, failed_check)
    errors = count_errors(log)
    current_rounds = int((item.job_record.get(FixChecksRecordKey.ROUNDS) or 0) if item else 0)

    if cap_stopped := _check_caps(item, current_rounds, errors, status.head_sha, repo, pull):
        return cap_stopped

    facts = FixRound(
        repo, pull, status, item_num, item, heads, failed_check.name, log, current_rounds, errors
    )
    # A docs or a lockfile failure has a fixer of tier 1, also in a check whose name the class
    # reads as infrastructure: a stale `uv.lock` fails every job (#5983).
    infra = (
        not tier1_causes(failed_check.name, log).found
        and classify_failure(FailureEvidence(check=failed_check.name, log=log))
        == FailureClass.CI_INFRA
    )
    if not confirm:
        action = (
            f"comment that check `{failed_check.name}` failed on CI infrastructure, and wait"
            if infra
            else f"repair check `{failed_check.name}` with tier 1, then the model in the plan scope"
        )
        return facts.report(FixChecksResult.PLANNED, f"Plan: {action}")

    if infra:
        comment = (
            f"CI infrastructure failure detected on check `{failed_check.name}`. "
            "Waiting for infrastructure resolution."
        )
        post(
            Target(repo, pull, client=client),
            MARKER,
            failed_check.name,
            f"{MARKER}\n{failed_check.name}\n\n{comment}",
        )
        end_round(store, facts, FixChecksResult.WAIT)
        return facts.report(FixChecksResult.WAIT, "CI infrastructure failure; waiting")
    return facts


def run_fix_checks(
    store: RoadmapStore,
    repo: str,
    pull: int,
    *,
    head: str | None = None,
    check: str | None = None,
    confirm: bool = False,
    repair: Repair | None = None,
    ready_only: bool = False,
) -> FixChecksReport:
    """Run one repair round for failed checks on pull request `pull` (#5023). Without `confirm`
    the round plans and writes nothing; with it, a repair needs `repair` (#5971), and runs the
    phases `prepare`, `agent` and `publish` in this process (`repair_round`, #6601). The round
    takes the failed check that `check` names, or the first failed check (#5027). With
    `ready_only` the round runs only the ready path, and a failed check gives `skipped` (#6018)."""
    client = get_github_session().client
    judged = judge_round(
        store, client, repo, pull, head=head, check=check, confirm=confirm, ready_only=ready_only
    )
    if isinstance(judged, FixChecksReport):
        return judged
    if repair is None:
        raise RoadmapImplementError(
            "The step fix-checks needs a repair to act: the checkout of the pull request and its "
            "fixers."
        )
    from devops_cli.roadmap.steps.fix_checks_phases import repair_round

    return repair_round(store, client, judged, repair)
