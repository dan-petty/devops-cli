"""The roadmap step `review`: one verdict of #5968 for a bot pull request (#5969).

The fix steps repair a pull request, and the review step says what the pull request needs. It
gives an open bot pull request exactly one verdict, records it as the verdict label that the grades
of `devops roadmap eval grades` read (`pr_verdict.py`), posts one comment with the verdict, its
reason and its evidence, and takes the next action of the verdict.

**Facts first.** `review_facts.read_facts` reads the facts that a program can decide on.

**Rules.** The first rule that applies gives the verdict:

1. The item is closed: issue changed.
2. The text of the item changed since the plan (`stage.text_hash`): issue changed.
3. A merged pull request since the merge base changed the change folder of the item, and it is not
   the plan pull request of the item: issue changed.
4. A merge conflict: needs fix, by `fix-conflict` (`fix-plan` for a plan).
5. A failed check that is not of CI infrastructure: needs fix, by `fix-checks` (`fix-plan` for a
   plan).
6. Only a failed check of CI infrastructure, a check that runs, or no check run: the step waits,
   with no verdict.
7. A plan with an open finding, or with the label `verdict/fix-plan`: needs fix, by `fix-plan`.
8. An unresolved review thread: needs fix.
9. A pull request that `draft_readiness` refuses (a delivery whose change is not found, not ticked
   or not archived; a plan text that is a placeholder): needs fix.

**Model.** When no rule applies, the model of the task `ai.tasks.review` reads the diff, the plan
and the issue (`review_facts.read_case`), and says whether the diff does what they ask (a
delivery), or whether the plan can be built and is correct (a plan). Its reply is a proposal: the
step keeps only evidence that names a file of the diff, and a discard with no such evidence becomes
needs fix. `review_judge.py` holds the cap of new tokens, `roadmap.review.token_budget`.

**Guards.** `roadmap.review.mode` `off` sends no request. The step skips a pull request whose head
moved from `--head`, or whose item a live Job holds (`job_holds` or `stage.job`). It stops on a pull
request of a person and on a claim label (`claim_labels`, which leaves out `owner/service`). The
rules run on each call, so a new fact of a judged head gives a new verdict; only the model is asked
once for each head and issue text (`review.key`, `review.source`). A rule verdict that the record
and the label hold writes nothing again. A pull request with `roadmap.review.rounds` verdicts gets
one comment that leaves it for a person, and no model call. A wait on CI infrastructure logs one
line, and with writes it ends after `roadmap.review.infra_wait_hours` with one comment for a
person. An Issue changed verdict answers one issue text (`review.text`), so the updated work of
that text is judged.

**Writes.** Only with `confirm` in the mode `on`; else the step returns the verdict and the action
that it would take, and writes nothing. Before the first write the step reads the pull request
again, and a head that moved writes nothing. The verdict label replaces the other verdict labels
that only this step writes; `verdict/fix-plan` stays, because the stage job, the row `plan_drift`
and the step fix-plan also write it. Then:

- Mergeable: a draft is marked ready (`mark_ready` with the judged head). The pipeline is then done
  with the item until a person merges.
- Needs fix: the label and the due fix stay for the watch row; `verdict/fix-plan` starts the row
  fix-plan. A pull request that a bot marked ready becomes a draft again (`mark_draft`), because the
  fix rows take only a draft; one that a person marked ready stays ready. The watch row holds the
  ready mark while a verdict label other than `verdict/mergeable` is on the pull request.
- Discard of the model alone: the label and the comment, and a person decides the close (#6024).
- Discard of a rule: the step checks the shared branch and the withdraw before the first write,
  marks the start (`review.discard`), deletes the branch with a lease on the judged head
  (`Withdraw`), closes the pull request, and returns the item to New with `apply_return`, which
  clears the keys of the plan or of the delivery. A call on the closed pull request ends a discard
  that stopped on the way. A branch that holds the work of the other kind is left for a person.
- Issue changed: the label marks the work for an update, a ready pull request goes back to draft as
  for needs fix, and the verdict scores nothing.

The record keeps the count of verdicts of the pull request, the key, the verdict and the source of
the last one (`ReviewRecordKey`). Each judged or failed attempt logs one result line (job
`review`).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Protocol

from devops_cli.config.constants import CONST_ROADMAP_REVIEW_COMMENT_MARKER
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import DevOpsCLIError, RoadmapImplementError, RoadmapPullReviewLimitError
from devops_cli.git.branch_form import issue_of_branch
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary
from devops_cli.github.merge_readiness import merge_conflict
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.claim import claim_labels
from devops_cli.roadmap.failure import FailureClass, FailureEvidence, classify_failure
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from devops_cli.roadmap.pr_verdict import PullKind, Verdict, verdict_label
from devops_cli.roadmap.pull_labels import add_pull_labels, remove_pull_labels
from devops_cli.roadmap.return_item import apply_return, plan_return
from devops_cli.roadmap.stage.stage_verify import FIX_PLAN_LABEL
from devops_cli.roadmap.status_sync import job_holds
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.steps.fix_checks import is_bot_author
from devops_cli.roadmap.steps.ready import mark_draft, mark_ready, read_ready_draft
from devops_cli.roadmap.steps.review_facts import (
    EVIDENCE_LINES,
    ReplyVerdict,
    ReviewCase,
    ReviewFacts,
    ReviewReply,
    issue_of_path,
    pull_kind_of,
    read_case,
    read_facts,
    record_number,
    safe,
)
from devops_cli.roadmap.stores.store import (
    STAGE_REMOVAL_KEYS,
    ImplementRecordKey,
    Item,
    PostedComment,
    ReviewRecordKey,
    RoadmapStore,
    StageRecordKey,
)
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.config.defaults import RowMode
    from devops_cli.github.client import PullStatus

logger = logging.getLogger(__name__)


class ReviewResult(StrEnum):
    """How one call of the step review ended (#5969)."""

    JUDGED = "judged"
    WAIT = "wait"
    SKIPPED = "skipped"
    STOPPED = "stopped"
    CAPPED = "capped"
    FAILED = "failed"


class DueFix(StrEnum):
    """The fix step that a verdict needs fix leaves for the watch row."""

    FIX_CHECKS = "fix-checks"
    FIX_CONFLICT = "fix-conflict"
    FIX_PLAN = "fix-plan"


# The verdict labels that only the review step writes, so it replaces them. `verdict/fix-plan` has
# other writers and stays.
OWN_LABELS: Final[frozenset[str]] = frozenset(
    {
        "verdict/mergeable",
        "verdict/fix-implementation",
        "verdict/discard-plan",
        "verdict/discard-implementation",
        "verdict/issue-changed",
    }
)
# The name of each verdict in a comment.
_VERDICT_NAMES: Final[Mapping[Verdict, str]] = {
    Verdict.MERGEABLE: "Mergeable",
    Verdict.NEEDS_FIX: "Needs fix",
    Verdict.DISCARD_PLAN: "Discard plan",
    Verdict.DISCARD_IMPLEMENTATION: "Discard implementation",
    Verdict.ISSUE_CHANGED: "Issue changed",
}
_DISCARDS: Final[frozenset[Verdict]] = frozenset(
    {Verdict.DISCARD_PLAN, Verdict.DISCARD_IMPLEMENTATION}
)
# The verdicts that send the work back: a ready pull request becomes a draft again, so the fix rows
# take it and no person merges it.
_BACK_TO_DRAFT: Final[frozenset[Verdict]] = frozenset({Verdict.NEEDS_FIX, Verdict.ISSUE_CHANGED})
_DRAFT_AGAIN: Final[str] = "make the pull request a draft again; "
# The keys of a delivery that a discard clears, as the return of the implement job clears them.
_DELIVERY_KEYS: Final[tuple[ImplementRecordKey, ...]] = (
    ImplementRecordKey.GROUP,
    ImplementRecordKey.SHA,
    ImplementRecordKey.BRANCH,
    ImplementRecordKey.PR,
    ImplementRecordKey.BASE,
    ImplementRecordKey.PLAN_SUMMARY,
    ImplementRecordKey.CHECKED_SHA,
    ImplementRecordKey.PUBLISHED_SHA,
    ImplementRecordKey.RESULT,
)


@dataclass(frozen=True)
class Judgement:
    """One verdict with its reason, its evidence and the fix it leaves. `source` is `rule` or
    `model`."""

    verdict: Verdict
    reason: str
    evidence: tuple[str, ...] = ()
    due: DueFix | None = None
    source: str = "rule"


@dataclass(frozen=True)
class Waiting:
    """No verdict yet: a check runs, or only CI infrastructure failed (`infra`)."""

    reason: str
    infra: bool = False


class ReviewJudge(Protocol):
    """The model judge of the step. A test passes its own."""

    def judge(self, case: ReviewCase) -> ReviewReply:
        """The verdict of the model on `case`. A call that fails raises a `DevOpsCLIError`."""
        ...


# Delete the branch `branch` of `origin` with a lease on the commit `lease` (#5969).
Withdraw = Callable[[str, str], None]


@dataclass(frozen=True)
class ReviewReport:
    """The outcome of one call of the step review. `written` says whether it wrote to GitHub."""

    repo: str
    pull: int
    result: ReviewResult
    head: str = ""
    kind: PullKind | None = None
    verdict: Verdict | None = None
    label: str | None = None
    due: DueFix | None = None
    rounds: int = 0
    reason: str = ""
    evidence: tuple[str, ...] = ()
    action: str = ""
    written: bool = False

    def to_json(self) -> str:
        data: dict[str, Any] = {
            "job": "review",
            "repo": self.repo,
            "pull": self.pull,
            "result": self.result.value,
            "written": self.written,
        }
        optional: dict[str, Any] = {
            "head": self.head,
            "kind": self.kind.value if self.kind else None,
            "verdict": self.verdict.value if self.verdict else None,
            "label": self.label,
            "due": self.due.value if self.due else None,
            "rounds": self.rounds,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "action": self.action,
        }
        data.update({key: value for key, value in optional.items() if value})
        return json.dumps(data)


# ── The rules ────────────────────────────────────────────────────────────────────────────────


def _changed_issue(facts: ReviewFacts) -> Judgement | None:
    """Rules 1 to 3: the item closed, its text changed, or related work changed its plan."""
    if not facts.item_open:
        return Judgement(Verdict.ISSUE_CHANGED, f"Item #{facts.item_number} is closed.")
    if facts.text_changed:
        return Judgement(
            Verdict.ISSUE_CHANGED,
            f"The text of item #{facts.item_number} changed after the plan was written.",
            ("`stage.text_hash` is not the hash of the issue text now",),
        )
    for related in facts.related:
        own = [path for path in related.files if issue_of_path(path) == facts.item_number]
        if own and related.number != facts.own_plan:
            return Judgement(
                Verdict.ISSUE_CHANGED,
                f"Pull request #{related.number} merged after the base of this pull request and "
                f"changed the change folder of item #{facts.item_number}.",
                tuple(f"#{related.number} changed `{path}`" for path in own[:EVIDENCE_LINES]),
            )
    return None


def _fix_of(facts: ReviewFacts, delivery_fix: DueFix | None) -> DueFix | None:
    """The due fix: `fix-plan` for a plan, which revises the plan on the latest base branch, else
    the fix of the delivery."""
    return DueFix.FIX_PLAN if facts.kind is PullKind.PLAN else delivery_fix


def _failed_checks(checks: CheckVerdictSummary) -> tuple[list[str], list[str]]:
    """The names of the failed checks of CI infrastructure, and of the other failed checks."""
    failed = [c.name for c in checks.items if c.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL)]
    infra = [
        name
        for name in failed
        if classify_failure(FailureEvidence(check=name)) is FailureClass.CI_INFRA
    ]
    return infra, [name for name in failed if name not in infra]


