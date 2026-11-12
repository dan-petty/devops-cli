"""`devops roadmap consolidate` (#3740): a plan of proposed groups of open items that share a
root cause.

The shortlists of `consolidate_shortlist.py` give the candidates. A judge (`consolidate_judge.py`)
proposes a group for each shortlist and tries to refute it. **A model verdict only flags.** The
run writes a local plan and no GitHub change: it never closes, merges, relabels or moves an item.
The only write is `decline_group`, one mark in the job record of the anchor of a group.

**Rules in code.** The judge's answer is cut down by `settle`, whatever the judge says:

- An anchor or a member outside the shortlist is dropped, and so is a started item (status In
  Progress or In Review) as a member. A started item is an anchor only for a `link-only` group.
- An item with a milestone is never merged, never made a child and never closed with its anchor.
  No job writes a milestone (the store has no method to set one), so a person set it. The item may
  be an anchor or a link.
- Only a kept group has a non-link action; a weakened group is `link-only`, and a dropped group
  is not in the plan. An action that the shape does not allow becomes `link`.
- A cited `#N` must be an issue of the repository, and a cited `path:line` a line of the file at
  the recorded commit. A citation that fails is dropped and recorded.

**Memory.** A group id follows the members (`group_id`). A decline stores the id in the job record
of the anchor. A group with an id that is declined, a group whose members all link to the anchor
already, and a member that a person reopened after a close as a duplicate of the anchor are not
proposed. The plan keeps the judgement of each shortlist under the hash of its case, so a rerun
over the same case makes no model call and marks its groups `carried`. Each judged shortlist is
saved to `<date>.progress.json` at once. The plan `<date>.json` is written when every shortlist is
done, so a gateway that does not answer leaves no plan and keeps the work.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.config.constants import (
    CONST_GH_ISSUE_STATE_REASON_REOPENED,
    CONST_ROADMAP_CONSOLIDATE_DIR,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_CONSOLIDATE_JUDGED,
    DEFAULT_ROADMAP_CONSOLIDATE_TEXT_CHARS,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.validation import ValidationError as InvalidInputError
from devops_cli.lang import MESSAGES
from devops_cli.output.file_writer import write_json_file
from devops_cli.roadmap.body_hash import text_of_a_person
from devops_cli.roadmap.consolidate_judge import (
    Action,
    CaseItem,
    CaseMember,
    Citation,
    Judgement,
    MemberVerdict,
    Refutation,
    Shape,
    ShortlistCase,
    ShortlistJudge,
)
from devops_cli.roadmap.consolidate_shortlist import (
    Member,
    Shortlist,
    Signal,
    consolidation_groups,
)
from devops_cli.roadmap.failure import FailureClass, StepName, failure_class_of
from devops_cli.roadmap.stores.store import (
    ChangeKind,
    CloseReason,
    ConsolidateRecordKey,
    GitHubState,
    IssueRecord,
    RoadmapStore,
)

logger = logging.getLogger(__name__)

_STARTED: Final[frozenset[str]] = frozenset(
    {CONST_ROADMAP_STATUS_IN_PROGRESS, CONST_ROADMAP_STATUS_IN_REVIEW}
)
# The actions a shape allows besides `link`.
_ALLOWED: Final[dict[Shape, frozenset[Action]]] = {
    Shape.MERGE: frozenset({Action.MERGE}),
    Shape.PARENT: frozenset({Action.CHILD}),
    Shape.CLOSE: frozenset({Action.CLOSE_WHEN_ANCHOR_MERGES}),
    Shape.LINK_ONLY: frozenset(),
}
_PLAN_FILE_PATTERN: Final[str] = "????-??-??.json"
_ID_HEX: Final[int] = 8


# ── The plan ──


class Source(Protocol):
    """The files of one commit of the repository: the edge of `git show <sha>:<path>`."""

    @property
    def sha(self) -> str | None:
        """The commit, once a file was read; None before."""

    def read(self, path: str) -> str | None:
        """The text of `path` at the commit, or None when there is no such file."""


class GitSource:
    """The files of `ref` in the clone `checkout` of `repo`, read with `git show <sha>:<path>`. The
    commit is resolved on the first read and recorded. A clone of another repository, a ref that
    does not resolve and a missing file all read as no file, so a cited path then fails."""

    def __init__(self, checkout: Path, repo: str, ref: str | None = None) -> None:
        self._checkout = checkout
        self._repo = repo
        self._ref = ref
        self._sha: str | None = None
        self._usable: bool | None = None

    @property
    def sha(self) -> str | None:
        return self._sha

    def _resolve(self) -> bool:
        from devops_cli.core.repo import get_repo_origin_name
        from devops_cli.exceptions import GitOperationError
        from devops_cli.roadmap.clone_git import default_branch, git

        if self._usable is None:
            operation = "roadmap.consolidate.source"
            origin = get_repo_origin_name(self._checkout)
            self._usable = origin is not None and origin.lower() == self._repo.lower()
            if self._usable:
                try:
                    ref = (
                        self._ref or f"origin/{default_branch(self._checkout, operation=operation)}"
                    )
                    self._sha = git(
                        self._checkout,
                        "rev-parse",
                        "--verify",
                        f"{ref}^{{commit}}",
                        operation=operation,
                    )
                except GitOperationError as exc:
                    logger.warning("The ref of the cited files does not resolve: %s", exc)
                    self._usable = False
            else:
                logger.warning(
                    "%s is no clone of %s, so cited files read as missing.",
                    self._checkout,
                    self._repo,
                )
        return self._usable

    def read(self, path: str) -> str | None:
        from devops_cli.exceptions import GitOperationError
        from devops_cli.roadmap.clone_git import git

        if not self._resolve():
            return None
        try:
            return git(
                self._checkout, "show", f"{self._sha}:{path}", operation="roadmap.consolidate.show"
            )
        except GitOperationError:
            return None


@dataclass(frozen=True)
class Edges:
    """What a run reaches beyond the store: the judge, the embedder and the files of the
    commit."""

    judge: ShortlistJudge
    embed: Callable[[Sequence[str]], list[list[float]]]
    source: Source


class GroupMember(BaseModel):
    """A member of a group: what a later apply does with it, why, and the evidence: what tools
    found, then what the judge cited and code confirmed."""

    model_config = ConfigDict(frozen=True)

    number: int
    action: Action
    reason: str
    evidence: tuple[str, ...] = ()


class Group(BaseModel):
    """A proposed group. `verdict` is that of the refutation (kept or weakened). `carried` says
    that the plan of an earlier run held the group too. `rejected` lists the citations that code
    dropped."""

    model_config = ConfigDict(frozen=True)

    id: str
    anchor: int
    shape: Shape
    theme: str
    root_cause: str
    members: tuple[GroupMember, ...]
    consistency_gained: str
    risks: tuple[str, ...] = ()
    confidence: float
    verdict: Refutation
    reasons: tuple[str, ...] = ()
    carried: bool = False
    rejected: tuple[str, ...] = ()


class PendingClose(BaseModel):
    """A member to close when its anchor merges: listed until the anchor is closed as completed."""

    model_config = ConfigDict(frozen=True)

    member: int
    anchor: int
    group: str


class Failure(BaseModel):
    """A shortlist that could not be judged: the step, the class of the failure and its text."""

    model_config = ConfigDict(frozen=True)

    anchor: int
    step: StepName
    failure_class: FailureClass
    error: str


class LeftOut(BaseModel):
    """A shortlist whose group is not in the plan, and why: the group id when there is one."""

    model_config = ConfigDict(frozen=True)

    anchor: int
    group: str | None = None
    reason: str


class Judged(BaseModel):
    """The judgement of one case, kept under the digest of the case."""

    model_config = ConfigDict(frozen=True)

    digest: str
    judgement: Judgement


class Plan(BaseModel):
    """The plan of a run. `judged` is the record of the model output; a dry run holds the
    requests of a run in `requests` and is no file."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    repo: str
    day: date
    sha: str | None = None
    groups: tuple[Group, ...] = ()
    pending_closes: tuple[PendingClose, ...] = ()
    failures: tuple[Failure, ...] = ()
    left_out: tuple[LeftOut, ...] = ()
    judged: tuple[Judged, ...] = ()
    unjudged: int = 0
    dry_run: bool = Field(default=False, exclude=True)
    requests: tuple[PlannedRequest, ...] = Field(default=(), exclude=True)
    write_requests: tuple[PlannedRequest, ...] = Field(default=(), exclude=True)

    @property
    def new_groups(self) -> tuple[Group, ...]:
        """The groups that no earlier plan held."""
        return tuple(group for group in self.groups if not group.carried)


