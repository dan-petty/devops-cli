"""`devops roadmap step fix-plan`: one repair of an open plan pull request that holds the label
`plan/needs-fix` (#5061).

The stage job keeps a plan in draft with `plan/needs-fix` when an open finding of its model review
remains after the repair rounds (#3264). The stage job does not select a staged item again, the
implement job leaves such a draft out, and the row `stage_ready` keeps it a draft. This step is
the later round that removes the label, and it runs the same way each time: only the plan runs of
the stage planner and of the verification pass call a model.

**Selection.** An open item with the Status Ready whose record holds `stage.pr` (a Staged item),
with no `implement.job` and no claim of an agent or a person (`claimed_by`). Its pull request is
an open draft that holds `plan/needs-fix`. The item has fewer than
`CONST_ROADMAP_FIX_PLAN_HEAD_ATTEMPTS` attempts on the head of the pull request, no attempt in the
last `CONST_ROADMAP_FIX_PLAN_WAIT_HOURS` hours, and fewer than `CONST_ROADMAP_FIX_PLAN_REVISIONS`
revisions that the step pushed to the pull request. The highest priority goes first
(`priority_order`), and a call takes at most one plan. The record rules cost no request. Each
other item costs one read of its pull request, until one qualifies. `--item` judges one item.

**Attempt.** Only with `--confirm`, or in the mode `on` of the row. No attempt starts once the
Service stops (#4925). The step fetches the default branch and the branch of the plan, and stops
before any write when the branch moved after the read, or holds a commit of another author than
the clone identity. It writes the attempt marks, reads the change folder at the head with the plan
reader, and gives it to `revise_plan` at the default branch of `origin`: the checks judge the plan,
the review counts its open findings, the planner gets the plan and those findings, and the review
judges the revision with the normal repair rounds.

**Writes.** A head plan with no open finding loses the label, and the plan stays. A revision with
fewer open findings than the head plan is one commit on the latest default branch, which the step
pushes with `--force-with-lease` on the head that it read; the pull request gets the title and the
body of the revision, and loses the label when no open finding remains. A revision that is not
better, and a failed plan run, write only the record. The step posts one comment with
`CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER` on the issue for each attempt that changes the plan or the
label, and writes only its own record keys (`FixPlanRecordKey`, ADR 0021 section 8).

**Result.** Each attempt logs one result line (`log_job_result`, job `fix_plan`) and adds 1 to
`devops_cli_roadmap_fix_plan_total` by repository and result.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
    CONST_ROADMAP_FIX_PLAN_HEAD_ATTEMPTS,
    CONST_ROADMAP_FIX_PLAN_REVISIONS,
    CONST_ROADMAP_FIX_PLAN_WAIT_HOURS,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import branch_authors, checkout_at, default_branch, git
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from devops_cli.roadmap.plan_read import (
    PlanReadError,
    change_root,
    files_at,
    read_change,
    tree_files,
)
from devops_cli.roadmap.pull_labels import remove_pull_labels
from devops_cli.roadmap.request_plan import fix_plan_requests
from devops_cli.roadmap.service_stop import raise_if_service_stops
from devops_cli.roadmap.stage.stage import (
    FalsePremise,
    PlanRevision,
    StagedChange,
    StageFailure,
    StageTarget,
    priority_order,
    revise_plan,
)
from devops_cli.roadmap.stage.stage_change import write_change_files
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_verify import (
    PLAN_NEEDS_FIX_LABEL,
    Finding,
    open_findings_section,
)
from devops_cli.roadmap.stores.store import (
    FixPlanRecordKey,
    GitHubState,
    ImplementRecordKey,
    StageRecordKey,
)
from devops_cli.roadmap.trust import trusted_replies
from devops_cli.telemetry.instruments import ROADMAP_FIX_PLAN_TOTAL, emit

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from devops_cli.ai.client import LLMClient
    from devops_cli.dry_run import PlannedRequest
    from devops_cli.github.client import PullStatus
    from devops_cli.roadmap.stage.stage_change import StageProposal
    from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
    from devops_cli.roadmap.stores.store import Item, JobRecord, RoadmapStore

logger = logging.getLogger(__name__)

_GIT_OPERATION: Final[str] = "roadmap.fix_plan"
# One line of `finding_line`: "- `<type>` at <where>: <problem>", and ' Evidence: "<quote>"' after it
# when the finding has a quote.
_FINDING_LINE: Final[re.Pattern[str]] = re.compile(
    r'- `(?P<type>[a-z_]+)` at (?P<where>.+?): (?P<problem>.+?)(?: Evidence: "(?P<quote>.*)")?'
)
# The comments that list the open findings of a plan: the stage comment and this step's comment.
_PLAN_MARKERS: Final[tuple[str, ...]] = (
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
)
# The characters of a commit that a comment or a reason shows.
_SHORT: Final[int] = 12


class FixPlanResult(StrEnum):
    """How an attempt ended: `revised` pushed a revision that still has an open finding, `cleared`
    left no open finding (the label goes), `unchanged` made no better plan, and `failed` stopped in
    the plan run or in the read of the plan."""

    REVISED = "revised"
    CLEARED = "cleared"
    UNCHANGED = "unchanged"
    FAILED = "failed"


@dataclass(frozen=True)
class FixPlanTarget:
    """The plan pull request that the step selected: the item, the number of the pull request and
    the read of it."""

    item: Item
    pull: int
    status: PullStatus


@dataclass(frozen=True)
class FixPlanLeftOut:
    """A Staged item that the step did not take, and why."""

    number: int
    reason: str


@dataclass(frozen=True)
class FixPlanAttempt:
    """One attempt: the item, the pull request, the result, the open findings of the review before
    and after the repair, the head of the branch after the attempt, and the class of a failure."""

    number: int
    pull: int
    result: FixPlanResult
    before: int = 0
    after: int = 0
    head: str = ""
    failure: FailureClass | None = None


@dataclass(frozen=True)
class FixPlanRun:
    """What a call did: the selected plan pull request, the Staged items it left out, the attempt,
    and for a dry run the requests and the writes of a run."""

    repo: str
    target: FixPlanTarget | None = None
    left_out: tuple[FixPlanLeftOut, ...] = ()
    attempt: FixPlanAttempt | None = None
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()


def _count(text: str | None) -> int:
    return int(text) if text is not None and text.isdigit() else 0


def _time(text: str | None) -> datetime | None:
    """The time that `text` holds, in UTC when it names no zone, or None for no time."""
    try:
        found = datetime.fromisoformat(text) if text else None
    except ValueError:
        return None
    return found.replace(tzinfo=UTC) if found is not None and found.tzinfo is None else found


def _finding_of(line: str) -> Finding | None:
    """The finding that one line of `finding_line` holds, or None for a line of another form or a
    type that the review does not name."""
    found = _FINDING_LINE.fullmatch(line)
    if found is None:
        return None
    try:
        return Finding(
            type=DefectType(found["type"]),
            where=found["where"],
            problem=found["problem"],
            quote=found["quote"] or "",
        )
    except ValueError:
        return None


def comment_open_findings(body: str) -> tuple[Finding, ...]:
    """The open findings that the comment `body` lists first, in the section that
    `open_findings_section` writes (#3264): the stage comment, or the comment of an attempt of
    this step that kept the label. A comment with no such section gives none. A line of the section
    that does not read as a finding is left out and logged, with no text of the comment."""
    heading = MESSAGES.roadmap.stage_comment_open_findings.split("{findings}")[0].strip()
    _, found, rest = body.partition(heading)
    if not found:
        return ()
    lines = []
    for line in rest.lstrip("\n").splitlines():
        if not line.startswith("- "):
            break
        lines.append(line)
    findings = tuple(f for f in map(_finding_of, lines) if f is not None)
    if len(findings) < len(lines):
        logger.warning(
            "fix-plan read %d of the %d lines of the open findings of a comment",
            len(findings),
            len(lines),
        )
    return findings


def plan_comment(store: RoadmapStore, number: int, pull: int) -> str:
    """The newest comment on issue `number` of the stage job or of this step that names plan pull
    request `pull`, or an empty text when none does. Only a comment of a trusted author counts
    (`trusted_replies`): the step gives its findings to the planner."""
    names = re.compile(rf"#{pull}\b")
    for comment in reversed(trusted_replies(store.comments_on(number))):
        if any(marker in comment.body for marker in _PLAN_MARKERS) and names.search(comment.body):
            return comment.body
    return ""


@dataclass(frozen=True)
class _Marks:
    """The fix-plan marks of a record: the pull request and the head of `fix_plan.key`, the
    attempts on that head, the revisions on that pull request, and the time of the last attempt."""

    pull: str = ""
    head: str = ""
    attempts: int = 0
    revisions: int = 0
    at: datetime | None = None

    @classmethod
    def of(cls, record: JobRecord) -> _Marks:
        pull, _, head = (record.get(FixPlanRecordKey.KEY) or "").partition(":")
        return cls(
            pull,
            head,
            _count(record.get(FixPlanRecordKey.ATTEMPTS)),
            _count(record.get(FixPlanRecordKey.REVISIONS)),
            _time(record.get(FixPlanRecordKey.AT)),
        )

    def attempts_on(self, pull: int, head: str) -> int:
        return self.attempts if (self.pull, self.head) == (str(pull), head) else 0

    def revisions_on(self, pull: int) -> int:
        return self.revisions if self.pull == str(pull) else 0


def _staged_pull(item: Item) -> int | None:
    """The plan pull request that the record of the open `item` holds, or None."""
    recorded = item.job_record.get(StageRecordKey.PR) or ""
    if item.state is not GitHubState.OPEN or not recorded.isdigit():
        return None
    return int(recorded)


def _record_reason(item: Item, pull: int | None, now: datetime) -> str | None:
    """Why the record of `item` leaves it out, before any read, or None."""
    texts = MESSAGES.roadmap
    marks = _Marks.of(item.job_record)
    wait = timedelta(hours=CONST_ROADMAP_FIX_PLAN_WAIT_HOURS)
    if pull is None or item.status != CONST_ROADMAP_STATUS_READY:
        return texts.fix_plan_left_not_staged
    if item.job_record.get(ImplementRecordKey.JOB):
        return texts.fix_plan_left_runner
    if (owner := claimed_by(item)) is not None:
        return texts.item_left_claimed.format(owner=owner)
    if marks.at is not None and now - marks.at < wait:
        return texts.fix_plan_left_recent.format(
            at=marks.at.isoformat(), hours=CONST_ROADMAP_FIX_PLAN_WAIT_HOURS
        )
    if (count := marks.revisions_on(pull)) >= CONST_ROADMAP_FIX_PLAN_REVISIONS:
        return texts.fix_plan_left_revisions.format(count=count, pull=pull)
    return None


def _pull_reason(item: Item, pull: int, status: PullStatus) -> str | None:
    """Why the read of plan pull request `pull` leaves `item` out, or None."""
    texts = MESSAGES.roadmap
    count = _Marks.of(item.job_record).attempts_on(pull, status.head_sha)
    if not status.is_open_draft:
        return texts.fix_plan_left_not_draft.format(pull=pull)
    if PLAN_NEEDS_FIX_LABEL not in status.labels:
        return texts.fix_plan_left_no_label.format(pull=pull)
    if count >= CONST_ROADMAP_FIX_PLAN_HEAD_ATTEMPTS:
        head = status.head_sha[:_SHORT]
        return texts.fix_plan_left_attempts.format(head=head, pull=pull, count=count)
    return None


def _candidates(
    store: RoadmapStore, item: int | None, pull: int | None = None
) -> tuple[list[Item], list[FixPlanLeftOut]]:
    """The items to judge, highest priority first: the one that `item` names, the one whose record
    holds plan pull request `pull`, or each open item whose record holds a plan pull request."""
    if item is None:
        found = [
            each
            for each in store.items()
            if (recorded := _staged_pull(each)) is not None and pull in (None, recorded)
        ]
        if pull is not None and not found:
            return [], [
                FixPlanLeftOut(pull, MESSAGES.roadmap.fix_plan_left_no_item.format(pull=pull))
            ]
        return sorted(found, key=priority_order), []
    named = store.item(item)
    if named is None:
        return [], [FixPlanLeftOut(item, MESSAGES.roadmap.item_left_not_item)]
    return [named], []


def select_fix_plan(
    store: RoadmapStore,
    *,
    repo: str,
    item: int | None = None,
    pull: int | None = None,
    now: datetime | None = None,
) -> tuple[FixPlanTarget | None, tuple[FixPlanLeftOut, ...]]:
    """The plan pull request that the step takes, and the Staged items it left out before it, as
    the module says. `item` or `pull` names the one item to judge. It reads a pull request only for
    an item that the record rules keep."""
    now = now or datetime.now(UTC)
    candidates, left = _candidates(store, item, pull)
    for each in candidates:
        pull = _staged_pull(each)
        reason = _record_reason(each, pull, now)
        if reason is None and pull is not None:
            status = get_github_session().client.get_pull_status(repo, pull)
            reason = _pull_reason(each, pull, status)
            if reason is None:
                return FixPlanTarget(each, pull, status), tuple(left)
        left.append(FixPlanLeftOut(each.number, reason or ""))
    return None, tuple(left)


def _git(cwd: Path, *args: str) -> str:
    return git(cwd, *args, operation=_GIT_OPERATION)


def _branch_reason(source: Path, target: FixPlanTarget) -> str | None:
    """Why the branch of the plan stops the attempt before any write, or None: it does not name the
    item, it moved after the read, or it holds a commit of another author than the clone."""
    texts = MESSAGES.roadmap
    status, pull = target.status, target.pull
    parts = parse_branch(status.head_ref)
    if parts is None or parts.issue != target.item.number:
        return texts.fix_plan_left_branch.format(branch=status.head_ref, pull=pull)
    tip = _git(source, "rev-parse", f"origin/{status.head_ref}")
    if tip != status.head_sha:
        head = status.head_sha[:_SHORT]
        return texts.fix_plan_left_moved.format(pull=pull, tip=tip[:_SHORT], head=head)
    own = _git(source, "config", "user.name")
    others = [
        a for a in branch_authors(source, status.head_ref, operation=_GIT_OPERATION) if a != own
    ]
    if others:
        return texts.fix_plan_left_person.format(pull=pull, count=len(others))
    return None


def _head_plan(source: Path, target: FixPlanTarget) -> tuple[StageTarget, StageProposal]:
    """The stage target and the plan of the head of the pull request. The type comes from the
    branch and the slug from the change folder, so the folder keeps its name. The summary comes
    from the title of the pull request, which the folder does not hold."""
    item, status = target.item, target.status
    head = status.head_sha
    paths = tree_files(source, head, operation=_GIT_OPERATION)
    root, reasons = change_root(paths, item.number)
    if root is None:
        raise PlanReadError(CONST_OPENSPEC_CHANGES_DIR, " ".join(reasons))
    files = files_at(
        source,
        head,
        [path for path in paths if path.startswith(f"{root}/")],
        operation=_GIT_OPERATION,
    )
    proposal = read_change(files)
    lead = MESSAGES.roadmap.stage_title_lead.format(number=item.number)
    summary = status.title.partition(lead)[2].strip()
    if summary:
        proposal = proposal.model_copy(update={"summary": summary})
    parts = parse_branch(status.head_ref)
    type_ = parts.type if parts is not None else ""
    slug = root.rsplit("/", 1)[-1].removeprefix(f"{item.number}-")
    return StageTarget(item, type_, slug), proposal


def _push(source: Path, target: FixPlanTarget, base: str, change: StagedChange) -> str:
    """Write the change folder of `change` as one commit on the latest default branch `base`, and
    push it to the branch of the plan with a lease on the head that the step read; the new head.
    The step fetches `base` again just before the push and rebases the commit onto it (#4879)."""
    branch, head = target.status.head_ref, target.status.head_sha
    body = MESSAGES.roadmap.fix_plan_commit_body.format(number=target.item.number)
    with checkout_at(source, f"origin/{base}", operation=_GIT_OPERATION) as tree:
        write_change_files(tree, change.files)
        _git(tree, "add", "--", f"{CONST_OPENSPEC_CHANGES_DIR}/{change.target.change}")
        _git(tree, "commit", "-q", "-m", change.title, "-m", body)
        _git(tree, "fetch", "-q", "origin", base)
        _git(tree, "rebase", "-q", f"origin/{base}")
        pushed = _git(tree, "rev-parse", "HEAD")
        lease = f"--force-with-lease=refs/heads/{branch}:{head}"
        _git(tree, "push", "-q", lease, "origin", f"HEAD:refs/heads/{branch}")
    return pushed


def _comment(
    target: FixPlanTarget, result: FixPlanResult, revision: PlanRevision, head: str
) -> str:
    """The comment of an attempt that changed the plan or the label."""
    texts = MESSAGES.roadmap
    change = revision.outcome
    after = change.open_findings if isinstance(change, StagedChange) else ()
    values = {
        "marker": CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
        "pull": target.pull,
        "head": head[:_SHORT],
        "before": len(revision.before),
        "after": len(after),
    }
    if result is FixPlanResult.REVISED:
        return texts.fix_plan_comment_revised.format(
            **values, findings=open_findings_section(after)
        )
    if head == target.status.head_sha:
        return texts.fix_plan_comment_clean.format(**values)
    return texts.fix_plan_comment_cleared.format(**values)


def _failure(outcome: object) -> FailureClass:
    """The class of an outcome that is no revision."""
    if isinstance(outcome, StageFailure):
        return outcome.failure_class
    if isinstance(outcome, FalsePremise):
        return FailureClass.PREMISE_FALSE
    return FailureClass.PLAN_DEFECT


@dataclass(frozen=True)
class _Attempt:
    """The parts of one attempt that its writes need."""

    store: RoadmapStore
    repo: str
    source: Path
    target: FixPlanTarget
    base: str


def _settle(attempt: _Attempt, revision: PlanRevision) -> FixPlanAttempt:
    """Write what `revision` makes of the plan, as the module says, and the attempt it was."""
    target = attempt.target
    outcome, before = revision.outcome, len(revision.before)
    number, pull, head = target.item.number, target.pull, target.status.head_sha
    if not isinstance(outcome, StagedChange):
        failure = _failure(outcome)
        return FixPlanAttempt(
            number, pull, FixPlanResult.FAILED, before, head=head, failure=failure
        )
    after = len(outcome.open_findings)
    if before and after >= before:
        return FixPlanAttempt(number, pull, FixPlanResult.UNCHANGED, before, after, head)
    if before:
        head = _push(attempt.source, target, attempt.base, outcome)
        if (outcome.title, outcome.body) != (target.status.title, target.status.body):
            client = get_github_session().client
            client.update_pull(attempt.repo, pull, title=outcome.title, body=outcome.body)
    result = FixPlanResult.REVISED if after else FixPlanResult.CLEARED
    if not after:
        remove_pull_labels(attempt.store, pull, (PLAN_NEEDS_FIX_LABEL,))
    attempt.store.comment(number, _comment(target, result, revision, head))
    return FixPlanAttempt(number, pull, result, before, after, head)


def _result_marks(target: FixPlanTarget, done: FixPlanAttempt) -> Mapping[FixPlanRecordKey, str]:
    """The marks that end an attempt: its result, and after a push the new head with no attempt
    and one more revision."""
    marks = {FixPlanRecordKey.RESULT: done.result.value}
    if done.head == target.status.head_sha:
        return marks
    revisions = _Marks.of(target.item.job_record).revisions_on(target.pull) + 1
    return marks | {
        FixPlanRecordKey.KEY: f"{target.pull}:{done.head}",
        FixPlanRecordKey.ATTEMPTS: "0",
        FixPlanRecordKey.REVISIONS: str(revisions),
    }


def _report(repo: str, done: FixPlanAttempt, counts: Mapping[str, int]) -> None:
    """Log the line and the result line of `done`, and count its result."""
    logger.info(
        MESSAGES.roadmap.fix_plan_attempt.format(
            pull=done.pull,
            number=done.number,
            result=done.result.value,
            before=done.before,
            after=done.after,
        )
    )
    log_job_result(
        RoadmapJob.FIX_PLAN,
        repo,
        done.number,
        done.result.value,
        failure=done.failure,
        counts={**counts, "before": done.before, "after": done.after},
    )
    emit(ROADMAP_FIX_PLAN_TOTAL, 1, {"repo": repo, "result": done.result.value})


def _attempt(
    attempt: _Attempt,
    now: datetime,
    *,
    model: LLMClient | ToolboxModel | None,
    verifier: ToolboxModel,
) -> FixPlanAttempt | FixPlanLeftOut:
    """One attempt on the selected plan, or why the branch stops it before any write."""
    store, source, target = attempt.store, attempt.source, attempt.target
    number, status = target.item.number, target.status
    raise_if_service_stops(f"the fix-plan of #{number}")
    _git(source, "fetch", "-q", "origin", attempt.base, status.head_ref)
    if (reason := _branch_reason(source, target)) is not None:
        return FixPlanLeftOut(number, reason)
    marks = _Marks.of(target.item.job_record)
    revisions = marks.revisions_on(target.pull)
    store.set_marks(
        target.item,
        {
            FixPlanRecordKey.KEY: f"{target.pull}:{status.head_sha}",
            FixPlanRecordKey.ATTEMPTS: str(marks.attempts_on(target.pull, status.head_sha) + 1),
            FixPlanRecordKey.REVISIONS: str(revisions) if revisions else None,
            FixPlanRecordKey.AT: now.isoformat(),
            FixPlanRecordKey.RESULT: None,
        },
    )
    try:
        stage_target, proposal = _head_plan(source, target)
    except PlanReadError:
        done = FixPlanAttempt(
            number,
            target.pull,
            FixPlanResult.FAILED,
            head=status.head_sha,
            failure=FailureClass.PLAN_DEFECT,
        )
        counts: Mapping[str, int] = {}
    else:
        sha = _git(source, "rev-parse", f"origin/{attempt.base}")
        findings = comment_open_findings(plan_comment(store, number, target.pull))
        revision = revise_plan(
            stage_target,
            proposal,
            repo=attempt.repo,
            checkout=source,
            sha=sha,
            verifier=verifier,
            model=model,
            findings=findings,
        )
        done = _settle(attempt, revision)
        counts = revision.attempt.counts() if revision.attempt is not None else {}
    store.set_marks(store.item(number) or target.item, _result_marks(target, done))
    _report(attempt.repo, done, counts)
    return done


def run_fix_plan(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    confirm: bool,
    item: int | None = None,
    pull: int | None = None,
    now: datetime | None = None,
    model: LLMClient | ToolboxModel | None = None,
    verifier: ToolboxModel | None = None,
) -> FixPlanRun:
    """Select one plan pull request of `repo` and, with `confirm`, run one attempt on it in the
    clone `source`, as the module says. Without `confirm` the call makes no model call and no
    write. `model` and `verifier` are those of `plan_stage`; with no `verifier`, the model of the
    task `verification` reviews. A failed read or write of GitHub or git raises after the attempt
    marks."""
    now = now or datetime.now(UTC)
    target, left = select_fix_plan(store, repo=repo, item=item, pull=pull, now=now)
    run = FixPlanRun(repo, target, left)
    if target is None:
        logger.info(MESSAGES.roadmap.fix_plan_none.format(repo=repo))
        return run
    logger.info(
        MESSAGES.roadmap.fix_plan_selected.format(
            repo=repo,
            pull=target.pull,
            number=target.item.number,
            head=target.status.head_sha[:_SHORT],
        )
    )
    if not confirm:
        return run
    if verifier is None:
        from devops_cli.ai.client.factory import get_task_model
        from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel

        verifier = ToolboxModel(get_task_model("verification"))
    base = target.status.base_ref or default_branch(source, operation=_GIT_OPERATION)
    done = _attempt(
        _Attempt(store, repo, source, target, base), now, model=model, verifier=verifier
    )
    if isinstance(done, FixPlanLeftOut):
        return FixPlanRun(repo, target, (*left, done))
    return FixPlanRun(repo, target, left, done)


def dry_run_fix_plan(repo: str, *, item: int | None = None) -> FixPlanRun:
    """The run a dry run returns, having made no request: the requests and the git commands that
    a run makes, in order, and the writes that `--confirm` adds."""
    reads, writes = fix_plan_requests(repo, item=item)
    return FixPlanRun(repo, dry_run=True, requests=reads, write_requests=writes)


def render_fix_plan(run: FixPlanRun) -> str:
    """The report of a call: the selection, the items left out, and the attempt."""
    texts = MESSAGES.roadmap
    target = run.target
    lines = [
        texts.fix_plan_none.format(repo=run.repo)
        if target is None
        else texts.fix_plan_selected.format(
            repo=run.repo,
            pull=target.pull,
            number=target.item.number,
            head=target.status.head_sha[:_SHORT],
        )
    ]
    lines += [
        texts.fix_plan_left.format(number=left.number, reason=left.reason) for left in run.left_out
    ]
    done = run.attempt
    if done is not None:
        lines.append(
            texts.fix_plan_attempt.format(
                pull=done.pull,
                number=done.number,
                result=done.result.value,
                before=done.before,
                after=done.after,
            )
        )
    return "\n".join(lines)


__all__ = [
    "FixPlanAttempt",
    "FixPlanLeftOut",
    "FixPlanResult",
    "FixPlanRun",
    "FixPlanTarget",
    "comment_open_findings",
    "dry_run_fix_plan",
    "plan_comment",
    "render_fix_plan",
    "run_fix_plan",
    "select_fix_plan",
]