def _check_rules(facts: ReviewFacts) -> Judgement | Waiting | None:
    """Rules 5 and 6: a failed check, or a wait for the checks."""
    checks = facts.checks
    if checks is None or checks.reports_nothing:
        return Waiting("The head reports no check run yet.")
    if checks.unread_reason or checks.unread_count:
        return Waiting(checks.unread_reason or "A check run could not be read.")
    infra, failed = _failed_checks(checks)
    if failed:
        return Judgement(
            Verdict.NEEDS_FIX,
            f"{len(failed)} check(s) failed on the head.",
            tuple(f"check `{name}` failed" for name in failed[:EVIDENCE_LINES]),
            _fix_of(facts, DueFix.FIX_CHECKS),
        )
    if infra:
        return Waiting(f"Only CI infrastructure failed: {', '.join(infra)}.", infra=True)
    if checks.pending_count:
        return Waiting(f"{checks.pending_count} check(s) still run.")
    return None


def _open_work(facts: ReviewFacts) -> Judgement | None:
    """Rules 7 to 9: open findings of a plan, unresolved threads, and an incomplete pull request."""
    if facts.kind is PullKind.PLAN and (facts.findings or FIX_PLAN_LABEL in facts.labels):
        evidence = facts.findings or (f"the pull request holds `{FIX_PLAN_LABEL}`",)
        return Judgement(
            Verdict.NEEDS_FIX,
            "The plan has open findings.",
            evidence[:EVIDENCE_LINES],
            DueFix.FIX_PLAN,
        )
    if facts.threads:
        return Judgement(
            Verdict.NEEDS_FIX,
            f"{len(facts.threads)} review thread(s) are not resolved.",
            tuple(f"thread at `{place}`" for place in facts.threads[:EVIDENCE_LINES]),
            _fix_of(facts, None),
        )
    if facts.incomplete:
        return Judgement(Verdict.NEEDS_FIX, facts.incomplete, (), _fix_of(facts, None))
    return None