class _Progress(BaseModel):
    """The judgements of the shortlists done so far in a run that is not finished."""

    repo: str
    judged: tuple[Judged, ...] = ()


def group_id(anchor: int, members: Iterable[int]) -> str:
    """The id of a group: its anchor and a hash of its members, so that a change of members is a
    new group."""
    joined = ",".join(str(number) for number in sorted(members))
    return f"g{anchor}-{hashlib.sha256(joined.encode()).hexdigest()[:_ID_HEX]}"


def plan_path(directory: Path, day: date) -> Path:
    """The plan of `day` in the data directory `directory`."""
    return directory / CONST_ROADMAP_CONSOLIDATE_DIR / f"{day.isoformat()}.json"


def _progress_path(directory: Path, day: date) -> Path:
    return directory / CONST_ROADMAP_CONSOLIDATE_DIR / f"{day.isoformat()}.progress.json"


def read_plan(path: Path) -> Plan:
    """The plan in `path`. A file that is no plan raises `pydantic.ValidationError`."""
    return Plan.model_validate_json(path.read_text(encoding="utf-8"))


def _last_plan(directory: Path, repo: str) -> Plan | None:
    """The newest plan of `repo` that the data directory holds, or None. A file that can't be
    read is logged and skipped."""
    folder = directory / CONST_ROADMAP_CONSOLIDATE_DIR
    for path in sorted(folder.glob(_PLAN_FILE_PATTERN), reverse=True):
        try:
            plan = read_plan(path)
        except (OSError, ValidationError) as exc:
            logger.warning("The plan %s can't be read, so it is skipped: %s", path, exc)
            continue
        if plan.repo == repo:
            return plan
    return None


