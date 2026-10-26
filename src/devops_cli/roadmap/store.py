"""The roadmap store: the one interface roadmap jobs read and write Items, milestones and board fields through.

An Item is an issue of this repository that is on the board. A Milestone is a GitHub milestone:
a planning bucket with any title. Its number identifies it, so a rename keeps it, and its due
date orders it. A Candidate is an open issue of this repository that is not on the board yet.
Both adapters keep the same promises: reads page through every result, and a read that cannot
complete raises instead of returning an empty or partial result.

A store lives for one command or one Service round (#1361). It reads the board's fields once,
and the board listing once for each Projects filter, when first needed. Its own writes keep that
listing current with the values they sent and the cards they add. A change someone else makes
meanwhile is seen by the next store (ADR 0003). A write never trusts the listing: it reads the
one card it writes, by the card's node id, so it joins the job record the card holds then. A
job's write of a field someone changed since the store read it raises `RoadmapCardChangedError`
before it changes anything, unless the card already holds the value it writes, so a job never
reverts a change it did not see (ADR 0002).

Every board field write also records the value it set in the card's job record, so a job can
tell a person's change from its own by comparing a field with its record (ADR 0002). The record
also holds refine's own marks on an Item, which change no field.
"""

from __future__ import annotations

from collections.abc import Collection, Container, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_PROJECT_JOB_RECORD_FIELD
from devops_cli.config.defaults import DEFAULT_GH_PROJECT_OPTION_COLOR
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapCardChangedError
from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from devops_cli.roadmap.board_read import GraphQLSpend
    from devops_cli.roadmap.github_store import GhRunner

# ── Vocabulary ────────────────────────────────────────────────────────────────


class GitHubState(StrEnum):
    """The open or closed state GitHub gives an issue or a milestone."""

    OPEN = "open"
    CLOSED = "closed"


class ItemField(StrEnum):
    """A single-select board field on an Item that a job sets and the job record remembers.

    Each member's lower-cased name is the attribute that holds it on `Item`.
    """

    STATUS = "Status"
    PRIORITY = "Priority"
    VALUE = "Value"
    EFFORT = "Effort"


class CloseReason(StrEnum):
    """Why an issue was closed, named as GitHub's `state_reason` names it."""

    COMPLETED = "completed"
    NOT_PLANNED = "not_planned"
    DUPLICATE = "duplicate"


class EvidenceKind(StrEnum):
    """What a piece of evidence for a P0 is (#742): a GitHub security advisory, a failed Actions
    run of this repository, or the commit of this repository that introduced a regression."""

    ADVISORY = "advisory"
    FAILED_RUN = "failed_run"
    REGRESSION_COMMIT = "regression_commit"


class ChangeKind(StrEnum):
    """What happened to an Item.

    Both adapters report the first four, which the repository's issue events report. The
    in-memory adapter also records the rest as they happen: a board field set, a comment and an
    edit. GitHub reports none of those as an event, and the GitHub adapter does not report them.
    A poll finds them only by a comparison of what it reads with what it read before (ADR 0003).
    """

    LABELED = "labeled"
    UNLABELED = "unlabeled"
    CLOSED = "closed"
    REOPENED = "reopened"
    FIELD_CHANGED = "field_changed"
    COMMENTED = "commented"
    EDITED = "edited"


class RefineRecordKey(StrEnum):
    """What refine records in an Item's job record (#744): the body hash outside the section,
    the section hash, whether the proposal needs splitting, the body hash a reply that never
    validated was about (#1539), the next step the item waits on with the open items that
    block it (#1758), and the repository paths whose code the proposal cites as the cause of
    the block (#2005)."""

    BODY_HASH = "refine.body_hash"
    SECTION_HASH = "refine.section_hash"
    NEEDS_SPLIT = "refine.needs_split"
    FAILED_BODY_HASH = "refine.failed_body_hash"
    NEXT_STEP = "refine.next_step"
    BLOCKED_BY = "refine.blocked_by"
    BLOCK_PATHS = "refine.block_paths"