def rule_judgement(facts: ReviewFacts) -> Judgement | Waiting | None:
    """The verdict that the facts give with no model, a wait, or None when only the model can
    decide. The rules are the ones of the module text, in that order."""
    if changed := _changed_issue(facts):
        return changed
    if merge_conflict(facts.mergeable, facts.mergeable_state):
        return Judgement(
            Verdict.NEEDS_FIX,
            "The pull request has a merge conflict with its base branch.",
            (f"mergeable state `{facts.mergeable_state or 'dirty'}`",),
            _fix_of(facts, DueFix.FIX_CONFLICT),
        )
    if checked := _check_rules(facts):
        return checked
    return _open_work(facts)


def model_judgement(facts: ReviewFacts, reply: ReviewReply) -> Judgement:
    """The verdict of `reply` for the pull request of `facts`. Only evidence that names a file of
    the diff stays, and a discard with no such evidence becomes needs fix."""
    known = set(facts.files)
    evidence = tuple(
        f"`{safe(each.path, 300)}{f':{each.line}' if each.line else ''}`: {safe(each.note, 300)}"
        for each in reply.evidence
        if each.path in known
    )
    reason = safe(reply.reason)
    match reply.verdict:
        case ReplyVerdict.MERGEABLE:
            return Judgement(Verdict.MERGEABLE, reason, evidence, source="model")
        case ReplyVerdict.ISSUE_CHANGED:
            return Judgement(Verdict.ISSUE_CHANGED, reason, evidence, source="model")
        case ReplyVerdict.DISCARD if evidence:
            plan = facts.kind is PullKind.PLAN
            verdict = Verdict.DISCARD_PLAN if plan else Verdict.DISCARD_IMPLEMENTATION
            return Judgement(verdict, reason, evidence, source="model")
        case ReplyVerdict.DISCARD:
            reason = f"The model asked for a discard with no evidence in the diff: {reason}"
        case ReplyVerdict.NEEDS_FIX:
            pass
    return Judgement(Verdict.NEEDS_FIX, reason, evidence, _fix_of(facts, None), source="model")


