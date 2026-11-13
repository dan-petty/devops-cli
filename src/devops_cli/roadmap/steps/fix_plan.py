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
A run with `skip_wait` (`--skip-wait`, which the command allows only for a named item and with
`--confirm`) leaves out the wait and keeps the other rules (#5413). It also takes a head over the
attempt cap when `fix_plan.version` gives an older release than the current one, or no release,
for its counted attempts, and logs why: a release can fix the cause of those attempts. The Service
never passes `skip_wait`.

**Attempt.** Only with `--confirm`, or in the mode `on` of the row. No attempt starts once the
Service stops (#4925). The step fetches the default branch and the branch of the plan, and stops
before any write when the branch moved after the read, or holds a commit of another author than
the clone identity. It reads the change folder at the head with the plan reader before the attempt
marks (#5213). A plan that the reader refuses is `unreadable`: the step writes only `fix_plan.at`
and `fix_plan.result`, logs one warning with the file and the masked reason, and writes no result
line, because the defect is in the writer or the reader of the plan and not in this step. Else the
step writes the attempt marks, with the release in `fix_plan.version`, and gives the plan to
`revise_plan` at the default branch of `origin`: the checks judge the plan, and a plan that they
refuse gets a new plan from the planner (the gated plan). The trace gate judges only a
Feasibility sentence that a reply of the planner adds or changes, because the gate of the run that
wrote the head passed each sentence of it (#5391). The review of the plan that passed the checks
counts its open findings (`before`), the planner gets the plan with those findings and the open
findings of the last plan comment, and the review judges the revision with the normal repair
rounds (`after`). The first review of the revision is a later review: it says for each open
finding of the head whether it still holds, and opens a new finding only in the text that the
revision changed (#5409). An earlier review wrote the comment, so the count of the comment
(`comment`) is only reported (#5150).

**Results**, in this order:

- `timeout`: the time budget of the step ended before a plan run or a review (#5363). The step
  pushes nothing, also a gated plan or a revision that exists, and the label stays. The comment
  lists the open findings that keep the label and the counts of the attempt.
- `stopped`: a false premise, an open blocker or a head over the budget stops the attempt before a
  gated plan exists. The label stays, and the comment holds the evidence. A person decides.
- `failed`: a model call or the checks fail before a gated plan exists, or a step after the checks
  fails and the gated plan is the plan of the head. The label stays.
- `revised` or `cleared`: the revision of a repair is not the same plan as the gated plan
  (`same_plan`), and its reviews fixed more open findings of the head than they added
  (`PlanRevision.fixed` and `PlanRevision.added`, #5409). The step pushes the revision, and the
  label goes for `cleared`, when no open finding remains.
- `regated`: else, the gated plan is not the same plan as the head. The step pushes the gated plan,
  and the label goes only after a review of it with no open finding and no failed step.
- `dismissed`: else, the review of the head found no open finding. The label goes, and the comment
  dismisses the open findings of the last plan comment.
- `unchanged`: else. The label stays.

**Kills.** SIGTERM (`sigterm_raises` of the command) or a stop of the Service can end an attempt
after its marks (`attempt_kill`). A kill of the class `deadline`, SIGTERM after the time budget is
spent, counts: the record gets the result `timeout`, and the result line holds the class `timeout`
and `kill=deadline`. A kill of the class `evicted` does not count while the head has fewer than
`_HEAD_EVICTIONS` evicted attempts: the record keeps the count, the time and the release of the
attempt before it, adds 1 to `fix_plan.evicted` and gets the result `evicted`. A later evicted
attempt counts. An evicted attempt writes no result line, as an attempt that the stop of the
Service ends wrote none before. A killed attempt posts no comment and pushes nothing, and the kill
goes on with its class.

**Writes.** A push is one commit on the latest default branch, which the step pushes with
`--force-with-lease` on the head that it read; the pull request gets the title and the body of the
plan. The step posts one comment with `CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER` on the issue for
each attempt that ends `revised`, `cleared`, `regated`, `dismissed`, `stopped` or `timeout`, and
writes only its own record keys (`FixPlanRecordKey`, ADR 0021 section 8).

**Budget.** The setting `roadmap.fix_plan.time_budget_seconds` starts with the call (#5363). The
planner compares the time with it before each plan run and each review run, and starts no run once
it is spent: a Job that runs the step then writes its result line and its comment before the
deadline of the Job stops the pod. Each review logs one progress line with its number, its open
findings, the tokens and the seconds so far, and the budget.

**Result.** Each attempt with a read plan logs one line and one result line (`log_job_result`, job
`fix_plan`) with the counts of the plan runs and `comment`, `before` only when the review of the
head ran, and `after` only when a review of a revision ran: a count that the attempt did not
measure is left out, never written as 0. A stop names its kind (`stop`), and a failure its step
(`step`) and its class, `timeout` for a spent budget. Each attempt adds 1 to
`devops_cli_roadmap_fix_plan_total` by repository and result.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import cache
from typing import TYPE_CHECKING, Final

from packaging.version import InvalidVersion, Version

from devops_cli import __version__
from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
    CONST_ROADMAP_FIX_PLAN_HEAD_ATTEMPTS,
    CONST_ROADMAP_FIX_PLAN_REVISIONS,
    CONST_ROADMAP_FIX_PLAN_WAIT_HOURS,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import ServiceStoppingError
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.agent_run import bounded_text
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled, kill_of
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import branch_authors, checkout_at, default_branch, git
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from devops_cli.roadmap.plan_read import (
    PlanReadError,
    change_root,
    files_at,
    read_change,
    tree_files,
)
from devops_cli.roadmap.planned import open_plan_creates, planned_changes_at
from devops_cli.roadmap.pull_labels import remove_pull_labels
from devops_cli.roadmap.request_plan import fix_plan_requests
from devops_cli.roadmap.service_stop import raise_if_service_stops
from devops_cli.roadmap.stage.stage import (
    Blocked,
    FalsePremise,
    OverBudget,
    PlanRevision,
    StagedChange,
    StageFailure,
    StageTarget,
    priority_order,
    revise_plan,
    same_plan,
)
from devops_cli.roadmap.stage.stage_change import safe_text, write_change_files
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_verify import (
    PLAN_NEEDS_FIX_LABEL,
    Finding,
    Locator,
    PlanPart,
    finding_line,
    open_findings_section,
)
from devops_cli.roadmap.stores.store import (
    FixPlanRecordKey,
    GitHubState,
    ImplementRecordKey,
    StageRecordKey,
)
from devops_cli.roadmap.time_budget import TimeBudget
from devops_cli.roadmap.trust import trusted_replies
from devops_cli.telemetry.instruments import ROADMAP_FIX_PLAN_TOTAL, emit

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from pathlib import Path

    from devops_cli.ai.client import LLMClient
    from devops_cli.dry_run import PlannedRequest
    from devops_cli.github.client import PullStatus
    from devops_cli.roadmap.decision_point import ResolverChain
    from devops_cli.roadmap.stage.stage_change import StageProposal
    from devops_cli.roadmap.stage.stage_jev_screen import ScreenCase
    from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
    from devops_cli.roadmap.stores.store import Item, JobRecord, RoadmapStore

logger = logging.getLogger(__name__)

_GIT_OPERATION: Final[str] = "roadmap.fix_plan"
# One line of `finding_line`: "- `<type>` at <part> (<section>): <problem>", with the capability of
# a requirement after the part (#5410), and ' Evidence: "<quote>"' after it when the finding has a
# quote. A capability holds no space and no bracket (`Locator`). The section ends at the first `): `
# outside a pair of brackets in it, so `what_changes (item 2)` and `The row runs (fast): yes` read
# back whole. A section with a bracket that has no pair ends at the first `): `.
_FINDING_LINE: Final[re.Pattern[str]] = re.compile(
    r"- `(?P<type>[a-z_]+)` at (?P<part>[a-z]+)(?: (?P<capability>[^\s()]+))? "
    r"\((?P<section>(?:[^()]|\([^()]*\))+?|.+?)\): "
    r'(?P<problem>.+?)(?: Evidence: "(?P<quote>.*)")?'
)
# The comments that list the open findings of a plan: the stage comment and this step's comment.
_PLAN_MARKERS: Final[tuple[str, ...]] = (
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
)
# The characters of a commit that a comment or a reason shows.
_SHORT: Final[int] = 12
# The setting of the time budget, which its error and its comment name (#5363).
_BUDGET_SETTING: Final[str] = "roadmap.fix_plan.time_budget_seconds"
# The evicted attempts on one head that do not count (#5413). A later one counts, so a retry that is
# free is bounded.
_HEAD_EVICTIONS: Final[int] = 3


class FixPlanResult(StrEnum):
    """How an attempt ended, as the module says: `revised` pushed a better revision that still has
    an open finding, `cleared` pushed one with no open finding (the label goes), `regated` pushed
    the plan that passed the checks in place of a head that they refused, `dismissed` found no
    open finding in the head (the label goes, no push), `unchanged` made no better plan, `stopped`
    stopped before a gated plan existed, `failed` failed before a plan to push existed,
    `unreadable` could not read the plan of the head (#5213), `timeout` spent the time budget
    before a model call and pushed nothing (#5363) or met the deadline of its Job, and `evicted`
    ended for an eviction, a node drain or a stop of the Service (#5413)."""

    REVISED = "revised"
    CLEARED = "cleared"
    REGATED = "regated"
    DISMISSED = "dismissed"
    UNCHANGED = "unchanged"
    STOPPED = "stopped"
    FAILED = "failed"
    UNREADABLE = "unreadable"
    TIMEOUT = "timeout"
    EVICTED = "evicted"


class FixPlanStop(StrEnum):
    """Why the planner stopped before it judged a plan: a false premise of the item, an open item
    whose plan creates a path that the premise cites, or a task group over the budget."""

    PREMISE = "premise"
    BLOCKED = "blocked"
    OVER_BUDGET = "over_budget"


@dataclass(frozen=True)
class FixPlanTarget:
    """The plan pull request that the step selected: the item, the number of the pull request and
    the read of it. `extra` says why a run with `skip_wait` takes a head over the attempt cap, and
    is empty for any other selection (#5413)."""

    item: Item
    pull: int
    status: PullStatus
    extra: str = ""


@dataclass(frozen=True)
class FixPlanLeftOut:
    """A Staged item that the step did not take, and why."""

    number: int
    reason: str


@dataclass(frozen=True)
class FixPlanAttempt:
    """One attempt: the item, the pull request, the result, the open findings of the review of
    the head before the repair and of the last review of the revision, the head of the branch after
    the attempt, the class of a failure, the counts of the plan runs (`StageAttempt.counts`), and
    the open findings that the last plan comment lists (#5150). `before` is None when the review of
    the head did not run, and `after` when no review of a revision ran (#5213). `step` is the step
    of a failure, `stop` the kind of a stop of the planner, and `reason` the masked reason of a
    failure or of a plan that the reader refused."""

    number: int
    pull: int
    result: FixPlanResult
    before: int | None = None
    after: int | None = None
    head: str = ""
    failure: FailureClass | None = None
    counts: tuple[tuple[str, int], ...] = ()
    comment: int = 0
    step: StepName | None = None
    stop: FixPlanStop | None = None
    reason: str = ""


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
    """The finding that one line of `finding_line` holds, or None for a line of another form, or
    for a type or a part that the review does not name."""
    found = _FINDING_LINE.fullmatch(line)
    if found is None:
        return None
    try:
        return Finding(
            type=DefectType(found["type"]),
            where=Locator(
                part=PlanPart(found["part"]),
                section=found["section"],
                capability=found["capability"] or "",
            ),
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
    attempts on that head, the revisions on that pull request, the time of the last attempt, the
    release of the last counted attempt, and the evicted attempts on that head that did not
    count."""

    pull: str = ""
    head: str = ""
    attempts: int = 0
    revisions: int = 0
    at: datetime | None = None
    version: str = ""
    evicted: int = 0

    @classmethod
    def of(cls, record: JobRecord) -> _Marks:
        pull, _, head = (record.get(FixPlanRecordKey.KEY) or "").partition(":")
        return cls(
            pull,
            head,
            _count(record.get(FixPlanRecordKey.ATTEMPTS)),
            _count(record.get(FixPlanRecordKey.REVISIONS)),
            _time(record.get(FixPlanRecordKey.AT)),
            record.get(FixPlanRecordKey.VERSION) or "",
            _count(record.get(FixPlanRecordKey.EVICTED)),
        )

    def attempts_on(self, pull: int, head: str) -> int:
        return self.attempts if (self.pull, self.head) == (str(pull), head) else 0

    def evicted_on(self, pull: int, head: str) -> int:
        return self.evicted if (self.pull, self.head) == (str(pull), head) else 0

    def revisions_on(self, pull: int) -> int:
        return self.revisions if self.pull == str(pull) else 0


def _staged_pull(item: Item) -> int | None:
    """The plan pull request that the record of the open `item` holds, or None."""
    recorded = item.job_record.get(StageRecordKey.PR) or ""
    if item.state is not GitHubState.OPEN or not recorded.isdigit():
        return None
    return int(recorded)


def _older_release(version: str) -> bool:
    """Whether `version`, the release of the counted attempts on a head, is older than the
    release that runs. A record with no release is older: `fix_plan.version` came with #5413. A
    release that does not parse is not older, so the cap holds."""
    if not version:
        return True
    try:
        return Version(version) < Version(__version__)
    except InvalidVersion:
        return False


def _record_reason(
    item: Item, pull: int | None, now: datetime, *, skip_wait: bool = False
) -> str | None:
    """Why the record of `item` leaves it out, before any read, or None. `skip_wait` leaves out
    the wait of `fix_plan.at`."""
    texts = MESSAGES.roadmap
    marks = _Marks.of(item.job_record)
    wait = timedelta(hours=CONST_ROADMAP_FIX_PLAN_WAIT_HOURS)
    if pull is None or item.status != CONST_ROADMAP_STATUS_READY:
        return texts.fix_plan_left_not_staged
    if item.job_record.get(ImplementRecordKey.JOB):
        return texts.fix_plan_left_runner
    if (owner := claimed_by(item)) is not None:
        return texts.item_left_claimed.format(owner=owner)
    if not skip_wait and marks.at is not None and now - marks.at < wait:
        return texts.fix_plan_left_recent.format(
            at=marks.at.isoformat(), hours=CONST_ROADMAP_FIX_PLAN_WAIT_HOURS
        )
    if (count := marks.revisions_on(pull)) >= CONST_ROADMAP_FIX_PLAN_REVISIONS:
        return texts.fix_plan_left_revisions.format(count=count, pull=pull)
    return None


def _pull_reason(
    item: Item, pull: int, status: PullStatus, *, skip_wait: bool = False
) -> str | None:
    """Why the read of plan pull request `pull` leaves `item` out, or None. With `skip_wait`, a
    head over the attempt cap whose counted attempts ran on an older release is not left out."""
    texts = MESSAGES.roadmap
    marks = _Marks.of(item.job_record)
    count = marks.attempts_on(pull, status.head_sha)
    if not status.is_open_draft:
        return texts.fix_plan_left_not_draft.format(pull=pull)
    if PLAN_NEEDS_FIX_LABEL not in status.labels:
        return texts.fix_plan_left_no_label.format(pull=pull)
    if count >= CONST_ROADMAP_FIX_PLAN_HEAD_ATTEMPTS and not (
        skip_wait and _older_release(marks.version)
    ):
        head = status.head_sha[:_SHORT]
        return texts.fix_plan_left_attempts.format(head=head, pull=pull, count=count)
    return None


def _extra(item: Item, pull: int, status: PullStatus) -> str:
    """Why a run with `skip_wait` takes head `status` of plan pull request `pull` over the attempt
    cap, or an empty text for a head under the cap."""
    marks = _Marks.of(item.job_record)
    count = marks.attempts_on(pull, status.head_sha)
    if count < CONST_ROADMAP_FIX_PLAN_HEAD_ATTEMPTS:
        return ""
    return MESSAGES.roadmap.fix_plan_extra_attempt.format(
        head=status.head_sha[:_SHORT],
        pull=pull,
        count=count,
        version=marks.version or MESSAGES.roadmap.fix_plan_no_release,
        current=__version__,
    )


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
    skip_wait: bool = False,
) -> tuple[FixPlanTarget | None, tuple[FixPlanLeftOut, ...]]:
    """The plan pull request that the step takes, and the Staged items it left out before it, as
    the module says. `item` or `pull` names the one item to judge. It reads a pull request only for
    an item that the record rules keep. `skip_wait` leaves out the wait and takes a head of an
    older release over the attempt cap once, with a warning that says why (#5413)."""
    now = now or datetime.now(UTC)
    candidates, left = _candidates(store, item, pull)
    for each in candidates:
        pull = _staged_pull(each)
        reason = _record_reason(each, pull, now, skip_wait=skip_wait)
        if reason is None and pull is not None:
            status = get_github_session().client.get_pull_status(repo, pull)
            reason = _pull_reason(each, pull, status, skip_wait=skip_wait)
            if reason is None:
                extra = _extra(each, pull, status)
                if extra:
                    logger.warning(extra)
                return FixPlanTarget(each, pull, status, extra), tuple(left)
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


@dataclass(frozen=True)
class _Attempt:
    """The parts of one attempt that its writes need."""

    store: RoadmapStore
    repo: str
    source: Path
    target: FixPlanTarget
    base: str
    budget: TimeBudget


@dataclass(frozen=True)
class _Decision:
    """What the step makes of a revision: the result, the plan to push, and whether the label
    goes."""

    result: FixPlanResult
    push: StagedChange | None = None
    unlabel: bool = False


def _stop_of(outcome: object) -> FixPlanStop | None:
    """The kind of a stop of the planner, or None for another outcome."""
    if isinstance(outcome, FalsePremise):
        return FixPlanStop.PREMISE
    if isinstance(outcome, Blocked):
        return FixPlanStop.BLOCKED
    if isinstance(outcome, OverBudget):
        return FixPlanStop.OVER_BUDGET
    return None


def _decide(revision: PlanRevision, head: StageProposal) -> _Decision:
    """The result of `revision` of the plan `head`, in the order of the module (#5213). A spent
    time budget pushes nothing (#5363). A revision is better when its reviews fixed more open
    findings of the head than they added: the later reviews judged each finding of the head, so
    the step compares no counts of two independent reviews (#5409)."""
    outcome, gated = revision.outcome, revision.gated
    if isinstance(outcome, StageFailure) and outcome.failure_class is FailureClass.TIMEOUT:
        return _Decision(FixPlanResult.TIMEOUT)
    if _stop_of(outcome) is not None and not revision.reviewed:
        return _Decision(FixPlanResult.STOPPED)
    failed = isinstance(outcome, StageFailure)
    if failed and gated is None:
        return _Decision(FixPlanResult.FAILED)
    repaired = revision.repaired
    if (
        repaired is not None
        and not same_plan(repaired.proposal, head if gated is None else gated.proposal)
        and len(revision.fixed) > len(revision.added)
    ):
        after = len(repaired.open_findings)
        result = FixPlanResult.REVISED if after else FixPlanResult.CLEARED
        return _Decision(result, repaired, unlabel=not after)
    clean = revision.reviewed and not revision.before and not failed
    if gated is not None:
        return _Decision(FixPlanResult.REGATED, gated, unlabel=clean)
    if clean:
        return _Decision(FixPlanResult.DISMISSED, unlabel=True)
    return _Decision(FixPlanResult.UNCHANGED)


def _stop_evidence(outcome: object) -> str:
    """The evidence of a stop of the planner, for the comment."""
    texts = MESSAGES.roadmap
    if isinstance(outcome, FalsePremise):
        return texts.fix_plan_stop_premise.format(evidence=" ".join(outcome.evidence))
    if isinstance(outcome, Blocked):
        return texts.fix_plan_stop_blocked.format(
            paths=", ".join(f"`{path}`" for path in outcome.paths),
            issues=", ".join(f"#{number}" for number in outcome.blockers),
        )
    if isinstance(outcome, OverBudget):
        worst = outcome.worst
        return texts.fix_plan_stop_over_budget.format(
            title=safe_text(worst.group.title), tokens=worst.tokens, budget=outcome.budget
        )
    return ""


def _regated_why(done: FixPlanAttempt, decision: _Decision) -> str:
    """Why the label of a pushed gated plan goes or stays."""
    texts = MESSAGES.roadmap
    if decision.unlabel:
        return texts.fix_plan_regated_clean
    if done.step is not None:
        failure = done.failure.value if done.failure is not None else ""
        return texts.fix_plan_regated_failed.format(step=done.step.value, failure=failure)
    return texts.fix_plan_regated_open.format(before=done.before or 0)


def _counts_text(counts: Iterable[tuple[str, int]]) -> str:
    """The counts of the plan runs of an attempt on one line, as `<name> <value>` pairs."""
    return ", ".join(f"{name} {value}" for name, value in counts)


def _comment(
    target: FixPlanTarget,
    done: FixPlanAttempt,
    decision: _Decision,
    revision: PlanRevision,
    listed: tuple[Finding, ...],
    budget: int,
) -> str | None:
    """The comment of an attempt, or None for an attempt that posts none. A comment that keeps the
    label lists the open findings that keep it: those of the last review, or those of the last
    plan comment when no review ran, so the next attempt reads them (`comment_open_findings`).
    `budget` is the time budget of the step in seconds, which a `timeout` comment names."""
    texts = MESSAGES.roadmap
    values = {
        "marker": CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER,
        "pull": target.pull,
        "head": done.head[:_SHORT],
        "before": done.before or 0,
        "after": done.after or 0,
    }
    held = revision.before if revision.reviewed else listed
    match done.result:
        case FixPlanResult.REVISED:
            after = decision.push.open_findings if decision.push is not None else ()
            return texts.fix_plan_comment_revised.format(
                **values, findings=open_findings_section(after)
            )
        case FixPlanResult.CLEARED:
            return texts.fix_plan_comment_cleared.format(**values)
        case FixPlanResult.REGATED:
            return texts.fix_plan_comment_regated.format(
                **values,
                why=_regated_why(done, decision),
                findings="" if decision.unlabel else open_findings_section(held),
            )
        case FixPlanResult.DISMISSED:
            dismissed = (
                texts.fix_plan_dismissed_findings.format(
                    findings="\n".join(finding_line(finding) for finding in listed)
                )
                if listed
                else ""
            )
            return texts.fix_plan_comment_dismissed.format(**values, dismissed=dismissed)
        case FixPlanResult.TIMEOUT:
            return texts.fix_plan_comment_timeout.format(
                **values,
                budget=budget,
                step=done.step.value if done.step is not None else "",
                counts=_counts_text(
                    revision.attempt.counts().items() if revision.attempt is not None else ()
                ),
                findings=open_findings_section(held),
            )
        case FixPlanResult.STOPPED:
            return texts.fix_plan_comment_stopped.format(
                **values,
                evidence=_stop_evidence(revision.outcome),
                findings=open_findings_section(listed),
            )
        case _:
            return None


def _attempt_of(
    target: FixPlanTarget, revision: PlanRevision, decision: _Decision, head: str
) -> FixPlanAttempt:
    """The attempt that `revision` and `decision` make, with the head of the branch after it."""
    outcome = revision.outcome
    failure: FailureClass | None = None
    step: StepName | None = None
    reason = ""
    if isinstance(outcome, StageFailure):
        failure, step, reason = outcome.failure_class, outcome.step, bounded_text(outcome.reason)
    elif isinstance(outcome, FalsePremise):
        failure = FailureClass.PREMISE_FALSE
    repaired = revision.repaired
    return FixPlanAttempt(
        target.item.number,
        target.pull,
        decision.result,
        len(revision.before) if revision.reviewed else None,
        len(repaired.open_findings) if repaired is not None else None,
        head,
        failure,
        step=step,
        stop=_stop_of(outcome),
        reason=reason,
    )


def _settle(
    attempt: _Attempt,
    head_plan: StageProposal,
    listed: tuple[Finding, ...],
    revision: PlanRevision,
) -> FixPlanAttempt:
    """Write what `revision` makes of the plan `head_plan`, as the module says, and the attempt it
    was. `listed` are the open findings of the last plan comment."""
    target = attempt.target
    decision = _decide(revision, head_plan)
    head = target.status.head_sha
    pushed = decision.push
    if pushed is not None:
        head = _push(attempt.source, target, attempt.base, pushed)
        if (pushed.title, pushed.body) != (target.status.title, target.status.body):
            client = get_github_session().client
            client.update_pull(attempt.repo, target.pull, title=pushed.title, body=pushed.body)
    if decision.unlabel:
        remove_pull_labels(attempt.store, target.pull, (PLAN_NEEDS_FIX_LABEL,))
    done = _attempt_of(target, revision, decision, head)
    comment = _comment(target, done, decision, revision, listed, attempt.budget.seconds)
    if comment is not None:
        attempt.store.comment(target.item.number, comment)
    return done


def _result_marks(
    target: FixPlanTarget, done: FixPlanAttempt
) -> Mapping[FixPlanRecordKey, str | None]:
    """The marks that end an attempt: its result, and after a push the new head with no attempt,
    no evicted attempt and one more revision."""
    marks: dict[FixPlanRecordKey, str | None] = {FixPlanRecordKey.RESULT: done.result.value}
    if done.head == target.status.head_sha:
        return marks
    revisions = _Marks.of(target.item.job_record).revisions_on(target.pull) + 1
    return marks | {
        FixPlanRecordKey.KEY: f"{target.pull}:{done.head}",
        FixPlanRecordKey.ATTEMPTS: "0",
        FixPlanRecordKey.REVISIONS: str(revisions),
        FixPlanRecordKey.EVICTED: None,
    }


def _detail(done: FixPlanAttempt) -> str:
    """What the attempt `done` found, for its line: one text for each path of the attempt."""
    texts = MESSAGES.roadmap
    if done.result is FixPlanResult.STOPPED:
        stop = done.stop.value if done.stop is not None else ""
        return texts.fix_plan_detail_stopped.format(stop=stop)
    if done.step is not None:
        failure = done.failure.value if done.failure is not None else ""
        if done.before is None:
            return texts.fix_plan_detail_failed.format(step=done.step.value, failure=failure)
        return texts.fix_plan_detail_failed_reviewed.format(
            before=done.before, step=done.step.value, failure=failure
        )
    if done.stop is FixPlanStop.OVER_BUDGET:
        return texts.fix_plan_detail_over_budget.format(before=done.before or 0)
    if done.after is not None:
        return texts.fix_plan_detail_repaired.format(before=done.before or 0, after=done.after)
    return texts.fix_plan_detail_reviewed.format(before=done.before or 0)


def _attempt_line(done: FixPlanAttempt) -> str:
    """The line that reports `done`: its result, what it found, and the reason of a failure."""
    texts = MESSAGES.roadmap
    reason = texts.fix_plan_reason.format(reason=done.reason) if done.reason else ""
    if done.result is FixPlanResult.UNREADABLE:
        return texts.fix_plan_unreadable.format(
            pull=done.pull,
            number=done.number,
            head=done.head[:_SHORT],
            hours=CONST_ROADMAP_FIX_PLAN_WAIT_HOURS,
            reason=reason,
        )
    return texts.fix_plan_attempt.format(
        pull=done.pull,
        number=done.number,
        result=done.result.value,
        detail=_detail(done),
        comment=done.comment,
        reason=reason,
    )


def _report(repo: str, done: FixPlanAttempt) -> None:
    """Log the line and the result line of `done`, and count its result. The result line holds
    `before` and `after` only when the attempt measured them (#5213)."""
    logger.info(_attempt_line(done))
    counts = {**dict(done.counts), "comment": done.comment}
    if done.before is not None:
        counts["before"] = done.before
    if done.after is not None:
        counts["after"] = done.after
    names = {
        key: value.value
        for key, value in (("stop", done.stop), ("step", done.step))
        if value is not None
    }
    log_job_result(
        RoadmapJob.FIX_PLAN,
        repo,
        done.number,
        done.result.value,
        failure=done.failure,
        counts=counts,
        names=names,
    )
    emit(ROADMAP_FIX_PLAN_TOTAL, 1, {"repo": repo, "result": done.result.value})


def _unreadable(attempt: _Attempt, now: datetime, error: PlanReadError) -> FixPlanAttempt:
    """The attempt on a plan that the reader refuses (#5213): the record gets only the time and the
    result, so the attempt uses no attempt of the head and the next read waits the hours of
    `fix_plan.at`. One warning names the file and the masked reason, and no result line counts it
    against the job: the defect is in the writer or the reader of the plan."""
    target = attempt.target
    done = FixPlanAttempt(
        target.item.number,
        target.pull,
        FixPlanResult.UNREADABLE,
        head=target.status.head_sha,
        reason=bounded_text(f"{error.path}: {error.reason}"),
    )
    attempt.store.set_marks(
        target.item,
        {FixPlanRecordKey.AT: now.isoformat(), FixPlanRecordKey.RESULT: done.result.value},
    )
    logger.warning(_attempt_line(done))
    emit(ROADMAP_FIX_PLAN_TOTAL, 1, {"repo": attempt.repo, "result": done.result.value})
    return done


def _open_creates(store: RoadmapStore, source: Path, base: str) -> Callable[[], Mapping[str, int]]:
    """The read of the paths that the open plans on the default branch create, as the stage job
    reads them (#3418). The planner reads them at most once for the attempt, and only when the
    premise cites a path that the default branch lacks."""

    def read() -> Mapping[str, int]:
        planned = planned_changes_at(source, f"origin/{base}", base, operation=_GIT_OPERATION)
        return open_plan_creates(store, source, planned, operation=_GIT_OPERATION)

    return cache(read)


def _start_marks(target: FixPlanTarget, now: datetime) -> Mapping[FixPlanRecordKey, str | None]:
    """The marks that start an attempt on the head of `target`: one more attempt on the head, the
    time, the release that runs, and the evicted attempts of the head, which a new head resets."""
    marks = _Marks.of(target.item.job_record)
    head = target.status.head_sha
    revisions = marks.revisions_on(target.pull)
    evicted = marks.evicted_on(target.pull, head)
    return {
        FixPlanRecordKey.KEY: f"{target.pull}:{head}",
        FixPlanRecordKey.ATTEMPTS: str(marks.attempts_on(target.pull, head) + 1),
        FixPlanRecordKey.REVISIONS: str(revisions) if revisions else None,
        FixPlanRecordKey.AT: now.isoformat(),
        FixPlanRecordKey.RESULT: None,
        FixPlanRecordKey.VERSION: __version__,
        FixPlanRecordKey.EVICTED: str(evicted) if evicted else None,
    }


def _kill_marks(target: FixPlanTarget, kill: AttemptKill) -> Mapping[FixPlanRecordKey, str | None]:
    """The marks that a kill of the class `kill` writes after the start marks, as the module says.
    A free evicted attempt gets the count, the time and the release of the record before it back,
    so no rule counts it. Another kill keeps the start marks, so the attempt counts."""
    record = target.item.job_record
    marks = _Marks.of(record)
    head = target.status.head_sha
    evicted = marks.evicted_on(target.pull, head)
    if kill is AttemptKill.DEADLINE:
        return {FixPlanRecordKey.RESULT: FixPlanResult.TIMEOUT.value}
    if evicted >= _HEAD_EVICTIONS:
        return {FixPlanRecordKey.RESULT: FixPlanResult.EVICTED.value}
    return {
        FixPlanRecordKey.KEY: f"{target.pull}:{head}",
        FixPlanRecordKey.ATTEMPTS: str(marks.attempts_on(target.pull, head)),
        FixPlanRecordKey.AT: record.get(FixPlanRecordKey.AT),
        FixPlanRecordKey.VERSION: record.get(FixPlanRecordKey.VERSION),
        FixPlanRecordKey.EVICTED: str(evicted + 1),
        FixPlanRecordKey.RESULT: FixPlanResult.EVICTED.value,
    }


def _killed(attempt: _Attempt, comment: int, kill: AttemptKill) -> None:
    """Write the marks of a kill of the class `kill` on the attempt `attempt`, log one warning,
    and count the result. A deadline kill also logs its result line with `comment`, the open
    findings of the last plan comment. The kill writes in the grace period of the pod, so it
    makes only the read and the write of `set_marks`, which writes the marks on the issue as it
    is now, and posts no comment."""
    store, target = attempt.store, attempt.target
    number, head = target.item.number, target.status.head_sha
    marks = _kill_marks(target, kill)
    store.set_marks(target.item, marks)
    texts = MESSAGES.roadmap
    before = _Marks.of(target.item.job_record)
    if FixPlanRecordKey.EVICTED in marks:
        line = texts.fix_plan_killed_free.format(
            pull=target.pull,
            number=number,
            head=head[:_SHORT],
            evicted=before.evicted_on(target.pull, head) + 1,
            limit=_HEAD_EVICTIONS,
        )
    else:
        line = texts.fix_plan_killed_counted.format(
            kill=kill.value,
            pull=target.pull,
            number=number,
            head=head[:_SHORT],
            count=before.attempts_on(target.pull, head) + 1,
        )
    logger.warning(line)
    result = FixPlanResult.TIMEOUT if kill is AttemptKill.DEADLINE else FixPlanResult.EVICTED
    if kill is AttemptKill.DEADLINE:
        log_job_result(
            RoadmapJob.FIX_PLAN,
            attempt.repo,
            number,
            result.value,
            failure=FailureClass.TIMEOUT,
            counts={"comment": comment},
            names={"kill": kill.value},
        )
    emit(ROADMAP_FIX_PLAN_TOTAL, 1, {"repo": attempt.repo, "result": result.value})


def _attempt(
    attempt: _Attempt,
    now: datetime,
    *,
    model: LLMClient | ToolboxModel | None,
    verifier: ToolboxModel,
    screen: ResolverChain[ScreenCase] | None = None,
) -> FixPlanAttempt | FixPlanLeftOut:
    """One attempt on the selected plan, or why the branch stops it before any write."""
    store, source, target = attempt.store, attempt.source, attempt.target
    number, status = target.item.number, target.status
    raise_if_service_stops(f"the fix-plan of #{number}")
    _git(source, "fetch", "-q", "origin", attempt.base, status.head_ref)
    if (reason := _branch_reason(source, target)) is not None:
        return FixPlanLeftOut(number, reason)
    try:
        stage_target, proposal = _head_plan(source, target)
    except PlanReadError as error:
        return _unreadable(attempt, now, error)
    store.set_marks(target.item, _start_marks(target, now))
    listed: tuple[Finding, ...] = ()
    try:
        sha = _git(source, "rev-parse", f"origin/{attempt.base}")
        listed = comment_open_findings(plan_comment(store, number, target.pull))
        revision = revise_plan(
            stage_target,
            proposal,
            repo=attempt.repo,
            checkout=source,
            sha=sha,
            verifier=verifier,
            model=model,
            findings=listed,
            open_creates=_open_creates(store, source, attempt.base),
            screen=screen,
            time_budget=attempt.budget,
        )
    except ServiceStoppingError as stop:
        _killed(attempt, len(listed), kill_of(attempt.budget, stop))
        raise
    except AttemptKilled as killed:
        kill = kill_of(attempt.budget, killed)
        _killed(attempt, len(listed), kill)
        raise AttemptKilled(kill) from killed
    done = _settle(attempt, proposal, listed, revision)
    counts = revision.attempt.counts() if revision.attempt is not None else {}
    done = replace(done, counts=tuple(counts.items()), comment=len(listed))
    store.set_marks(store.item(number) or target.item, _result_marks(target, done))
    _report(attempt.repo, done)
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
    screen: ResolverChain[ScreenCase] | None = None,
    skip_wait: bool = False,
) -> FixPlanRun:
    """Select one plan pull request of `repo` and, with `confirm`, run one attempt on it in the
    clone `source`, as the module says. Without `confirm` the call makes no model call and no
    write. `model`, `verifier` and `screen` are those of `plan_stage`; with no `verifier`, the
    model of the task `verification` reviews. `skip_wait` is the rule of `select_fix_plan` for a
    named item (#5413). A failed read or write of GitHub or git raises after the attempt marks, and
    a kill raises `AttemptKilled` with its class after the marks of the kill. The time budget
    `roadmap.fix_plan.time_budget_seconds` starts with the call (#5363)."""
    budget = TimeBudget.start(load_settings().roadmap.fix_plan.time_budget_seconds, _BUDGET_SETTING)
    now = now or datetime.now(UTC)
    target, left = select_fix_plan(
        store, repo=repo, item=item, pull=pull, now=now, skip_wait=skip_wait
    )
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
        _Attempt(store, repo, source, target, base, budget),
        now,
        model=model,
        verifier=verifier,
        screen=screen,
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
    if target is not None and target.extra:
        lines.append(target.extra)
    lines += [
        texts.fix_plan_left.format(number=left.number, reason=left.reason) for left in run.left_out
    ]
    done = run.attempt
    if done is not None:
        lines.append(_attempt_line(done))
        if done.counts:
            lines.append(
                texts.fix_plan_counts.format(
                    counts=_counts_text(done.counts), head=done.head[:_SHORT]
                )
            )
    return "\n".join(lines)


__all__ = [
    "FixPlanAttempt",
    "FixPlanLeftOut",
    "FixPlanResult",
    "FixPlanRun",
    "FixPlanStop",
    "FixPlanTarget",
    "comment_open_findings",
    "dry_run_fix_plan",
    "plan_comment",
    "render_fix_plan",
    "run_fix_plan",
    "select_fix_plan",
]