def _progress(directory: Path, day: date, repo: str) -> tuple[Judged, ...]:
    path = _progress_path(directory, day)
    if not path.is_file():
        return ()
    try:
        held = _Progress.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        logger.warning("The progress file %s can't be read, so it is skipped: %s", path, exc)
        return ()
    return held.judged if held.repo == repo else ()


def _write(path: Path, model: BaseModel) -> None:
    write_json_file(path, model.model_dump(mode="json"), atomic=True)


# ── The board ──


@dataclass(frozen=True)
class _Board:
    """What the rules read of the repository: the issues, the started items, and the issues with
    a milestone, which a person set."""

    issues: dict[int, IssueRecord]
    started: frozenset[int]
    planned: frozenset[int]


def _was_reopened(store: RoadmapStore, board: _Board, member: int, anchor: int) -> bool:
    """Whether someone reopened `member` after a close as a duplicate of `anchor`. A close as a
    duplicate that names no issue counts for every anchor. Only an issue that GitHub marks as
    reopened reads its timeline."""
    if board.issues[member].state_reason != CONST_GH_ISSUE_STATE_REASON_REOPENED:
        return False
    closed = False
    for closure in store.closures(member):
        if closure.kind is ChangeKind.CLOSED:
            closed = closure.reason == CloseReason.DUPLICATE.value and closure.duplicate_of in (
                None,
                anchor,
            )
        elif closure.kind is ChangeKind.REOPENED and closed:
            return True
    return False


def _tool_evidence(member: Member) -> tuple[str, ...]:
    return tuple(f"{e.signal.value}: {e.detail}" for e in member.evidence)


def _linked(member: Member) -> bool:
    return any(e.signal is Signal.LINK for e in member.evidence)


def _item(issue: IssueRecord) -> CaseItem:
    text = text_of_a_person(issue.body)[:DEFAULT_ROADMAP_CONSOLIDATE_TEXT_CHARS]
    return CaseItem(number=issue.number, title=issue.title, text=text)