# ── The call ─────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReviewCall:
    """One call of the step: what it read, how it may write, the verdicts of the pull request so
    far, and the login that last marked the pull request ready (`ready_by`)."""

    store: RoadmapStore
    repo: str
    pull: int
    status: PullStatus
    item: Item
    kind: PullKind
    mode: str
    writes: bool
    rounds: int
    ready_by: str | None = None

    def report(self, result: ReviewResult, reason: str, **fields: Any) -> ReviewReport:
        return ReviewReport(
            repo=self.repo,
            pull=self.pull,
            result=result,
            head=self.status.head_sha,
            kind=self.kind,
            rounds=self.rounds,
            reason=reason,
            **fields,
        )

    @property
    def text(self) -> str:
        """The hash of the issue text now."""
        return body_hashes(self.item.body)[0]

    @property
    def key(self) -> str:
        """The key of a verdict: the pull request, its head and the hash of the issue text."""
        return f"{self.pull}:{self.status.head_sha}:{self.text[:12]}"


def _rounds(item: Item, pull: int) -> int:
    """The verdicts that the record counts for `pull`; 0 for another pull request."""
    if item.job_record.get(ReviewRecordKey.PULL) != str(pull):
        return 0
    value = item.job_record.get(ReviewRecordKey.ROUNDS) or "0"
    return int(value) if value.isdigit() else 0


def _live_unit(item: Item) -> str | None:
    """The live unit that works on the item, as the watch row reads it: a runner Job
    (`job_holds`) or a stage Job (`stage.job`, #6024)."""
    if job_holds(item):
        return item.job_record.get(ImplementRecordKey.JOB)
    return item.job_record.get(StageRecordKey.JOB) or None


