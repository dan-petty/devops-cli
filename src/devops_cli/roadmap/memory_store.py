"""The in-memory roadmap store: the roadmap held in process, with no I/O, for tests.

It keeps the promises the GitHub adapter keeps, so the contract suite runs against it. A test
seeds milestones with `seed_milestone`, issues with `seed_issue`, pull requests with `seed_pull`
and labels with `seed_label`, and acts as a person with
`as_actor`: a person's writes change labels and record changes under their name, but never
touch the job record. Each issue keeps its body as GitHub does, the record block included, and
every read takes the block out with the same rules as the GitHub adapter.

A person also labels, unlabels, closes and reopens issues through the helpers below; each
records the change a poll would find. Every write to an issue, a comment included, moves its
`updated_at`, as on GitHub. `seed_evidence` makes a piece of evidence one GitHub confirms, and
`seed_commit` a commit on the default branch that changed a path. Every write the store makes
as a job, not as a person, is kept in `job_writes`, so a test can check what a job wrote and
that a preview wrote nothing.

A job's write of a field compares the issue's value with the value the store last wrote to
that field, else with the value of the Item the caller passes, as the GitHub adapter does: a
person's change since raises before anything changes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from devops_cli.config.constants import CONST_GH_ISSUE_STATE_REASON_REOPENED
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_MEMORY_ACTOR,
    DEFAULT_ROADMAP_MEMORY_AUTHOR_ASSOCIATION,
    DEFAULT_ROADMAP_MEMORY_REPO,
)
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.roadmap.store import (
    Candidate,
    Change,
    ChangeKind,
    CloseReason,
    Closure,
    Evidence,
    GitHubState,
    IssueComment,
    IssueRecord,
    Item,
    ItemField,
    Milestone,
    OpenPull,
    RepositoryFacts,
    RepositoryLabel,
    RoadmapStore,
    already_closed,
    as_utc,
    decode_job_record,
    encode_job_record,
    field_label,
    find_milestone,
    item_of,
    milestone_edits,
    milestone_order,
    relabeled,
    require_milestone,
    require_unchanged,
    require_value,
    select_candidates,
    select_items,
    split_record,
    with_record,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class JobWrite:
    """One write the store made as a job: the operation, the issue or milestone it touched, and
    the field or mark it set with its value."""

    operation: str
    number: int | None = None
    key: str | None = None
    value: str | None = None


@dataclass
class _Roadmap:
    """The state every view of one in-memory roadmap shares. Each issue's body is held as
    GitHub holds it, its record block included."""

    repo: str
    clock: Callable[[], datetime]
    milestones: dict[int, Milestone] = field(default_factory=dict)
    issues: dict[int, IssueRecord] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)
    comments: dict[int, list[IssueComment]] = field(default_factory=dict)
    files: dict[tuple[str, str | None], str] = field(default_factory=dict)
    # When each commit on the default branch that changed a path was made, by path.
    commits: dict[str, list[datetime]] = field(default_factory=dict)
    closures: dict[int, list[Closure]] = field(default_factory=dict)
    evidence: set[Evidence] = field(default_factory=set)
    job_writes: list[JobWrite] = field(default_factory=list)
    is_private: bool = False
    # The repositories `seed_repository` made, by full name.
    repositories: dict[str, RepositoryFacts] = field(default_factory=dict)
    # The head branch and draft state of each pull request `seed_pull` made, by number.
    pulls: dict[int, tuple[str, bool]] = field(default_factory=dict)
    labels: list[RepositoryLabel] = field(default_factory=list)


class InMemoryRoadmapStore(RoadmapStore):
    """The roadmap in memory: milestones, issues and pull requests, and their labels."""

    def __init__(
        self,
        *,
        is_private: bool = False,
        repo: str = DEFAULT_ROADMAP_MEMORY_REPO,
        actor: str = DEFAULT_ROADMAP_MEMORY_ACTOR,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._roadmap = _Roadmap(repo=repo, clock=clock, is_private=is_private)
        self._actor = actor
        self._writes_job_record = True
        # The value this view last wrote to each field of each issue.
        self._written: dict[tuple[int, ItemField], str | None] = {}

    def as_actor(self, actor: str) -> InMemoryRoadmapStore:
        """The same roadmap, written by a person: changes carry their name, and no job record."""
        person = InMemoryRoadmapStore(actor=actor)
        person._roadmap, person._writes_job_record = self._roadmap, False
        return person

    # ── Seeding ──

    def seed_milestone(
        self,
        title: str,
        *,
        description: str = "",
        due_on: date | None = None,
        state: GitHubState = GitHubState.OPEN,
    ) -> Milestone:
        """Create a milestone as a person does on GitHub, returning it; the next number names it."""
        number = max(self._roadmap.milestones, default=0) + 1
        closed_at = self._roadmap.clock() if state is GitHubState.CLOSED else None
        self._roadmap.milestones[number] = Milestone(
            number=number,
            title=title,
            description=description,
            state=state,
            due_on=due_on,
            closed_at=closed_at,
        )
        return self._counted(self._roadmap.milestones[number])

    def seed_issue(
        self,
        title: str,
        *,
        body: str = "",
        state: GitHubState = GitHubState.OPEN,
        state_reason: str | None = None,
        labels: Iterable[str] = (),
        fields: Mapping[ItemField, str] | None = None,
        milestone: str | None = None,
        pull_request: bool = False,
        author_association: str | None = DEFAULT_ROADMAP_MEMORY_AUTHOR_ASSOCIATION,
        sub_issues: int = 0,
        parent: int | None = None,
        updated_at: datetime | None = None,
    ) -> int:
        """Open an issue (or a pull request) as GitHub would, returning its number.

        `fields` adds the label of each field's value to `labels`, as a person sets them, with
        no job record; a Priority makes the issue an Item. `milestone` is the title of a seeded
        milestone. Seeding records no change. `author_association` is the author's relation to
        the repository, the owner's unless given, since GitHub gives one for every issue.
        `sub_issues` is how many sub-issues GitHub records for it, and `parent` is the issue
        that has it as a sub-issue. The issue is created now by the store's clock, and closed
        now when seeded closed, and last changed at `updated_at` when that is given. `body` is
        kept as given, so a test can seed a record block.
        """
        if milestone is not None:
            require_milestone(self._roadmap.milestones.values(), milestone, "roadmap.issue.seed")
        number = len(self._roadmap.issues) + 1
        kind = "pull" if pull_request else "issues"
        now = self._roadmap.clock()
        given = (*labels, *(field_label(f, value) for f, value in (fields or {}).items()))
        self._roadmap.issues[number] = IssueRecord(
            id=number,
            number=number,
            title=title,
            url=f"https://github.com/{self._roadmap.repo}/{kind}/{number}",
            body=body,
            state=state,
            state_reason=state_reason,
            labels=given,
            milestone=milestone,
            pull_request=pull_request,
            author_association=author_association,
            created_at=now,
            updated_at=as_utc(updated_at) if updated_at is not None else now,
            closed_at=now if state is GitHubState.CLOSED else None,
            sub_issues=sub_issues,
            parent=parent,
        )
        return number

    def seed_pull(
        self,
        title: str,
        *,
        head_ref: str,
        draft: bool = False,
        state: GitHubState = GitHubState.OPEN,
        updated_at: datetime | None = None,
    ) -> int:
        """Open a pull request on the branch `head_ref`, a draft when `draft`, returning its
        number. It is an issue that is a pull request, so it shares the numbers of the issues."""
        number = self.seed_issue(title, state=state, pull_request=True, updated_at=updated_at)
        self._roadmap.pulls[number] = (head_ref, draft)
        return number

    def seed_label(self, name: str, color: str, description: str = "") -> None:
        """Add a label to the repository, as a person does on GitHub."""
        self._roadmap.labels.append(
            RepositoryLabel(name=name, color=color, description=description)
        )

    def seed_file(self, path: str, text: str, *, ref: str | None = None) -> None:
        """Commit `text` at `path` on `ref`, or on the default branch when `ref` is None."""
        self._roadmap.files[(path, ref)] = text

    def seed_visibility(self, *, is_private: bool) -> None:
        """Set whether the repository is private."""
        self._roadmap.is_private = is_private

    def seed_commit(self, path: str, *, at: datetime) -> None:
        """Record a commit on the default branch, made at `at`, that changed `path`."""
        self._roadmap.commits.setdefault(path, []).append(as_utc(at))

    def seed_repository(self, facts: RepositoryFacts) -> None:
        """Make the repository `facts` describe, which GitHub knows."""
        self._roadmap.repositories[facts.full_name] = facts

    def raw_body(self, number: int) -> str:
        """Issue `number`'s body as GitHub holds it, its record block included."""
        return self._require_issue(number, "roadmap.issue.read_body").body

    def job_writes(self) -> list[JobWrite]:
        """Every write the store made as a job, oldest first; a person's writes are not kept."""
        return list(self._roadmap.job_writes)

    # ── What a person does on GitHub ──

    def add_label(self, number: int, label: str) -> None:
        """Label issue `number`, as a person does on GitHub; a label it holds stays one."""
        issue = self._require_issue(number, "roadmap.issue.label")
        if label not in issue.labels:
            self._relabel(issue, (*issue.labels, label))

    def remove_label(self, number: int, label: str) -> None:
        """Take `label` off issue `number`, as a person does on GitHub."""
        issue = self._require_issue(number, "roadmap.issue.unlabel")
        self._relabel(issue, tuple(held for held in issue.labels if held != label))

    def reopen_issue(self, number: int) -> None:
        """Reopen a closed issue, as a person does on GitHub."""
        issue = self._require_issue(number, "roadmap.issue.reopen")
        if issue.state is GitHubState.CLOSED:
            self._update_issue(
                issue,
                state=GitHubState.OPEN,
                state_reason=CONST_GH_ISSUE_STATE_REASON_REOPENED,
                closed_at=None,
            )
            self._closure(number, ChangeKind.REOPENED)
            self._record(ChangeKind.REOPENED, number)

    def close_by_hand(self, number: int, reason: CloseReason) -> None:
        """Close an issue without a comment, as a person's bulk close does on GitHub."""
        self._close(self._require_issue(number, "roadmap.issue.close"), reason)

    def move_by_hand(self, number: int, milestone: str | None) -> None:
        """Put issue `number` in the milestone `milestone` names, or in none, as a person does."""
        issue = self._require_issue(number, "roadmap.issue.milestone")
        target = (
            None
            if milestone is None
            else require_milestone(self.milestones(), milestone, "roadmap.issue.milestone").title
        )
        self._update_issue(issue, milestone=target)

    def edit_body_by_hand(self, number: int, body: str) -> None:
        """Write `body` as the whole body of issue `number`, as a person does in GitHub's editor,
        which shows the record block as text."""
        self._update_issue(self._require_issue(number, "roadmap.issue.edit"), body=body)

    def seed_evidence(self, evidence: Evidence) -> None:
        """Make `evidence` one GitHub confirms: the advisory, failed run or commit exists."""
        self._roadmap.evidence.add(evidence)

    # ── Milestones ──

    def milestones(self) -> list[Milestone]:
        """Every milestone, open and closed, by due date and then by number."""
        counted = (self._counted(milestone) for milestone in self._roadmap.milestones.values())
        return sorted(counted, key=milestone_order)

    def milestone(self, name: str) -> Milestone | None:
        """The milestone with the exact title `name`, else the one numbered `name`, or None."""
        return find_milestone(self.milestones(), name)

    def edit_milestone(
        self,
        name: str,
        *,
        title: str | None = None,
        description: str | None = None,
        due_on: date | None = None,
        state: GitHubState | None = None,
    ) -> Milestone:
        """Change only the given fields of the milestone `name` names, raising if there is none.

        A new title is the one its issues show from then on: GitHub keeps a milestone by its
        number, so a rename moves nothing.
        """
        milestones = self.milestones()
        current = require_milestone(milestones, name, "roadmap.milestone.edit")
        edits = milestone_edits(
            milestones, current, title=title, description=description, due_on=due_on, state=state
        )
        edited = current.model_copy(update=edits | self._closed_at(current, edits.get("state")))
        self._roadmap.milestones[current.number] = edited
        if edited.title != current.title:
            self._retitle(current.title, edited.title)
        self._log("edit_milestone", current.number, value=str(edits.get("state") or "") or None)
        return self._counted(edited)

    def close_milestone(self, name: str) -> Milestone:
        """Close the milestone `name` names, raising if there is none."""
        return self.edit_milestone(name, state=GitHubState.CLOSED)

    # ── Issues ──

    def issues(self) -> list[IssueRecord]:
        """Every issue, open and closed, Item or not; never pull requests."""
        return [
            self._read(issue) for issue in self._roadmap.issues.values() if not issue.pull_request
        ]

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""
        number = self.seed_issue(title, body=body, labels=labels)
        self._log("create_issue", number, value=title)
        return self._read(self._roadmap.issues[number])

    def add_sub_issue(self, parent: int, child: int) -> None:
        """Add issue `child` as a sub-issue of issue `parent`."""
        parent_issue = self._require_issue(parent, "roadmap.add_sub_issue")
        child_issue = self._require_issue(child, "roadmap.add_sub_issue")
        self._update_issue(parent_issue, sub_issues=parent_issue.sub_issues + 1)
        self._update_issue(child_issue, parent=parent)
        self._log("add_sub_issue", parent, value=str(child))

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number`, oldest first."""
        return list(self._roadmap.closures.get(number, []))

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue or pull request `number`, keeping its other labels; a label it
        holds stays one. GitHub labels a pull request through the issues endpoint (#2748)."""
        issue = self._require_issue(number, "roadmap.issue.label", pull_request=True)
        if label not in issue.labels:
            self._relabel(issue, (*issue.labels, label))
        self._log("label_issue", number, value=label)

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether the evidence was seeded as one GitHub confirms."""
        return evidence in self._roadmap.evidence

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""
        issue = self._require_issue(number, "roadmap.issue.comment")
        self._update_issue(issue)
        made = IssueComment(body=body, created_at=as_utc(self._roadmap.clock()))
        self._roadmap.comments.setdefault(number, []).append(made)
        self._log("comment", number, value=body)

    def seed_comment(
        self, number: int, body: str, *, author_association: str | None = None
    ) -> None:
        """Add a comment as another commenter made it, with their relation to the repository,
        as GitHub gives it. Seeding records no change and no write."""
        self._require_issue(number, "roadmap.issue.seed_comment")
        made = IssueComment(
            body=body,
            created_at=as_utc(self._roadmap.clock()),
            author_association=author_association,
        )
        self._roadmap.comments.setdefault(number, []).append(made)

    def comments_on(self, number: int) -> list[IssueComment]:
        """Every comment on issue `number`, oldest first."""
        return list(self._roadmap.comments.get(number, []))

    def close(self, number: int, reason: CloseReason, *, comment: str | None = None) -> None:
        """Post `comment` on issue `number` when given, then close it for `reason`. A pull
        request, a missing issue and a closed issue are refused before any write."""
        issue = self._require_issue(number, "roadmap.issue.close")
        if issue.state is GitHubState.CLOSED:
            raise already_closed(number, {"number": number})
        if comment is not None:
            self.comment(number, comment)
        self._close(self._roadmap.issues[number], reason)
        self._log("close", number, value=reason.value)

    def path_changed_at(self, path: str) -> datetime | None:
        """When the newest commit `seed_commit` recorded for `path` was made, or None."""
        return max(self._roadmap.commits.get(path, []), default=None)

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The text committed at `path` on `ref`, raising when there is none."""
        text = self._roadmap.files.get((path, ref))
        if text is None:
            raise GitHubFileNotFoundError(
                f"{self._roadmap.repo} has no {path} on {ref or 'its default branch'}.",
                operation="roadmap.read",
                details={"path": path[:256], "ref": (ref or "")[:256]},
            )
        return text

    def repository_is_private(self) -> bool:
        """Whether the repository is private."""
        return self._roadmap.is_private

    def repository_facts(self, full_name: str) -> RepositoryFacts | None:
        """The facts `seed_repository` gave for `full_name`, or None."""
        return self._roadmap.repositories.get(full_name)

    def read_issue_body(self, number: int) -> str:
        """The body of issue `number`, with no record block, raising if it is not an issue of
        this repository."""
        return self._read(self._require_issue(number, "roadmap.issue.read_body")).body

    def write_issue_body(self, number: int, body: str) -> None:
        """Write `body` as the body of issue `number`, keeping its record block, raising if it
        is not an issue of this repository."""
        issue = self._require_issue(number, "roadmap.issue.write_body")
        self._update_issue(issue, body=with_record(body, self._block(issue)))
        self._log("write_issue_body", number, value=body)

    # ── Items ──

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is no Item."""
        issue = self._roadmap.issues.get(number)
        return next(iter(select_items([self._read(issue)])), None) if issue else None

    def items(self, *, milestone: int | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the milestone numbered `milestone`."""
        issues = list(self._roadmap.issues.values())
        if milestone is not None:
            held = self._roadmap.milestones.get(milestone)
            title = held.title if held is not None else None
            issues = [issue for issue in issues if title is not None and issue.milestone == title]
        return select_items(self._read(issue) for issue in issues)

    def backlog(self) -> list[Item]:
        """The open Items in no milestone."""
        return [
            item
            for item in self.items()
            if item.state is GitHubState.OPEN and item.milestone is None
        ]

    def open_items(self) -> list[Item]:
        """The open Items."""
        return [item for item in self.items() if item.state is GitHubState.OPEN]

    def open_pulls(self) -> list[OpenPull]:
        """The open pull requests that `seed_pull` made."""
        pulls = (
            (self._roadmap.issues[number], head_ref, draft)
            for number, (head_ref, draft) in self._roadmap.pulls.items()
        )
        return [
            OpenPull(
                number=issue.number,
                title=issue.title,
                url=issue.url,
                head_ref=head_ref,
                draft=draft,
                updated_at=issue.updated_at or self._roadmap.clock(),
            )
            for issue, head_ref, draft in pulls
            if issue.state is GitHubState.OPEN
        ]

    def repository_labels(self) -> list[RepositoryLabel]:
        """The labels that `seed_label` made."""
        return list(self._roadmap.labels)

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that hold no Priority."""
        return select_candidates(self._read(issue) for issue in self._roadmap.issues.values())

    def changes_since(self, since: datetime, *, except_actor: str | None = None) -> list[Change]:
        """The changes made at or after `since`, oldest first, without those `except_actor`
        made; an empty actor leaves out nothing."""
        cutoff = as_utc(since)
        skipped = except_actor or None
        return [
            change
            for change in self._roadmap.changes
            if change.at >= cutoff and (skipped is None or change.actor != skipped)
        ]

    # ── Item writes ──

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[Any, str | None] | None = None,
    ) -> None:
        """Replace the field's label family on the Item's issue and, as a job, record the value
        and `marks` in its record block, in one step. `job_writes` keeps the field's entry, then
        one entry for each mark. A job's write of a field a person changed since raises."""
        operation = "roadmap.item.set_field"
        require_value(field, value, operation)
        issue = self._require_issue(item.number, operation)
        if self._writes_job_record:
            now = item_of(self._read(issue)).field_value(field)
            read = self._written.get((item.number, field), item.field_value(field))
            require_unchanged(f"#{item.number}", field, read, now, value, operation)
        changes = {field: value, **(marks or {})}
        self._relabel(issue, relabeled(issue.labels, field, value), changes)
        self._written[(item.number, field)] = value
        self._log("set_field", item.number, field.value, value)
        for mark, marked in (marks or {}).items():
            self._log("set_mark", item.number, mark.value, marked)

    def set_marks(self, item: Item, marks: Mapping[Any, str | None]) -> None:
        """Set or clear a job's marks in the Item's job record; a person's view keeps no record.
        `job_writes` keeps one entry for each mark."""
        issue = self._require_issue(item.number, "roadmap.item.set_marks")
        self._relabel(issue, issue.labels, marks)
        for mark, value in marks.items():
            self._log("set_mark", item.number, mark.value, value)

    # ── Helpers ──

    def _read(self, issue: IssueRecord) -> IssueRecord:
        """The issue as a read returns it: its record block taken out of the body and read."""
        name = f"#{issue.number}"
        body, held = split_record(issue.body, issue=name)
        return issue.model_copy(
            update={"body": body, "job_record": decode_job_record(held, issue=name)}
        )

    def _block(
        self, issue: IssueRecord, changes: Mapping[Any, str | None] | None = None
    ) -> str | None:
        """The issue's record block with `changes` made, or the block it holds when there are no
        changes; None when it holds none and there are none."""
        _, held = split_record(issue.body, issue=f"#{issue.number}")
        if not held and not changes:
            return None
        return encode_job_record(held, changes or {})

    def _relabel(
        self,
        issue: IssueRecord,
        labels: tuple[str, ...],
        changes: Mapping[Any, str | None] | None = None,
    ) -> None:
        """Write `labels` to the issue and, as a job, `changes` to its record block, recording a
        `labeled` or `unlabeled` change for each label added or removed."""
        update: dict[str, Any] = {"labels": labels}
        if changes and self._writes_job_record:
            body, _ = split_record(issue.body, issue=f"#{issue.number}")
            update["body"] = with_record(body, self._block(issue, changes))
        self._update_issue(issue, **update)
        for label in labels:
            if label not in issue.labels:
                self._record(ChangeKind.LABELED, issue.number, label=label)
        for label in issue.labels:
            if label not in labels:
                self._record(ChangeKind.UNLABELED, issue.number, label=label)

    def _closed_at(self, current: Milestone, state: object) -> dict[str, datetime | None]:
        """When an edit closes the milestone, now; when it reopens it, never; else unchanged."""
        if state is None or state == current.state:
            return {}
        return {"closed_at": self._roadmap.clock() if state == GitHubState.CLOSED else None}

    def _close(self, issue: IssueRecord, reason: CloseReason) -> None:
        """Close the issue for `reason` now, recording the close in its timeline and changes."""
        self._update_issue(
            issue,
            state=GitHubState.CLOSED,
            state_reason=reason.value,
            closed_at=self._roadmap.clock(),
        )
        self._closure(issue.number, ChangeKind.CLOSED, reason.value)
        self._record(ChangeKind.CLOSED, issue.number)

    def _update_issue(self, issue: IssueRecord, **changes: Any) -> None:
        """Write `changes` to the issue, which moves its `updated_at` to now, as any write to an
        issue on GitHub does, a comment included."""
        update = changes | {"updated_at": self._roadmap.clock()}
        self._roadmap.issues[issue.number] = self._roadmap.issues[issue.number].model_copy(
            update=update
        )

    def _closure(self, number: int, kind: ChangeKind, reason: str | None = None) -> None:
        closure = Closure(kind=kind, at=self._roadmap.clock(), reason=reason)
        self._roadmap.closures.setdefault(number, []).append(closure)

    def _require_issue(
        self, number: int, operation: str, *, pull_request: bool = False
    ) -> IssueRecord:
        issue = self._roadmap.issues.get(number)
        if issue is None or (issue.pull_request and not pull_request):
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._roadmap.repo}.",
                operation=operation,
                details={"number": number},
            )
        return issue

    def _log(
        self,
        operation: str,
        number: int | None = None,
        key: str | None = None,
        value: str | None = None,
    ) -> None:
        if self._writes_job_record:
            self._roadmap.job_writes.append(JobWrite(operation, number, key, value))

    def _record(self, kind: ChangeKind, number: int, *, label: str | None = None) -> None:
        """Record a change as a poll reads it."""
        self._roadmap.changes.append(
            Change(
                kind=kind, number=number, actor=self._actor, at=self._roadmap.clock(), label=label
            )
        )

    def _retitle(self, old: str, new: str) -> None:
        """Show a renamed milestone's new title on its issues."""
        for issue in list(self._roadmap.issues.values()):
            if issue.milestone == old:
                self._update_issue(issue, milestone=new)

    def _counted(self, milestone: Milestone) -> Milestone:
        """The milestone with its open and closed issue counts, as GitHub reports them."""
        states = [
            issue.state
            for issue in self._roadmap.issues.values()
            if issue.milestone == milestone.title
        ]
        return milestone.model_copy(
            update={
                "open_issues": states.count(GitHubState.OPEN),
                "closed_issues": states.count(GitHubState.CLOSED),
            }
        )


__all__ = ["InMemoryRoadmapStore", "JobWrite"]