def _case(shortlist: Shortlist, kept: Sequence[Member], board: _Board) -> ShortlistCase:
    members = tuple(
        CaseMember(
            **_item(board.issues[m.number]).model_dump(),
            evidence=_tool_evidence(m),
            protected=m.number in board.planned,
        )
        for m in kept
    )
    return ShortlistCase(
        anchor=_item(board.issues[shortlist.anchor]),
        members=members,
        anchor_started=shortlist.anchor in board.started,
    )


# ── The rules ──


def _citation_holds(citation: Citation, board: _Board, source: Source) -> bool:
    if citation.issue is not None:
        return citation.issue in board.issues
    path = citation.path or ""
    if path.startswith("/") or ".." in path.split("/"):
        return False
    text = source.read(path)
    return text is not None and 1 <= (citation.line or 0) <= len(text.splitlines())


def _action(verdict: MemberVerdict, shape: Shape, *, link_only: bool, protected: bool) -> Action:
    """The action of a member after the rules: a link when the group is link-only, when the shape
    does not allow the action, or when the item has a milestone."""
    if link_only or verdict.action not in _ALLOWED[shape] or protected:
        return Action.LINK
    return verdict.action


def _settle(
    shortlist: Shortlist,
    kept: Sequence[Member],
    judgement: Judgement,
    board: _Board,
    source: Source,
) -> Group | None:
    """The group that the rules leave of `judgement`, or None. `kept` are the members of the
    shortlist that the judge saw."""
    anchor = judgement.anchor
    allowed = {shortlist.anchor, *(m.number for m in kept)}
    if judgement.verdict is Refutation.DROPPED or anchor not in allowed:
        return None
    tools = {m.number: _tool_evidence(m) for m in kept}
    link_only = (
        judgement.verdict is Refutation.WEAKENED
        or judgement.shape is Shape.LINK_ONLY
        or anchor in board.started
    )
    members: dict[int, GroupMember] = {}
    rejected: list[str] = []
    for verdict in judgement.members:
        number = verdict.number
        if number == anchor or number not in allowed or number in members:
            continue
        if number in board.started:
            continue
        cited: list[str] = []
        for citation in verdict.citations:
            if _citation_holds(citation, board, source):
                cited.append(citation.text)
            else:
                rejected.append(
                    MESSAGES.roadmap.consolidate_rejected.format(text=citation.text, member=number)
                )
        action = _action(
            verdict, judgement.shape, link_only=link_only, protected=number in board.planned
        )
        members[number] = GroupMember(
            number=number,
            action=action,
            reason=verdict.reason,
            evidence=(*tools.get(number, ()), *cited),
        )
    if not members:
        return None
    shaped = (
        judgement.shape
        if any(m.action is not Action.LINK for m in members.values())
        else Shape.LINK_ONLY
    )
    return Group(
        id=group_id(anchor, members),
        anchor=anchor,
        shape=shaped,
        theme=judgement.theme,
        root_cause=judgement.root_cause,
        members=tuple(members[n] for n in sorted(members)),
        consistency_gained=judgement.consistency_gained,
        risks=judgement.risks,
        confidence=judgement.confidence,
        verdict=judgement.verdict,
        reasons=judgement.reasons,
        rejected=tuple(rejected),
    )


def _all_linked(shortlist: Shortlist, group: Group) -> bool:
    """Whether every member of `group` links to the anchor already, by the evidence of tools."""
    if group.anchor != shortlist.anchor:
        return False
    linked = {m.number for m in shortlist.members if _linked(m)}
    return all(member.number in linked for member in group.members)


# ── The run ──


def _order(lists: Sequence[Shortlist]) -> list[Shortlist]:
    """The shortlists with the strongest evidence first, so a limit keeps the likeliest groups."""
    return sorted(
        lists, key=lambda s: (tuple(-w for w in max(m.weight for m in s.members)), s.anchor)
    )


def _declined(record: str | None) -> frozenset[str]:
    return frozenset(part for part in (record or "").split(",") if part)