def _guard(
    store: RoadmapStore, repo: str, pull: int, status: PullStatus, head: str | None
) -> ReviewReport | Item:
    """The item of the open pull request, or the report of the guard that stops the call."""

    def stop(result: ReviewResult, reason: str) -> ReviewReport:
        return ReviewReport(repo, pull, result, head=status.head_sha, reason=reason)

    if head is not None and status.head_sha != head:
        return stop(ReviewResult.SKIPPED, "The head moved from the judged head.")
    if not is_bot_author(status.author):
        return stop(ReviewResult.STOPPED, "The author of the pull request is not a bot.")
    number = issue_of_branch(status.head_ref)
    item = store.item(number) if number is not None else None
    if item is None:
        return stop(ReviewResult.SKIPPED, "The branch names no item of the roadmap.")
    if unit := _live_unit(item):
        return stop(ReviewResult.SKIPPED, f"A live Job works on the item: `{unit}`.")
    # `owner/service` is the claim of the Service itself and holds nothing against its jobs.
    if claim_labels(status.labels) or claim_labels(item.labels):
        return stop(ReviewResult.STOPPED, "The item or the pull request holds an owner label.")
    return item


def _comment(call: ReviewCall, key: str, body: str) -> None:
    """Post or update the comment of the step for `key` on the pull request."""
    keyed = f"<!-- devops roadmap review: {key} -->"
    text = f"{CONST_ROADMAP_REVIEW_COMMENT_MARKER}\n{keyed}\n{body}"
    post(Target(call.repo, call.pull, client=get_github_session().client), keyed, None, text)


def _acts(judgement: Judgement) -> bool:
    """Whether the step carries out the discard itself: only a discard of a rule. A discard of the
    model alone gets its label and its comment, and a person decides the close (#6024)."""
    return judgement.verdict in _DISCARDS and judgement.source == "rule"


def _may_draft(call: ReviewCall) -> bool:
    """Whether the step may make the ready pull request a draft again: a bot marked it ready, or
    a bot opened it ready. A person who marked it ready decides (#6024)."""
    return is_bot_author(call.ready_by or call.status.author)


def _shares_branch(call: ReviewCall) -> bool:
    """Whether the branch of the pull request holds the work of the other kind too: a plan branch
    that the implement job builds on, or a delivery on the branch of its plan pull request. A
    delete of the branch would lose that work (#6024)."""
    record, branch = call.item.job_record, call.status.head_ref
    if call.kind is PullKind.PLAN:
        return (
            record.get(ImplementRecordKey.BRANCH) == branch
            or record_number(call.item, ImplementRecordKey.PR) == call.pull
        )
    return (
        record.get(StageRecordKey.BRANCH) == branch
        or record_number(call.item, StageRecordKey.PR) == call.pull
    )


def _back(call: ReviewCall) -> str:
    """The first words of the action of a verdict that sends the work back."""
    if call.status.draft:
        return ""
    if _may_draft(call):
        return _DRAFT_AGAIN
    return "a person marked the pull request ready, so it stays ready; "


def _planned(call: ReviewCall, judgement: Judgement) -> str:
    """The next action of the verdict, in words."""
    work = "a new plan" if call.kind is PullKind.PLAN else "a new implementation"
    match judgement.verdict:
        case Verdict.MERGEABLE:
            if call.status.draft:
                return "mark the draft ready for review; a person merges it"
            return "none: the pull request is ready for review; a person merges it"
        case Verdict.NEEDS_FIX:
            fix = judgement.due.value if judgement.due else "a fix by a person"
            return f"{_back(call)}the watch row starts {fix}"
        case Verdict.DISCARD_PLAN | Verdict.DISCARD_IMPLEMENTATION if _acts(judgement):
            return f"delete the branch, close the pull request and return the item for {work}"
        case Verdict.DISCARD_PLAN | Verdict.DISCARD_IMPLEMENTATION:
            return (
                "a person decides the discard: close the pull request and return the item for "
                f"{work}, or remove the label"
            )
        case Verdict.ISSUE_CHANGED:
            return f"{_back(call)}the work waits for an update to the issue or to the merged work"


def _verdict_text(call: ReviewCall, judgement: Judgement, label: str) -> str:
    limit = load_settings().roadmap.review.rounds
    lines = [
        f"**Verdict: {_VERDICT_NAMES[judgement.verdict]}** (`{label}`), review "
        f"{call.rounds + 1} of {limit} of this pull request, head {call.status.head_sha[:12]}.",
        "",
        f"Reason: {judgement.reason}",
    ]
    if judgement.evidence:
        lines += ["", "Evidence:", *(f"- {line}" for line in judgement.evidence)]
    lines += ["", f"Next step: {_planned(call, judgement)}."]
    return "\n".join(lines)