JobRecord = dict[ItemField | RefineRecordKey, str | None]

# ── Models ────────────────────────────────────────────────────────────────────


class Milestone(BaseModel):
    """A GitHub milestone, a planning bucket: its number identifies it and its due date orders
    it. The title is any text. `closed_at` is when it last closed."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    description: str = ""
    state: GitHubState = GitHubState.OPEN
    due_on: date | None = None
    open_issues: int = 0
    closed_issues: int = 0
    closed_at: datetime | None = None


class Candidate(BaseModel):
    """An open issue of this repository that is not on the board yet."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    labels: tuple[str, ...] = ()
    milestone: str | None = None


class Item(BaseModel):
    """An issue of this repository that is on the board, with its board fields and job record.

    State, labels and the milestone title come from the issue; Status, Priority, Value and
    Effort from the board. The job record holds the last value the store set for each field; a
    field missing from it was never set by a job. `card_id` is the node id of the Item's card,
    which every Item a store reads or adds carries and a store writes it by; an Item built as a
    probe has none, and a write to it raises. `body` is the issue's body as the listing the Item
    came from read it, so a job can judge an Item by its text without a read of each issue.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    body: str = ""
    card_id: str | None = None
    state: GitHubState = GitHubState.OPEN
    state_reason: str | None = None
    labels: tuple[str, ...] = ()
    milestone: str | None = None
    status: str | None = None
    priority: str | None = None
    value: str | None = None
    effort: str | None = None
    job_record: JobRecord = Field(default_factory=dict)

    def field_value(self, field: ItemField) -> str | None:
        """The Item's current value for `field`, to compare with its job record."""
        return cast(str | None, getattr(self, field.name.lower()))


class AddedItem(Item):
    """The Item `add_item` returns: `restored` when the card the add named was one a person
    archived, which the add brought back with the fields and job record it holds (#1403)."""

    restored: bool = False


class Change(BaseModel):
    """One change to an Item, with who made it and when.

    `field` names the board field a change set, and `value` that field's value when the change
    is read. `job_record` is the Item's job record when the change is read, so a change whose
    value matches it is a job's own (ADR 0002).
    """

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    number: int
    actor: str | None
    at: datetime
    label: str | None = None
    field: ItemField | None = None
    value: str | None = None
    job_record: JobRecord = Field(default_factory=dict)


class IssueRecord(BaseModel):
    """What the repository's issue listing says about one issue or pull request.

    `milestone` is the title of the issue's milestone. `author_association` is GitHub's word for
    the author's relation to the repository, such as `OWNER`, `COLLABORATOR` or `NONE`.
    `updated_at` is when the issue last changed: any write to it, a comment included, moves it.
    `sub_issues` is how many sub-issues GitHub records for the issue, open or closed. `parent` is
    the number of the issue of the same repository that has the issue as a sub-issue.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    body: str = ""
    state: GitHubState = GitHubState.OPEN
    state_reason: str | None = None
    labels: tuple[str, ...] = ()
    milestone: str | None = None
    pull_request: bool = False
    author_association: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    sub_issues: int = 0
    parent: int | None = None


class IssueComment(BaseModel):
    """One comment on an issue: its body and when it was made."""

    model_config = ConfigDict(frozen=True)

    body: str
    created_at: datetime


class Closure(BaseModel):
    """One close or reopen of an issue, as its timeline records it: a close carries its state
    reason, and the issue it duplicates when it was closed as a duplicate."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    at: datetime
    reason: str | None = None
    duplicate_of: int | None = None


class Evidence(BaseModel):
    """A piece of evidence for a P0: its kind and the value that names it."""

    model_config = ConfigDict(frozen=True)

    kind: EvidenceKind
    value: str = Field(min_length=1, max_length=128)


class BoardEntry(BaseModel):
    """What the board holds for one issue of this repository: its card's node id, its fields
    and its job record."""

    model_config = ConfigDict(frozen=True)

    number: int
    card_id: str
    status: str | None = None
    priority: str | None = None
    value: str | None = None
    effort: str | None = None
    job_record: JobRecord = Field(default_factory=dict)