def _pending(
    groups: Sequence[Group], earlier: Plan | None, board: _Board
) -> tuple[PendingClose, ...]:
    """The closes that wait for an anchor: those of the groups, and those of the earlier plan whose
    anchor is open and whose member is open."""
    found: dict[tuple[int, int], PendingClose] = {}
    for group in groups:
        for member in group.members:
            if member.action is Action.CLOSE_WHEN_ANCHOR_MERGES:
                found[member.number, group.anchor] = PendingClose(
                    member=member.number, anchor=group.anchor, group=group.id
                )
    for held in earlier.pending_closes if earlier is not None else ():
        anchor_issue = board.issues.get(held.anchor)
        member_issue = board.issues.get(held.member)
        if (
            anchor_issue is not None
            and member_issue is not None
            and anchor_issue.state is GitHubState.OPEN
            and member_issue.state is GitHubState.OPEN
        ):
            found.setdefault((held.member, held.anchor), held)
    return tuple(found[key] for key in sorted(found))


def run_consolidate(
    store: RoadmapStore,
    edges: Edges,
    *,
    repo: str,
    directory: Path,
    today: date,
    limit: int | None = None,
) -> Plan:
    """Judge the shortlists of the open items and write the plan. It writes no GitHub change.

    At most `limit` shortlists (`DEFAULT_ROADMAP_CONSOLIDATE_JUDGED` by default) go to the judge;
    one whose case was judged before costs no call and does not count. The progress file holds each
    judgement as soon as it is made; the plan file is written when the run ends. A judge that
    raises `ModelGatewayUnreachableError` ends the run with no plan.
    """
    texts = MESSAGES.roadmap
    cap = DEFAULT_ROADMAP_CONSOLIDATE_JUDGED if limit is None else limit
    lists = consolidation_groups(store, edges.embed)
    items = {item.number: item for item in store.open_items()}
    issues = {issue.number: issue for issue in store.issues()}
    board = _Board(
        issues=issues,
        started=frozenset(n for n, item in items.items() if item.status in _STARTED),
        planned=frozenset(n for n, issue in issues.items() if issue.milestone),
    )
    earlier = _last_plan(directory, repo)
    remembered = {
        judged.digest: judged
        for judged in (*(earlier.judged if earlier else ()), *_progress(directory, today, repo))
    }
    previous = {group.id for group in earlier.groups} if earlier else set()

    used: dict[str, Judged] = {}
    groups: list[Group] = []
    failures: list[Failure] = []
    left_out: list[LeftOut] = []
    unjudged = calls = 0
    for shortlist in _order(lists):
        kept = [
            m
            for m in shortlist.members
            if m.number not in board.started
            and not _was_reopened(store, board, m.number, shortlist.anchor)
        ]
        if not kept:
            continue
        if all(_linked(m) for m in kept):
            left_out.append(LeftOut(anchor=shortlist.anchor, reason=texts.consolidate_left_linked))
            continue
        case = _case(shortlist, kept, board)
        found = remembered.get(case.digest)
        if found is None:
            if calls >= cap:
                unjudged += 1
                continue
            calls += 1
            try:
                judgement = edges.judge.judge(case)
            except StructuredOutputValidationError as exc:
                failures.append(
                    Failure(
                        anchor=shortlist.anchor,
                        step=StepName.JUDGE,
                        failure_class=failure_class_of(exc),
                        error=str(exc)[:300],
                    )
                )
                continue
            found = Judged(digest=case.digest, judgement=judgement)
            remembered[case.digest] = found
            used[case.digest] = found
            _write(
                _progress_path(directory, today),
                _Progress(repo=repo, judged=tuple(remembered.values())),
            )
        used[case.digest] = found
        group = _settle(shortlist, kept, found.judgement, board, edges.source)
        if group is None:
            dropped = found.judgement.verdict is Refutation.DROPPED
            reason = texts.consolidate_left_refuted if dropped else texts.consolidate_left_rules
            left_out.append(LeftOut(anchor=shortlist.anchor, reason=reason))
            continue
        declined = _declined(items[group.anchor].job_record.get(ConsolidateRecordKey.DECLINED))
        if _all_linked(shortlist, group) or group.id in declined:
            reason = (
                texts.consolidate_left_declined
                if group.id in declined
                else texts.consolidate_left_linked
            )
            left_out.append(LeftOut(anchor=group.anchor, group=group.id, reason=reason))
            continue
        groups.append(group.model_copy(update={"carried": group.id in previous}))

    plan = Plan(
        repo=repo,
        day=today,
        sha=edges.source.sha,
        groups=tuple(groups),
        pending_closes=_pending(groups, earlier, board),
        failures=tuple(failures),
        left_out=tuple(left_out),
        judged=tuple(used.values()),
        unjudged=unjudged,
    )
    _write(plan_path(directory, today), plan)
    _progress_path(directory, today).unlink(missing_ok=True)
    return plan