def _relabel(call: ReviewCall, label: str) -> None:
    """Add `label`, and remove the other verdict labels that only this step writes."""
    stale = tuple(name for name in call.status.labels if name in OWN_LABELS and name != label)
    if stale:
        remove_pull_labels(call.store, call.pull, stale)
    if label not in call.status.labels:
        add_pull_labels(call.store, call.pull, (label,))


def _return_item(
    store: RoadmapStore, repo: str, pull: int, number: int, kind: PullKind, *, verdict: str = ""
) -> PostedComment:
    """Return item `number` to New with the keys of its plan or its delivery and the keys of the
    step cleared, so the stage job plans it again or the implement job builds its plan again. The
    return comment holds `verdict`, the text of the verdict, when the call has it (#6194)."""
    plan = kind is PullKind.PLAN
    cleared: tuple[Any, ...] = STAGE_REMOVAL_KEYS if plan else _DELIVERY_KEYS
    marks: dict[Any, str | int | None] = dict.fromkeys((*cleared, *ReviewRecordKey))
    work = "a new plan" if plan else "a new implementation of its plan"
    comment = (
        f"{CONST_ROADMAP_REVIEW_COMMENT_MARKER}\nThe review discarded pull request #{pull}. The "
        f"item goes back to New for {work}."
    )
    if verdict:
        comment += f"\n\n{verdict}"
    return apply_return(store, plan_return(store, number, comment, repo, marks=marks))


def _discard(call: ReviewCall, withdraw: Withdraw, verdict: str) -> None:
    """Carry out a discard in an order that a later call can end (#6024): mark the start, delete
    the branch with a lease on the judged head, close the pull request, and return the item. A
    failed delete leaves the pull request open for the next call; after the delete, the next call
    ends the discard on the closed pull request. The return comment on the issue holds `verdict`,
    as the jobs and refine read the comments of the issue only. Then the comment of the step on
    the pull request, which held the verdict until now, becomes a link to it (#6194)."""
    head = call.status.head_sha
    call.store.set_marks(call.item, {ReviewRecordKey.DISCARD: f"{call.pull}:{head}"})
    withdraw(call.status.head_ref, head)
    get_github_session().client.close_pull(call.repo, call.pull)
    posted = _return_item(
        call.store, call.repo, call.pull, call.item.number, call.kind, verdict=verdict
    )
    _comment(
        call,
        head,
        f"The review discarded this pull request. The verdict is on #{call.item.number}: "
        f"{posted.url or call.item.url}.",
    )


def _finish_discard(
    store: RoadmapStore,
    repo: str,
    pull: int,
    status: PullStatus,
    *,
    writes: bool,
    withdraw: Withdraw | None,
) -> ReviewReport:
    """End a discard that this step started on the closed pull request `pull`: delete the branch
    if it is still there, and return the item. A closed pull request with no such mark is skipped."""
    skipped = ReviewReport(
        repo,
        pull,
        ReviewResult.SKIPPED,
        head=status.head_sha,
        reason="The pull request is closed or merged.",
    )
    number = issue_of_branch(status.head_ref)
    item = store.item(number) if number is not None else None
    mark = f"{pull}:{status.head_sha}"
    if status.merged or item is None or item.job_record.get(ReviewRecordKey.DISCARD) != mark:
        return skipped
    kind = pull_kind_of(item, pull, status.title)
    verdict = Verdict.DISCARD_PLAN if kind is PullKind.PLAN else Verdict.DISCARD_IMPLEMENTATION
    action = "delete the branch if it is there, and return the item"
    report = ReviewReport(repo, pull, ReviewResult.JUDGED, head=status.head_sha, kind=kind)
    if not writes:
        return replace(report, verdict=verdict, action=f"Plan: {action}")
    if withdraw is None:
        raise RoadmapImplementError(
            "The step review needs a withdraw to end a discard: the delete of the branch."
        )
    withdraw(status.head_ref, status.head_sha)
    _return_item(store, repo, pull, item.number, kind)
    return replace(report, verdict=verdict, action=action, written=True)


def _record(call: ReviewCall, judgement: Judgement) -> None:
    """Record the verdict: its pull request and round, its key, the verdict and its source, and
    the issue text that an Issue changed verdict answered."""
    marks: dict[Any, str | None] = {
        ReviewRecordKey.PULL: str(call.pull),
        ReviewRecordKey.ROUNDS: str(call.rounds + 1),
        ReviewRecordKey.KEY: call.key,
        ReviewRecordKey.VERDICT: judgement.verdict.value,
        ReviewRecordKey.SOURCE: judgement.source,
    }
    if judgement.verdict is Verdict.ISSUE_CHANGED:
        marks[ReviewRecordKey.TEXT] = call.text
    call.store.set_marks(call.item, marks)