class FieldOption(BaseModel):
    """One option of a single-select board field. A new option has no id until the board gives it one."""

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    name: str
    color: str = DEFAULT_GH_PROJECT_OPTION_COLOR
    description: str = ""


class BoardField(BaseModel):
    """A field the board has, with its node id, and its options when it is single-select."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    single_select: bool = False
    options: tuple[FieldOption, ...] = ()


# ── Rules both adapters apply ─────────────────────────────────────────────────


def as_utc(moment: datetime) -> datetime:
    """Read a naive time as UTC, so it compares with GitHub's timestamps."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def milestone_order(milestone: Milestone) -> tuple[bool, date, int]:
    """The one order of milestones: by due date, then by number, with no due date last."""
    return (milestone.due_on is None, milestone.due_on or date.min, milestone.number)


def find_milestone(milestones: Iterable[Milestone], name: str) -> Milestone | None:
    """The milestone `name` names: the one with that exact title, else the one with that number
    when `name` is a number. No title is read as a version."""
    listed = list(milestones)
    titled = next((milestone for milestone in listed if milestone.title == name), None)
    if titled is not None or not name.isdecimal():
        return titled
    return next((milestone for milestone in listed if milestone.number == int(name)), None)


def require_milestone(milestones: Iterable[Milestone], name: str, operation: str) -> Milestone:
    """The milestone `name` names, raising when there is none."""
    found = find_milestone(milestones, name)
    if found is None:
        raise GitHubOperationError(
            MESSAGES.roadmap.milestone_missing.format(name=name[:256]),
            operation=operation,
            details={"milestone": name[:256]},
        )
    return found


def milestone_edits(
    milestones: Sequence[Milestone],
    current: Milestone,
    *,
    title: str | None,
    description: str | None,
    due_on: date | None,
    state: GitHubState | None,
) -> dict[str, str | date]:
    """The fields an edit of `current` changes: only those it was given.

    A new title must differ from the title of every other milestone, as GitHub requires. An
    edit that names no state changes no state.
    """
    taken = {milestone.title for milestone in milestones if milestone.number != current.number}
    if title is not None and title in taken:
        raise GitHubOperationError(
            MESSAGES.roadmap.milestone_title_taken.format(title=title[:256]),
            operation="roadmap.milestone.edit",
            details={"title": title[:256]},
        )
    requested: dict[str, str | date | None] = {
        "title": title,
        "description": description,
        "due_on": due_on,
        "state": state,
    }
    return {name: change for name, change in requested.items() if change is not None}


def with_marks(record: JobRecord, marks: Mapping[Any, str | None]) -> JobRecord:
    """A copy of the job record with `marks` set or cleared in it."""
    merged: JobRecord = dict(record)
    for mark, value in marks.items():
        merged[mark] = value
    return merged


def require_option(
    options: Mapping[str, Sequence[str]], field: ItemField, value: str | None
) -> None:
    """Refuse a value that is not one of the board field's options. Clearing is always allowed."""
    if field.value not in options:
        raise GitHubOperationError(
            f"The board has no {field.value!r} field.",
            operation="roadmap.item.set_field",
            details={"field": field.value},
        )
    if value is not None and value not in options[field.value]:
        raise GitHubOperationError(
            f"{value!r} is not a {field.value} option on the board; "
            f"the options are {', '.join(options[field.value])}.",
            operation="roadmap.item.set_field",
            details={"field": field.value, "value": value[:256]},
        )


def require_unchanged(
    card: str,
    field: ItemField,
    read: Collection[str | None],
    now: str | None,
    value: str | None,
    operation: str,
) -> None:
    """Refuse a job's write of `value` to `field` on `card` when the card holds `now` but the
    store read another value (`read` holds each value it read, its own writes included): the
    job planned without that change, so the write would revert it (ADR 0002). Writing the value
    the card holds now reverts nothing, such as the Status the board sets on a card just added.
    """
    if set(read) == {now} or value == now:
        return
    texts = MESSAGES.roadmap
    before = min(set(read) - {now}, key=str)
    raise RoadmapCardChangedError(
        texts.card_changed.format(
            card=card,
            field=field.value,
            now=now or texts.card_value_unset,
            read=before or texts.card_value_unset,
        ),
        operation=operation,
        details={
            "card": card[:256],
            "field": field.value,
            "read": before and before[:256],
            "now": now and now[:256],
        },
    )