# ── Decline ──


@dataclass(frozen=True)
class Decline:
    """A decline: the group, its anchor, and whether the job record was written."""

    group: str
    anchor: int
    written: bool


def decline_group(
    store: RoadmapStore, group: str, *, repo: str, directory: Path, confirm: bool
) -> Decline:
    """Record that a person declined `group` of the last plan, in the job record of its anchor.
    With no `confirm` it writes nothing. This is the only write of the job."""
    plan = _last_plan(directory, repo)
    found = next((g for g in plan.groups if g.id == group), None) if plan else None
    if found is None:
        raise InvalidInputError(
            MESSAGES.roadmap.consolidate_decline_unknown.format(group=group), field="decline"
        )
    item = store.item(found.anchor)
    if item is None:
        raise InvalidInputError(
            MESSAGES.roadmap.consolidate_decline_no_item.format(anchor=found.anchor),
            field="decline",
        )
    if confirm:
        held = _declined(item.job_record.get(ConsolidateRecordKey.DECLINED))
        store.set_marks(item, {ConsolidateRecordKey.DECLINED: ",".join(sorted({*held, group}))})
    return Decline(group=group, anchor=found.anchor, written=confirm)


# ── Dry run and output ──


def dry_run_consolidate(
    repo: str, *, today: date, limit: int | None = None, decline: str | None = None
) -> Plan:
    """The plan a dry run returns, having made no request."""
    from devops_cli.roadmap.request_plan import consolidate_requests

    reads, writes = consolidate_requests(repo, limit=limit, decline=decline)
    return Plan(repo=repo, day=today, dry_run=True, requests=reads, write_requests=writes)


def render_plan(plan: Plan) -> str:
    """The summary of a plan: each group with its members and actions, the pending closes, the
    failures, and the counts."""
    texts = MESSAGES.roadmap
    lines = [texts.consolidate_title.format(repo=plan.repo, day=plan.day.isoformat())]
    if not plan.groups:
        lines.append(texts.consolidate_none)
    for group in plan.groups:
        lines.append(
            texts.consolidate_group.format(
                id=group.id,
                shape=group.shape.value,
                anchor=group.anchor,
                verdict=group.verdict.value,
                confidence=group.confidence,
                theme=group.theme,
                status=texts.consolidate_carried if group.carried else texts.consolidate_new,
            )
        )
        lines.append(texts.consolidate_cause.format(cause=group.root_cause))
        lines += [
            texts.consolidate_member.format(number=m.number, action=m.action.value, reason=m.reason)
            for m in group.members
        ]
        lines += [texts.consolidate_rejection.format(text=text) for text in group.rejected]
    if plan.pending_closes:
        lines.append(texts.consolidate_pending_heading)
        lines += [
            texts.consolidate_pending.format(member=p.member, anchor=p.anchor)
            for p in plan.pending_closes
        ]
    if plan.left_out:
        lines.append(texts.consolidate_left_heading)
        lines += [
            texts.consolidate_left.format(
                anchor=o.anchor, group=f" {o.group}" if o.group else "", reason=o.reason
            )
            for o in plan.left_out
        ]
    if plan.failures:
        lines.append(texts.consolidate_failures_heading)
        lines += [
            texts.consolidate_failure.format(
                anchor=f.anchor, step=f.step.value, klass=f.failure_class.value, error=f.error
            )
            for f in plan.failures
        ]
    lines.append(
        texts.consolidate_counts.format(
            groups=len(plan.groups), new=len(plan.new_groups), unjudged=plan.unjudged
        )
    )
    return "\n".join(lines)


__all__ = [
    "Decline",
    "Edges",
    "Failure",
    "GitSource",
    "Group",
    "GroupMember",
    "Judged",
    "LeftOut",
    "PendingClose",
    "Plan",
    "Source",
    "decline_group",
    "dry_run_consolidate",
    "group_id",
    "plan_path",
    "read_plan",
    "render_plan",
    "run_consolidate",
]