def _log(
    call: ReviewCall, judgement: Judgement | None, failure: FailureClass | None = None
) -> None:
    """The result line of an attempt that judged or failed."""
    names = {"kind": call.kind.value, "mode": call.mode}
    if judgement is not None:
        names |= {"verdict": judgement.verdict.value, "source": judgement.source}
    model_calls = int(judgement.source == "model") if judgement else int(failure is not None)
    log_job_result(
        RoadmapJob.REVIEW,
        call.repo,
        call.item.number,
        (ReviewResult.JUDGED if judgement else ReviewResult.FAILED).value,
        failure=failure,
        counts={"round": call.rounds + 1, "model_calls": model_calls},
        names=names,
    )


def _judge(
    call: ReviewCall, facts: ReviewFacts, judge: ReviewJudge | None
) -> Judgement | ReviewReport:
    """The verdict of the model, or the report of a failed call."""
    if judge is None:
        from devops_cli.roadmap.steps.review_judge import GatewayReviewJudge

        judge = GatewayReviewJudge()
    case = read_case(call.repo, call.status, call.item, facts)
    try:
        reply = judge.judge(case)
    except RoadmapPullReviewLimitError as exc:
        _log(call, None, FailureClass.LIMIT_REACHED)
        return call.report(ReviewResult.FAILED, str(exc))
    except DevOpsCLIError as exc:
        _log(call, None, FailureClass.PROVIDER)
        return call.report(ReviewResult.FAILED, f"The model call failed: {mask_secrets(str(exc))}")
    return model_judgement(facts, reply)


def _capped(call: ReviewCall) -> ReviewReport:
    """The report of a pull request at the cap of verdicts, and its one comment."""
    reason = (
        f"The pull request has {call.rounds} verdicts, the most that `roadmap.review.rounds` "
        "allows. A person decides what it needs now."
    )
    if call.writes:
        _comment(call, "rounds", reason)
    return call.report(ReviewResult.CAPPED, reason, written=call.writes)


def _wait(call: ReviewCall, waiting: Waiting, now: datetime) -> ReviewReport:
    """A wait for the checks. A wait on CI infrastructure logs one line, and with writes it has a
    limit of `roadmap.review.infra_wait_hours` from the first wait of the head (#6024)."""
    if not waiting.infra:
        return call.report(ReviewResult.WAIT, waiting.reason)
    head = call.status.head_sha
    logger.info(
        "The review of %s#%d waits on CI infrastructure at head %s: %s",
        call.repo,
        call.pull,
        head[:12],
        waiting.reason,
    )
    if not call.writes:
        return call.report(ReviewResult.WAIT, waiting.reason)
    waited, _, since = (call.item.job_record.get(ReviewRecordKey.WAIT) or "").partition(" ")
    if waited != head or not since:
        call.store.set_marks(call.item, {ReviewRecordKey.WAIT: f"{head} {now.isoformat()}"})
        return call.report(ReviewResult.WAIT, waiting.reason)
    hours = load_settings().roadmap.review.infra_wait_hours
    if now - datetime.fromisoformat(since) < timedelta(hours=hours):
        return call.report(ReviewResult.WAIT, waiting.reason)
    reason = (
        f"{waiting.reason} The head {head[:12]} waited {hours} hours or more "
        "(`roadmap.review.infra_wait_hours`): a person runs the failed check again."
    )
    _comment(call, f"infra-{head}", reason)
    return call.report(ReviewResult.STOPPED, reason, written=True)