def field_options(fields: Iterable[BoardField]) -> dict[str, tuple[str, ...]]:
    """Each board field's option names by field name; a field that is not single-select has none."""
    return {field.name: tuple(option.name for option in field.options) for field in fields}


def require_field(fields: Iterable[BoardField], name: str, operation: str) -> BoardField:
    """The board field named `name`, raising when the board has none."""
    found = next((field for field in fields if field.name == name), None)
    if found is None:
        raise GitHubOperationError(
            f"The board has no {name!r} field.", operation=operation, details={"field": name[:256]}
        )
    return found


def require_job_record_field(fields: Container[str]) -> None:
    """Refuse an Item write when the board has no field to record it in."""
    if CONST_GH_PROJECT_JOB_RECORD_FIELD not in fields:
        raise GitHubOperationError(
            f"The board has no {CONST_GH_PROJECT_JOB_RECORD_FIELD!r} field, so the store cannot "
            "record what it sets. Create it as a TEXT field before writing Items.",
            operation="roadmap.item.set_field",
            details={"field": CONST_GH_PROJECT_JOB_RECORD_FIELD},
        )


def join_items(issues: Iterable[IssueRecord], board: Mapping[int, BoardEntry]) -> list[Item]:
    """The Items among `issues`: the issues, never pull requests, that are on the board."""
    return sorted(
        (
            Item.model_validate(
                issue.model_dump(exclude={"pull_request"})
                | board[issue.number].model_dump(exclude={"number"})
            )
            for issue in issues
            if not issue.pull_request and issue.number in board
        ),
        key=lambda item: item.number,
    )


def select_candidates(
    issues: Iterable[IssueRecord], board: Mapping[int, BoardEntry]
) -> list[Candidate]:
    """The Candidates among `issues`: open issues, never pull requests, that are not on the board."""
    return sorted(
        (
            Candidate.model_validate(issue.model_dump(include=set(Candidate.model_fields)))
            for issue in issues
            if issue.state is GitHubState.OPEN
            and not issue.pull_request
            and issue.number not in board
        ),
        key=lambda candidate: candidate.number,
    )


# ── Interface ─────────────────────────────────────────────────────────────────


