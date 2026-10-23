"""The in-memory roadmap store: the roadmap held in process, with no I/O, for tests.

It keeps the promises the GitHub adapter keeps, so the contract suite runs against it. A
test seeds milestones with `seed_milestone` and issues with `seed_issue`, and acts as a person
with `as_actor`: a person's writes change fields and record changes under their name, but never
touch the job record. Cards hold option names, and `edit_options_by_hand` renames or clears them
by option id, as GitHub's cards, which hold option ids, show after a person edits a field's
options in its settings.

A person also labels, closes and reopens issues through the helpers below; each records the
change a poll would find. Every write to an issue, a comment included, moves its `updated_at`,
as on GitHub. A person's `archive_card` takes a card off every read with its fields and job
record, and `add_item` restores it, marked `restored`, as GitHub's board does (#1403).
`seed_evidence` makes a piece of evidence one GitHub confirms. Every write the store makes as a
job, not as a person, is kept in `job_writes`, so a test can check what a job wrote and that a
preview wrote nothing.

Each view holds every card as it last read it, with its own writes: a job's write of a field a
person changed since raises before it changes anything, as the GitHub adapter's does against
its listing (#1361). Reads here are live, so a view's next read sees the person's change.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from devops_cli.config.constants import (
    CONST_GH_ISSUE_STATE_REASON_REOPENED,
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_MEMORY_ACTOR, DEFAULT_ROADMAP_MEMORY_REPO
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.roadmap.store import (
    AddedItem,
    BoardEntry,
    BoardField,
    Candidate,
    Change,
    ChangeKind,
    CloseReason,
    Closure,
    Evidence,
    FieldOption,
    GitHubState,
    IssueRecord,
    Item,
    ItemField,
    Milestone,
    RefineRecordKey,
    RoadmapStore,
    as_utc,
    field_options,
    find_milestone,
    join_items,
    milestone_edits,
    milestone_order,
    require_field,
    require_job_record_field,
    require_milestone,
    require_option,
    require_unchanged,
    select_candidates,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _entry(number: int) -> BoardEntry:
    """A new card for issue `number`, with no field set."""
    return BoardEntry(number=number, card_id=f"card-{number}")


def _board_field_named(name: str) -> ItemField | None:
    return next((board_field for board_field in ItemField if board_field.value == name), None)


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
    """The state every view of one in-memory roadmap shares."""

    repo: str
    clock: Callable[[], datetime]
    has_board: bool
    board_fields: dict[str, BoardField] = field(default_factory=dict)
    milestones: dict[int, Milestone] = field(default_factory=dict)
    issues: dict[int, IssueRecord] = field(default_factory=dict)
    cards: dict[int, BoardEntry] = field(default_factory=dict)
    # The cards a person archived, by issue number: in no read, and restored by an add.
    archived: dict[int, BoardEntry] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)
    comments: dict[int, list[str]] = field(default_factory=dict)
    files: dict[tuple[str, str | None], str] = field(default_factory=dict)
    closures: dict[int, list[Closure]] = field(default_factory=dict)
    evidence: set[Evidence] = field(default_factory=set)
    job_writes: list[JobWrite] = field(default_factory=list)
    is_private: bool = False
    ids: Iterator[int] = field(default_factory=lambda: itertools.count(1))

    def new_id(self, kind: str) -> str:
        return f"{kind}-{next(self.ids)}"


class InMemoryRoadmapStore(RoadmapStore):
    """The roadmap in memory: milestones, issues and pull requests, and a board of them.

    `board_options` gives each single-select board field its options; a field left out is
    not on the board, and `seed_field` adds any other. `job_record_field=False` models a board
    that has no `Job record` field, and `board_exists=False` a board number that names no
    board.
    """

    def __init__(
        self,
        *,
        board_options: Mapping[ItemField, Iterable[str]] | None = None,
        job_record_field: bool = True,
        board_exists: bool = True,
        is_private: bool = False,
        repo: str = DEFAULT_ROADMAP_MEMORY_REPO,
        actor: str = DEFAULT_ROADMAP_MEMORY_ACTOR,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._roadmap = _Roadmap(
            repo=repo, clock=clock, has_board=board_exists, is_private=is_private
        )
        self._actor = actor
        self._writes_job_record = True
        # Each card as this view last read or wrote it, by issue number.
        self._read: dict[int, BoardEntry] = {}
        for board_field, names in (board_options or {}).items():
            self.seed_field(board_field.value, options=names)
        if job_record_field:
            self.seed_field(CONST_GH_PROJECT_JOB_RECORD_FIELD, single_select=False)

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
        milestone: str | None = None,
        pull_request: bool = False,
        on_board: bool = False,
        author_association: str | None = None,
    ) -> int:
        """Open an issue (or a pull request) as GitHub would, returning its number.

        `milestone` is the title of a seeded milestone. Seeding records no change. `on_board`
        puts it on the board with no fields set, which `add_item` refuses for a pull request but
        GitHub's board allows. The issue is created now by the store's clock, and closed now
        when seeded closed.
        """
        if milestone is not None:
            require_milestone(self._roadmap.milestones.values(), milestone, "roadmap.issue.seed")
        number = len(self._roadmap.issues) + 1
        kind = "pull" if pull_request else "issues"
        now = self._roadmap.clock()
        self._roadmap.issues[number] = IssueRecord(
            number=number,
            title=title,
            url=f"https://github.com/{self._roadmap.repo}/{kind}/{number}",
            body=body,
            state=state,
            state_reason=state_reason,
            labels=tuple(labels),
            milestone=milestone,
            pull_request=pull_request,
            author_association=author_association,
            created_at=now,
            updated_at=now,
            closed_at=now if state is GitHubState.CLOSED else None,
        )
        if on_board:
            self._roadmap.cards[number] = _entry(number)
        return number

    def seed_field(
        self, name: str, *, options: Iterable[str] = (), single_select: bool = True
    ) -> BoardField:
        """Put a field on the board, giving it and each of its options an id."""
        created = BoardField(
            id=self._roadmap.new_id("field"),
            name=name,
            single_select=single_select,
            options=tuple(self._with_id(FieldOption(name=option)) for option in options),
        )
        self._roadmap.board_fields[created.name] = created
        return created

    def seed_file(self, path: str, text: str, *, ref: str | None = None) -> None:
        """Commit `text` at `path` on `ref`, or on the default branch when `ref` is None."""
        self._roadmap.files[(path, ref)] = text

    def seed_visibility(self, *, is_private: bool) -> None:
        """Set whether the repository is private."""
        self._roadmap.is_private = is_private

    def edit_options_by_hand(self, name: str, options: Sequence[FieldOption]) -> BoardField:
        """Edit field `name`'s options as a person does in the board's field settings.

        An option given with a current id keeps it under the name given, so its cards keep
        their value; a current option left out is removed, and its cards lose their value.
        No store operation does this, because GitHub's API takes no option id.
        """
        current = require_field(
            self._roadmap.board_fields.values(), name, "roadmap.board.edit_options"
        )
        kept = {option.id: option.name for option in options if option.id is not None}
        renamed = {option.name: kept.get(option.id or "") for option in current.options}
        edited = current.model_copy(
            update={"options": tuple(self._with_id(option) for option in options)}
        )
        self._roadmap.board_fields[name] = edited
        self._map_card_values(name, lambda value: renamed.get(value) if value else None)
        return edited

    def board_fields(self) -> list[BoardField]:
        """Every field on the board, as a test reads it."""
        self._require_board()
        return list(self._roadmap.board_fields.values())

    def job_writes(self) -> list[JobWrite]:
        """Every write the store made as a job, oldest first; a person's writes are not kept."""
        return list(self._roadmap.job_writes)

    # ── What a person does on GitHub ──

    def add_label(self, number: int, label: str) -> None:
        """Label issue `number`, as a person does on GitHub."""
        issue = self._require_issue(number, "roadmap.issue.label")
        if label not in issue.labels:
            self._update_issue(issue, labels=(*issue.labels, label))
            self._record(ChangeKind.LABELED, number, label=label)

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

    def archive_card(self, number: int) -> None:
        """Archive issue `number`'s card, as a person does on the board: it keeps its fields
        and job record and leaves every read, so the issue is a candidate again."""
        entry = self._roadmap.cards.pop(number, None)
        if entry is None:
            raise GitHubOperationError(
                f"#{number} is not on the board.",
                operation="roadmap.card.archive",
                details={"number": number},
            )
        self._roadmap.archived[number] = entry

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
        """Every issue, open and closed, on the board or not; never pull requests."""
        return [issue for issue in self._roadmap.issues.values() if not issue.pull_request]

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""
        number = self.seed_issue(title, body=body, labels=labels)
        self._log("create_issue", number, value=title)
        return self._roadmap.issues[number]

    def close_as_duplicate(self, number: int, original: int, comment: str | None) -> None:
        """Comment on issue `number` unless `comment` is None, then close it as a duplicate of
        issue `original`."""
        issue = self._require_issue(number, "roadmap.issue.close_as_duplicate")
        self._require_issue(original, "roadmap.issue.close_as_duplicate")
        if comment is not None:
            self.comment(number, comment)
        self._close(
            self._roadmap.issues[issue.number], CloseReason.DUPLICATE, duplicate_of=original
        )
        self._log("close_as_duplicate", number, value=str(original))

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number`, oldest first."""
        return list(self._roadmap.closures.get(number, []))

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue `number`, keeping its other labels."""
        issue = self._require_issue(number, "roadmap.issue.label")
        if label not in issue.labels:
            self._update_issue(issue, labels=(*issue.labels, label))
            self._record(ChangeKind.LABELED, number, label=label)
        self._log("label_issue", number, value=label)

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether the evidence was seeded as one GitHub confirms."""
        return evidence in self._roadmap.evidence

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""
        issue = self._require_issue(number, "roadmap.issue.comment")
        self._update_issue(issue)
        self._roadmap.comments.setdefault(number, []).append(body)
        self._log("comment", number, value=body)
        self._record(ChangeKind.COMMENTED, number)

    def comments_on(self, number: int) -> list[str]:
        """The body of every comment on issue `number`, oldest first."""
        return list(self._roadmap.comments.get(number, []))

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

    def read_issue_body(self, number: int) -> str:
        """The body of issue `number`, raising if it is not an issue of this repository."""
        issue = self._require_issue(number, "roadmap.issue.read_body")
        return issue.body

    def write_issue_body(self, number: int, body: str) -> None:
        """Write `body` as the body of issue `number`, raising if it is not an issue of this repository."""
        issue = self._require_issue(number, "roadmap.issue.write_body")
        self._update_issue(issue, body=body)
        self._log("write_issue_body", number, value=body)
        self._record(ChangeKind.EDITED, number)

    # ── Items ──

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is not on the board."""
        self._require_board()
        issue = self._roadmap.issues.get(number)
        found = self._seen(join_items([issue], self._roadmap.cards)) if issue else []
        return next(iter(found), None)

    def items(self, *, milestone: int | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the milestone numbered `milestone`."""
        self._require_board()
        issues = list(self._roadmap.issues.values())
        if milestone is not None:
            held = self._roadmap.milestones.get(milestone)
            title = held.title if held is not None else None
            issues = [issue for issue in issues if title is not None and issue.milestone == title]
        return self._seen(join_items(issues, self._roadmap.cards))

    def backlog(self) -> list[Item]:
        """The open Items in no milestone."""
        return [
            item
            for item in self.items()
            if item.state is GitHubState.OPEN and item.milestone is None
        ]

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""
        self._require_board()
        return select_candidates(self._roadmap.issues.values(), self._roadmap.cards)

    def changes_since(self, since: datetime, *, except_actor: str | None = None) -> list[Change]:
        """The changes made at or after `since`, oldest first, each as a poll reads it now,
        without those `except_actor` made; an empty actor leaves out nothing."""
        cutoff = as_utc(since)
        skipped = except_actor or None
        return [
            self._as_read(change)
            for change in self._roadmap.changes
            if change.at >= cutoff and (skipped is None or change.actor != skipped)
        ]

    # ── Item writes ──

    def add_item(self, number: int) -> AddedItem:
        """Put issue `number` on the board and return its Item, raising if it is not an issue
        of this repository; an issue already on the board keeps its card, and an archived card
        is restored with its fields and marked `restored`."""
        self._require_board()
        issue = self._roadmap.issues.get(number)
        if issue is None or issue.pull_request:
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._roadmap.repo}, so it cannot be an Item.",
                operation="roadmap.item.add",
                details={"number": number},
            )
        archived = self._roadmap.archived.pop(number, None)
        card = self._roadmap.cards.setdefault(number, archived or _entry(number))
        self._read.setdefault(number, card)
        self._log("add_item", number)
        item = join_items([issue], self._roadmap.cards)[0]
        return AddedItem.model_validate(item.model_dump() | {"restored": archived is not None})

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[Any, str | None] | None = None,
    ) -> None:
        """Set or clear one of the Item's board fields; the store's own writes also record the
        value, and `marks` with it, in one step, so no write stops between the two.

        `job_writes` keeps the field's entry, then one entry for each mark. A job's write of a
        board field a person changed since this view read the card raises, unless the card
        already holds `value`.
        """
        operation = "roadmap.item.set_field"
        entry = self._require_entry(item, operation, field, value)
        require_option(field_options(self._roadmap.board_fields.values()), field, value)
        entry = self._recorded(entry.model_copy(update={field.name.lower(): value}), field, value)
        self._record(ChangeKind.FIELD_CHANGED, item.number, field=field, value=value)
        self._log("set_field", item.number, field.value, value)
        for mark, marked in (marks or {}).items():
            entry = self._recorded(entry, mark, marked)
            self._log("set_mark", item.number, mark.value, marked)
        self._roadmap.cards[item.number] = entry
        self._remember(entry, field)

    def set_marks(self, item: Item, marks: Mapping[Any, str | None]) -> None:
        """Set or clear a job's marks in the Item's job record; a person's view keeps no record.
        `job_writes` keeps one entry for each mark."""
        entry = self._require_entry(item, "roadmap.item.set_marks")
        for mark, value in marks.items():
            entry = self._recorded(entry, mark, value)
            self._log("set_mark", item.number, mark.value, value)
        self._roadmap.cards[item.number] = entry
        self._remember(entry)

    # ── Helpers ──

    def _closed_at(self, current: Milestone, state: object) -> dict[str, datetime | None]:
        """When an edit closes the milestone, now; when it reopens it, never; else unchanged."""
        if state is None or state == current.state:
            return {}
        return {"closed_at": self._roadmap.clock() if state == GitHubState.CLOSED else None}

    def _close(
        self, issue: IssueRecord, reason: CloseReason, *, duplicate_of: int | None = None
    ) -> None:
        """Close the issue for `reason` now, recording the close in its timeline and changes."""
        self._update_issue(
            issue,
            state=GitHubState.CLOSED,
            state_reason=reason.value,
            closed_at=self._roadmap.clock(),
        )
        self._closure(issue.number, ChangeKind.CLOSED, reason.value, duplicate_of)
        self._record(ChangeKind.CLOSED, issue.number)

    def _update_issue(self, issue: IssueRecord, **changes: Any) -> None:
        """Write `changes` to the issue, which moves its `updated_at` to now, as any write to an
        issue on GitHub does, a comment included."""
        update = changes | {"updated_at": self._roadmap.clock()}
        self._roadmap.issues[issue.number] = issue.model_copy(update=update)

    def _closure(
        self,
        number: int,
        kind: ChangeKind,
        reason: str | None = None,
        duplicate_of: int | None = None,
    ) -> None:
        closure = Closure(
            kind=kind, at=self._roadmap.clock(), reason=reason, duplicate_of=duplicate_of
        )
        self._roadmap.closures.setdefault(number, []).append(closure)

    def _require_issue(self, number: int, operation: str) -> IssueRecord:
        issue = self._roadmap.issues.get(number)
        if issue is None or issue.pull_request:
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._roadmap.repo}.",
                operation=operation,
                details={"number": number},
            )
        return issue

    def _require_entry(
        self, item: Item, operation: str, field: ItemField | None = None, value: str | None = None
    ) -> BoardEntry:
        """The Item's board entry, refusing an Item off the board, one whose card id is not its
        card's, a board with no record field, and a job's write of `value` to `field` when a
        person changed it since this view read the card."""
        self._require_board()
        entry = self._roadmap.cards.get(item.number)
        if entry is None or entry.card_id != item.card_id:
            raise GitHubOperationError(
                f"#{item.number} is not on the board.",
                operation=operation,
                details={"number": item.number},
            )
        if self._writes_job_record:
            require_job_record_field(self._roadmap.board_fields)
        if field is not None:
            self._require_unchanged(entry, field, value, item.field_value(field), operation)
        return entry

    def _require_unchanged(
        self, entry: BoardEntry, field: ItemField, value: str | None, held: str | None, op: str
    ) -> None:
        """A job's write of `value` to `field` raises when the card holds another value than
        this view read: its own copy, kept current by its writes, or `held`, the caller's, when
        it has none. A person's view checks nothing, as a person on GitHub sees the board."""
        if not self._writes_job_record:
            return
        attribute = field.name.lower()
        read = self._read.get(entry.number)
        before = held if read is None else getattr(read, attribute)
        now = getattr(entry, attribute)
        require_unchanged(f"#{entry.number}", field, {before}, now, value, op)

    def _seen(self, items: list[Item]) -> list[Item]:
        """`items`, each card held as this view read it."""
        self._read.update((item.number, self._roadmap.cards[item.number]) for item in items)
        return items

    def _remember(self, entry: BoardEntry, field: ItemField | None = None) -> None:
        """Hold this view's own write: its copy of the card takes the job record and `field`'s
        value `entry` holds, and keeps its other fields as the view read them."""
        read = self._read.get(entry.number)
        if read is None:
            return
        kept: dict[str, Any] = {"job_record": entry.job_record}
        if field is not None:
            kept[field.name.lower()] = getattr(entry, field.name.lower())
        self._read[entry.number] = read.model_copy(update=kept)

    def _log(
        self,
        operation: str,
        number: int | None = None,
        key: str | None = None,
        value: str | None = None,
    ) -> None:
        if self._writes_job_record:
            self._roadmap.job_writes.append(JobWrite(operation, number, key, value))

    def _as_read(self, change: Change) -> Change:
        """The change as a poll reads it now, as the GitHub adapter reads an issue event: with the
        Item's job record and the field's value now."""
        if change.number not in self._roadmap.issues:
            return change
        entry = self._roadmap.cards.get(change.number, _entry(change.number))
        values = entry.model_dump()
        return change.model_copy(
            update={
                "job_record": entry.job_record,
                "value": values.get(change.field.name.lower()) if change.field else None,
            }
        )

    def _require_board(self) -> None:
        if not self._roadmap.has_board:
            raise GitHubOperationError(
                "The board number names no board, so its cards and fields cannot be read or "
                "written.",
                operation="roadmap.board",
                details={"repo": self._roadmap.repo[:256]},
            )

    def _with_id(self, option: FieldOption) -> FieldOption:
        return (
            option
            if option.id
            else option.model_copy(update={"id": self._roadmap.new_id("option")})
        )

    def _map_card_values(self, field_name: str, change: Callable[[str | None], str | None]) -> None:
        """Change every card's value for the board field `field_name`, if it is one Items carry."""
        board_field = _board_field_named(field_name)
        if board_field is None:
            return
        attribute = board_field.name.lower()
        for number, entry in self._roadmap.cards.items():
            self._roadmap.cards[number] = entry.model_copy(
                update={attribute: change(getattr(entry, attribute))}
            )

    def _recorded(
        self, entry: BoardEntry, key: ItemField | RefineRecordKey, value: str | None
    ) -> BoardEntry:
        if not self._writes_job_record:
            return entry
        return entry.model_copy(update={"job_record": entry.job_record | {key: value}})

    def _record(
        self,
        kind: ChangeKind,
        number: int,
        *,
        field: ItemField | None = None,
        value: str | None = None,
        label: str | None = None,
    ) -> None:
        """Record a change as a poll reads it."""
        self._roadmap.changes.append(
            Change(
                kind=kind,
                number=number,
                actor=self._actor,
                at=self._roadmap.clock(),
                label=label,
                field=field,
                value=value,
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