def write_verdict(
    call: ReviewCall, judgement: Judgement, *, withdraw: Withdraw | None = None
) -> ReviewReport:
    """Write the verdict of `call`: read the head again, check the discard before the first write,
    then comment, label, act and record."""
    now = get_github_session().client.get_pull_status(call.repo, call.pull)
    if now.head_sha != call.status.head_sha or now.state != "open":
        return call.report(
            ReviewResult.SKIPPED, "The head moved, or the pull request closed, after the read."
        )
    label = verdict_label(call.kind, judgement.verdict) or ""
    acts = _acts(judgement)
    if acts and _shares_branch(call):
        reason = (
            "The branch of this pull request holds the work of the plan and of its delivery, so a "
            f"person decides the discard. Reason of the review: {judgement.reason}"
        )
        _comment(call, "shared", reason)
        return call.report(ReviewResult.STOPPED, reason, verdict=judgement.verdict, written=True)
    if acts and withdraw is None:
        raise RoadmapImplementError(
            "The step review needs a withdraw to discard: the delete of the branch."
        )
    verdict = _verdict_text(call, judgement, label)
    _comment(call, call.status.head_sha, verdict)
    _relabel(call, label)
    if acts and withdraw is not None:
        _discard(call, withdraw, verdict)
    else:
        if judgement.verdict is Verdict.MERGEABLE and call.status.draft:
            draft = read_ready_draft(call.repo, call.pull, store=call.store, status=now)
            mark_ready(call.repo, call.pull, expected_head=call.status.head_sha, draft=draft)
        elif judgement.verdict in _BACK_TO_DRAFT and not call.status.draft and _may_draft(call):
            mark_draft(call.repo, call.pull, expected_head=call.status.head_sha)
        _record(call, judgement)
    return call.report(
        ReviewResult.JUDGED,
        judgement.reason,
        verdict=judgement.verdict,
        label=label,
        due=judgement.due,
        evidence=judgement.evidence,
        action=_planned(call, judgement),
        written=True,
    )


def _holds(call: ReviewCall, judgement: Judgement | None) -> bool:
    """Whether the head and the issue text already have this verdict: a rule verdict that the
    record and the label hold, or a verdict of the model, which only a new head or a new text asks
    again. The rules run on each call; only the model call is saved (#6024)."""
    record = call.item.job_record
    if record.get(ReviewRecordKey.KEY) != call.key:
        return False
    if judgement is None:
        return record.get(ReviewRecordKey.SOURCE) == "model"
    label = verdict_label(call.kind, judgement.verdict)
    return record.get(ReviewRecordKey.VERDICT) == judgement.verdict.value and (
        label in call.status.labels
    )


def run_review(
    store: RoadmapStore,
    repo: str,
    pull: int,
    *,
    head: str | None = None,
    confirm: bool = False,
    judge: ReviewJudge | None = None,
    withdraw: Withdraw | None = None,
    mode: RowMode | None = None,
    now: datetime | None = None,
) -> ReviewReport:
    """Give pull request `pull` of `repo` one verdict (#5969), as the module text says. The step
    writes only with `confirm` in the mode `on`, and a discard of a rule then needs `withdraw`."""
    settings = load_settings().roadmap.review
    mode = mode or settings.mode
    if mode == "off":
        return ReviewReport(repo, pull, ReviewResult.SKIPPED, reason="roadmap.review.mode is off.")
    writes = confirm and mode == "on"
    status = get_github_session().client.get_pull_status(repo, pull)
    if status.state != "open":
        return _finish_discard(store, repo, pull, status, writes=writes, withdraw=withdraw)
    guarded = _guard(store, repo, pull, status, head)
    if isinstance(guarded, ReviewReport):
        return guarded
    facts = read_facts(store, repo, pull, status, guarded)
    call = ReviewCall(
        store=store,
        repo=repo,
        pull=pull,
        status=status,
        item=guarded,
        kind=facts.kind,
        mode=mode,
        writes=writes,
        rounds=_rounds(guarded, pull),
        ready_by=facts.ready_by,
    )
    outcome = rule_judgement(facts)
    if isinstance(outcome, Waiting):
        return _wait(call, outcome, now or datetime.now(UTC))
    if _holds(call, outcome):
        return call.report(
            ReviewResult.SKIPPED, "This head and this issue text hold their verdict."
        )
    if call.rounds >= settings.rounds:
        return _capped(call)
    judged = outcome if outcome is not None else _judge(call, facts, judge)
    if isinstance(judged, ReviewReport):
        return judged
    _log(call, judged)
    if not call.writes:
        return call.report(
            ReviewResult.JUDGED,
            judged.reason,
            verdict=judged.verdict,
            label=verdict_label(call.kind, judged.verdict) or "",
            due=judged.due,
            evidence=judged.evidence,
            action=f"Plan: {_planned(call, judged)}",
        )
    return write_verdict(call, judged, withdraw=withdraw)


__all__ = [
    "OWN_LABELS",
    "DueFix",
    "Judgement",
    "ReviewCall",
    "ReviewJudge",
    "ReviewReport",
    "ReviewResult",
    "Waiting",
    "Withdraw",
    "model_judgement",
    "rule_judgement",
    "run_review",
    "write_verdict",
]