@runtime_checkable
class RoadmapStore(Protocol):
    """Reads and writes the roadmap: its milestones, its Items and their board fields."""

    def milestones(self) -> list[Milestone]:
        """Every milestone, open and closed, by due date and then by number (`milestone_order`)."""

    def milestone(self, name: str) -> Milestone | None:
        """The milestone with the exact title `name`, else the one numbered `name`, or None."""

    def edit_milestone(
        self,
        name: str,
        *,
        title: str | None = None,
        description: str | None = None,
        due_on: date | None = None,
        state: GitHubState | None = None,
    ) -> Milestone:
        """Change only the given fields of the milestone `name` names, raising if there is none."""

    def close_milestone(self, name: str) -> Milestone:
        """Close the milestone `name` names, raising if there is none."""

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is not on the board."""

    def items(self, *, milestone: int | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the milestone numbered `milestone`."""

    def backlog(self) -> list[Item]:
        """The open Items in no milestone."""

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""

    def changes_since(self, since: datetime, *, except_actor: str | None = None) -> list[Change]:
        """The Item changes made at or after `since`, oldest first, without those
        `except_actor` made."""

    def add_item(self, number: int) -> AddedItem:
        """Put issue `number` on the board and return it as the Item its card makes it, raising
        if it is not an issue of this repository. An issue already on the board keeps its card,
        which is returned. A card a person archived is restored and returned, marked
        `restored`, with the fields and job record it holds: the board keeps one card for each
        issue, so an add cannot make another (#1403)."""

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[Any, str | None] | None = None,
    ) -> None:
        """Record the value in the Item's job record, with `marks` set or cleared in the same
        write, then set or clear the board field.

        The record comes first, so a field a write may have changed is never left without the
        record of the job's value. A value that is not one of the field's board options, an
        Item no longer on the board, or a field someone changed since the store read the card,
        unless the card already holds `value`, raises before the store changes anything. The
        record keeps what the store set for the Item's other fields, even when `item` was read
        before an earlier write.
        """

    def set_marks(self, item: Item, marks: Mapping[Any, str | None]) -> None:
        """Set or clear a job's marks in the Item's job record in one write, changing none of
        its fields. It raises like `set_field` before the store changes anything: for an Item
        no longer on the board, or a board with no job record field."""

    def issues(self) -> list[IssueRecord]:
        """Every issue of the repository, open and closed, on the board or not; never pull requests."""

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""

    def read_issue_body(self, number: int) -> str:
        """The body of issue `number`, raising if it is not an issue of this repository."""

    def write_issue_body(self, number: int, body: str) -> None:
        """Write `body` as the body of issue `number`, raising if it is not an issue of this repository."""

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The text of the repository file at `path` on `ref` (the default branch when None),
        raising `GitHubFileNotFoundError` when there is no such file."""

    def repository_is_private(self) -> bool:
        """Whether the repository is private."""

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""

    def comments_on(self, number: int) -> list[IssueComment]:
        """Every comment on issue `number`, oldest first."""

    def path_changed_at(self, path: str) -> datetime | None:
        """When the newest commit on the default branch that changed `path` was made, or None
        when no commit changed it (#2005)."""

    # ── What intake reads and writes (#742) ──

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number`, oldest first, from its timeline."""

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue `number`, keeping its other labels."""

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether GitHub confirms the evidence: the advisory exists, the run of this repository
        failed, or the commit exists in this repository."""

    def graphql_spend(self, *, read: bool = True) -> GraphQLSpend | None:
        """The GraphQL points the run spent and the points left, read from GraphQL itself, or
        with `read` False from the last budget a response of the run reported, sending nothing;
        None, with no request sent, for a store that has sent no GraphQL request."""
        return None


def get_roadmap_store(
    repo: str,
    *,
    board_owner: str | None = None,
    board_number: int | None = None,
    runner: GhRunner | None = None,
    board_filter: str = "",
) -> RoadmapStore:
    """Open the roadmap store for `repo`, its `gh` commands through `runner` when one is given.

    Every caller builds its store here, so a test replaces this one function with a fixture
    that returns the in-memory adapter. Without a board, milestone operations work, and Item
    reads and writes raise. Board reads pass `board_filter`, the job's Projects filter.
    """
    from devops_cli.roadmap.github_store import GitHubRoadmapStore

    if runner is None:
        return GitHubRoadmapStore(
            repo, board_owner=board_owner, board_number=board_number, board_filter=board_filter
        )
    return GitHubRoadmapStore(
        repo,
        board_owner=board_owner,
        board_number=board_number,
        runner=runner,
        board_filter=board_filter,
    )


__all__ = [
    "AddedItem",
    "BoardEntry",
    "BoardField",
    "Candidate",
    "Change",
    "ChangeKind",
    "CloseReason",
    "Closure",
    "Evidence",
    "EvidenceKind",
    "FieldOption",
    "GitHubState",
    "IssueComment",
    "IssueRecord",
    "Item",
    "ItemField",
    "JobRecord",
    "Milestone",
    "RefineRecordKey",
    "RoadmapStore",
    "as_utc",
    "field_options",
    "find_milestone",
    "get_roadmap_store",
    "join_items",
    "milestone_edits",
    "milestone_order",
    "require_field",
    "require_job_record_field",
    "require_milestone",
    "require_option",
    "require_unchanged",
    "select_candidates",
    "with_marks",
]
