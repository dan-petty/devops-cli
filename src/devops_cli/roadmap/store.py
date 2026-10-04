"""The roadmap store: the one interface roadmap jobs read and write Items, Releases and board fields through.

An Item is an issue of this repository that is on the board. A Release is a milestone whose
title parses as a version. A Candidate is an open issue of this repository that is not on the
board yet. A Card is anything on the board: an Item, a pull request, a draft issue or another
repository's issue. Both adapters keep the same promises: reads page through every result, a
read that can't complete raises instead of returning an empty or partial result, and no read is
cached.

Every Item and Card field write also records the value it set in the card's job record, so a
job can tell a person's change from its own by comparing a field with its record (ADR 0002).
The record also holds a job's own marks on an Item, such as the Release whose admitted set it is
in, which change no field. The run record is the job record of one draft issue card, the run
record card, which holds what a job keeps about the repository as a whole.
"""

from __future__ import annotations

from collections.abc import Collection, Container, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator

from devops_cli.config.constants import CONST_GH_PROJECT_JOB_RECORD_FIELD
from devops_cli.config.defaults import DEFAULT_GH_PROJECT_OPTION_COLOR, DEFAULT_RELEASE_LABEL
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.validation import InvalidVersionError

if TYPE_CHECKING:
    from devops_cli.roadmap.board_read import GraphQLSpend
    from devops_cli.roadmap.github_store import GhRunner

# ── Vocabulary ────────────────────────────────────────────────────────────────


class GitHubState(StrEnum):
    """The open or closed state GitHub gives an issue or a milestone."""

    OPEN = "open"
    CLOSED = "closed"


class ItemField(StrEnum):
    """A value on an Item that a job sets and the job record remembers.

    Every value but `RELEASE` names a single-select field on the board. The Release is the
    issue's milestone, which the board only mirrors. Each member's lower-cased name is the
    attribute that holds it on `Item`.
    """

    RELEASE = "Release"
    STATUS = "Status"
    PRIORITY = "Priority"
    VALUE = "Value"
    EFFORT = "Effort"


BOARD_FIELDS: tuple[ItemField, ...] = tuple(f for f in ItemField if f is not ItemField.RELEASE)


class CardKind(StrEnum):
    """What a board card holds, named as `gh project item-list` names it."""

    ISSUE = "Issue"
    PULL_REQUEST = "PullRequest"
    DRAFT_ISSUE = "DraftIssue"


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
    """What happened to an Item or a Release.

    The first six are what the repository's issue events report, and the GitHub adapter reads
    them. GitHub reports none of the rest as an issue event: a poll finds them by comparing what
    it reads with what it read before (ADR 0003). The in-memory adapter records every kind as it
    happens, as such a poll sees it. The four release kinds carry the Release they concern; the
    number of a cut, an un-cut or a ship is its release pull request's.
    """

    JOINED_RELEASE = "joined_release"
    LEFT_RELEASE = "left_release"
    LABELED = "labeled"
    UNLABELED = "unlabeled"
    CLOSED = "closed"
    REOPENED = "reopened"
    FIELD_CHANGED = "field_changed"
    BLOCKED_BY_ADDED = "blocked_by_added"
    BLOCKED_BY_REMOVED = "blocked_by_removed"
    COMMENTED = "commented"
    EDITED = "edited"
    RELEASE_STARTED = "release_started"
    RELEASE_CUT = "release_cut"
    RELEASE_UNCUT = "release_uncut"
    RELEASE_SHIPPED = "release_shipped"


# The kinds that concern a Release, not an Item.
RELEASE_CHANGE_KINDS: frozenset[ChangeKind] = frozenset(
    {
        ChangeKind.RELEASE_STARTED,
        ChangeKind.RELEASE_CUT,
        ChangeKind.RELEASE_UNCUT,
        ChangeKind.RELEASE_SHIPPED,
    }
)


class JobMark(StrEnum):
    """A job's own note, kept in a job record beside the fields it set.

    A mark names a Release by its milestone number, which GitHub keeps when the milestone is
    renamed. On an Item: `ADMITTED` names the Release whose admitted set the Item is in. `LEFT`
    names where a person took the Item out of since a job last placed it: a Release, or
    `backlog` (`CONST_ROADMAP_LEFT_BACKLOG`). Its return there is then never mistaken for the
    job's own placement, and where the person put it counts as a person's placement; a job
    that places the Item clears it. `NUDGED` holds when a job last nudged the Item, as an ISO
    8601 time. `PENDING` holds a change a job began on the Item and has not finished, as JSON,
    so its next run judges it again and finishes it.

    In the run record: `STARTED` names the Release the job last started, or recorded at its
    first run, and `SIZE` gives that Release's size then; a first run writes `SIZE` last.
    """

    ADMITTED = "Admitted"
    LEFT = "Left"
    NUDGED = "Nudged"
    PENDING = "Pending"
    STARTED = "Started"
    SIZE = "Size"


class PullRequestState(StrEnum):
    """Whether a pull request is open, closed without merging, or merged."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


JobRecord = dict[ItemField | JobMark, str | None]

# ── Models ────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=4096)
def _version_of(title: str) -> Version | None:
    """The version a title names, or None; titles repeat on every Item, so each parses once."""
    try:
        return Version(title)
    except InvalidVersion:
        return None


def parse_release_version(version: str) -> Version:
    """Parse a Release version, with or without its leading `v`."""
    parsed = _version_of(version)
    if parsed is None:
        raise InvalidVersionError(version[:256], tool_name="release")
    return parsed


def is_release_title(title: str) -> bool:
    """Report whether a milestone title parses as a version, which makes the milestone a Release."""
    return _version_of(title) is not None


def release_cut_branch(version: str) -> str:
    """The branch the Release of `version` is cut on: `chore/cut-vX.Y.Z` (#982)."""
    return f"chore/cut-v{parse_release_version(version)}"


def release_title(version: str) -> str:
    """The milestone title a Release of `version` carries: the normalized version after a `v`."""
    return f"v{parse_release_version(version)}"


class Release(BaseModel):
    """A milestone whose title parses as a version; `closed_at` is when it last closed."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    description: str = ""
    state: GitHubState = GitHubState.OPEN
    due_on: date | None = None
    open_issues: int = 0
    closed_issues: int = 0
    closed_at: datetime | None = None

    @property
    def version(self) -> Version:
        """The version the title names, which orders Releases and finds them."""
        return parse_release_version(self.title)


class Candidate(BaseModel):
    """An open issue of this repository that is not on the board yet."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    labels: tuple[str, ...] = ()
    release: str | None = None


class Item(BaseModel):
    """An issue of this repository that is on the board, with its board fields and job record.

    State, labels and Release come from the issue; Status, Priority, Value and Effort from the
    board. The job record holds the last value the store set for each field; a field missing
    from it was never set by a job.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    state: GitHubState = GitHubState.OPEN
    state_reason: str | None = None
    labels: tuple[str, ...] = ()
    release: str | None = None
    status: str | None = None
    priority: str | None = None
    value: str | None = None
    effort: str | None = None
    job_record: JobRecord = Field(default_factory=dict)

    def field_value(self, field: ItemField) -> str | None:
        """The Item's current value for `field`, to compare with its job record."""
        return cast(str | None, getattr(self, field.name.lower()))


class Change(BaseModel):
    """One change to an Item or a Release, with who made it and when.

    `release` is the Release an Item joined or left, the Release a release change concerns, or
    else the Release the Item is in when the change is read. `field` names the field a change
    set, the Release for joining or leaving one, and `value` that field's value when the change
    is read. `job_record` is the Item's job record when the change is read, so a change whose
    value matches it is a job's own (ADR 0002).
    """

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    number: int
    actor: str | None
    at: datetime
    release: str | None = None
    label: str | None = None
    field: ItemField | None = None
    value: str | None = None
    job_record: JobRecord = Field(default_factory=dict)


class IssueRecord(BaseModel):
    """What the repository's issue listing says about one issue or pull request.

    `author_association` is GitHub's word for the author's relation to the repository, such as
    `OWNER`, `COLLABORATOR` or `NONE`.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    body: str = ""
    state: GitHubState = GitHubState.OPEN
    state_reason: str | None = None
    labels: tuple[str, ...] = ()
    release: str | None = None
    pull_request: bool = False
    author_association: str | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None


class Closure(BaseModel):
    """One close or reopen of an issue, as its timeline records it: a close carries its state
    reason, and the issue it duplicates when it was closed as a duplicate."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    at: datetime
    reason: str | None = None
    duplicate_of: int | None = None


class IssueQuery(BaseModel):
    """Which issues to count, never pull requests: each condition given narrows the count.

    `labels` must all be on an issue; `uncommented` keeps issues with no comment at all.
    """

    model_config = ConfigDict(frozen=True)

    state: GitHubState | None = None
    labels: tuple[str, ...] = ()
    created_since: datetime | None = None
    closed_since: datetime | None = None
    reason: CloseReason | None = None
    uncommented: bool = False


class Evidence(BaseModel):
    """A piece of evidence for a P0: its kind and the value that names it."""

    model_config = ConfigDict(frozen=True)

    kind: EvidenceKind
    value: str = Field(min_length=1, max_length=128)


class BoardEntry(BaseModel):
    """What the board holds for one issue of this repository: its fields and job record."""

    model_config = ConfigDict(frozen=True)

    number: int
    status: str | None = None
    priority: str | None = None
    value: str | None = None
    effort: str | None = None
    job_record: JobRecord = Field(default_factory=dict)


class Card(BaseModel):
    """Anything on the board, with its board fields and job record.

    A draft issue has no number or URL, and `repository` names the repository an issue or pull
    request belongs to, which need not be this one.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    kind: CardKind
    number: int | None = None
    url: str | None = None
    repository: str | None = None
    status: str | None = None
    priority: str | None = None
    value: str | None = None
    effort: str | None = None
    job_record: JobRecord = Field(default_factory=dict)

    def field_value(self, field: ItemField) -> str | None:
        """The card's current value for a board field."""
        return cast(str | None, getattr(self, field.name.lower()))


class Board(BaseModel):
    """The project board: its node id, number, title and URL."""

    model_config = ConfigDict(frozen=True)

    id: str
    number: int
    title: str
    url: str


class FieldOption(BaseModel):
    """One option of a single-select board field. A new option has no id until the board gives it one."""

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    name: str
    color: str = DEFAULT_GH_PROJECT_OPTION_COLOR
    description: str = ""


class FieldSpec(BaseModel):
    """A board field to create: its name, and its options when it is single-select."""

    model_config = ConfigDict(frozen=True)

    name: str
    single_select: bool = False
    options: tuple[FieldOption, ...] = ()


class BoardField(FieldSpec):
    """A field the board has, with its node id."""

    id: str


class Workflow(BaseModel):
    """One of the board's built-in workflows and whether it is on."""

    model_config = ConfigDict(frozen=True)

    number: int
    name: str
    enabled: bool


class Dependency(BaseModel):
    """An issue an Item waits on, through GitHub's blocked-by link; it may be another repository's."""

    model_config = ConfigDict(frozen=True)

    number: int
    url: str
    repository: str
    state: GitHubState
    release: str | None = None


class PullRequest(BaseModel):
    """A pull request: where it goes, what it says, and when it last moved."""

    model_config = ConfigDict(frozen=True)

    number: int
    url: str
    state: PullRequestState = PullRequestState.OPEN
    draft: bool = False
    base: str = ""
    head: str = ""
    body: str = ""
    labels: tuple[str, ...] = ()
    release: str | None = None
    updated_at: datetime | None = None
    last_commit_at: datetime | None = None

    @field_validator("state", mode="before")
    @classmethod
    def _lower_case_state(cls, state: object) -> object:
        """GraphQL spells the state in capitals (`OPEN`), REST in lower case."""
        return state.lower() if isinstance(state, str) else state


class MergedPullRequest(BaseModel):
    """A pull request merged into a branch: what it says, the commits it merged, and the
    paths it changed, which closure quotes and reads task files from (#743)."""

    model_config = ConfigDict(frozen=True)

    number: int
    url: str
    title: str = ""
    body: str = ""
    labels: tuple[str, ...] = ()
    release: str | None = None
    merge_commit: str
    head_commit: str
    changed_paths: tuple[str, ...] = ()


class Branch(BaseModel):
    """A branch and the commit at its head."""

    model_config = ConfigDict(frozen=True)

    name: str
    sha: str


# ── Rules both adapters apply ─────────────────────────────────────────────────


def as_utc(moment: datetime) -> datetime:
    """Read a naive time as UTC, so it compares with GitHub's timestamps."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def in_release(title: str | None, version: Version) -> bool:
    """Report whether a milestone title names the Release of `version`."""
    return title is not None and _version_of(title) == version


def find_release(releases: Iterable[Release], version: str) -> Release | None:
    """The Release of `version`, whether or not it is written with a leading `v`."""
    wanted = parse_release_version(version)
    return next((release for release in releases if release.version == wanted), None)


def require_release(releases: Iterable[Release], version: str, operation: str) -> Release:
    """The Release of `version`, raising when there is none."""
    found = find_release(releases, version)
    if found is None:
        raise GitHubOperationError(
            f"No Release {version!r} exists.",
            operation=operation,
            details={"version": version[:256]},
        )
    return found


def require_new_release(releases: Iterable[Release], version: str, operation: str) -> str:
    """The title for a new Release of `version`, raising when that version already exists."""
    title = release_title(version)
    if find_release(releases, title) is not None:
        raise GitHubOperationError(
            f"Release {title} already exists.", operation=operation, details={"version": title}
        )
    return title


def release_edits(
    releases: Sequence[Release],
    current: Release,
    *,
    title: str | None,
    description: str | None,
    due_on: date | None,
    state: GitHubState | None,
) -> dict[str, str | date]:
    """The fields an edit of `current` changes: only those it was given.

    A new title must name a version no other Release has. An edit that names no state
    changes no state.
    """
    others = [release for release in releases if release.number != current.number]
    new_title = require_new_release(others, title, "roadmap.release.edit") if title else None
    requested: dict[str, str | date | None] = {
        "title": new_title,
        "description": description,
        "due_on": due_on,
        "state": state,
    }
    return {name: change for name, change in requested.items() if change is not None}


def with_marks(record: JobRecord, marks: Mapping[JobMark, str | None]) -> JobRecord:
    """A copy of the job record with `marks` set or cleared in it."""
    merged: JobRecord = dict(record)
    for mark, value in marks.items():
        merged[mark] = value
    return merged


def is_release_pull_request(
    pull_request: PullRequest, version: Version, default_branch: str
) -> bool:
    """Whether `pull_request` is the Release's pull request, open or not: into the default branch,
    with the `release` label and the Release's milestone. While one is open, the Release is cut,
    draft or not.

    Its head is no test here, so a renamed Release keeps its pull request; the cut opens it from
    `release_cut_branch` (#982), which `devops roadmap close` also requires (#743).
    """
    return (
        pull_request.base == default_branch
        and DEFAULT_RELEASE_LABEL in pull_request.labels
        and in_release(pull_request.release, version)
    )


def require_option(
    options: Mapping[str, Sequence[str]], field: ItemField, value: str | None
) -> None:
    """Refuse a value that isn't one of the board field's options. Clearing is always allowed."""
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


def field_options(fields: Iterable[BoardField]) -> dict[str, tuple[str, ...]]:
    """Each board field's option names by field name; a field that isn't single-select has none."""
    return {field.name: tuple(option.name for option in field.options) for field in fields}


def require_field(fields: Iterable[BoardField], name: str, operation: str) -> BoardField:
    """The board field named `name`, raising when the board has none."""
    found = next((field for field in fields if field.name == name), None)
    if found is None:
        raise GitHubOperationError(
            f"The board has no {name!r} field.", operation=operation, details={"field": name[:256]}
        )
    return found


def require_board_field(field: ItemField) -> None:
    """Refuse a card write to the Release, which is an issue's milestone and not a board field."""
    if field is ItemField.RELEASE:
        raise GitHubOperationError(
            "The Release is an issue's milestone, not a board field; set it on an Item.",
            operation="roadmap.card.set_field",
            details={"field": field.value},
        )


def require_job_record_field(fields: Container[str]) -> None:
    """Refuse an Item write when the board has no field to record it in."""
    if CONST_GH_PROJECT_JOB_RECORD_FIELD not in fields:
        raise GitHubOperationError(
            f"The board has no {CONST_GH_PROJECT_JOB_RECORD_FIELD!r} field, so the store can't "
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
    """Reads and writes the roadmap: its Releases, its Items and their board fields."""

    def releases(self) -> list[Release]:
        """Every Release, sorted by version."""

    def release(self, version: str) -> Release | None:
        """The Release of `version` (`0.2.25` and `v0.2.25` find the same one), or None."""

    def create_release(
        self,
        version: str,
        *,
        description: str = "",
        due_on: date | None = None,
        state: GitHubState = GitHubState.OPEN,
    ) -> Release:
        """Create the Release of `version`, raising if it already exists."""

    def edit_release(
        self,
        version: str,
        *,
        title: str | None = None,
        description: str | None = None,
        due_on: date | None = None,
        state: GitHubState | None = None,
    ) -> Release:
        """Change only the given fields of the Release of `version`, raising if there is none."""

    def close_release(self, version: str) -> Release:
        """Close the Release of `version`, raising if there is none."""

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is not on the board."""

    def items(self, *, release: str | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the Release of `release`."""

    def backlog(self) -> list[Item]:
        """The open Items in no Release."""

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""

    def changes_since(self, since: datetime) -> list[Change]:
        """The Item changes made at or after `since`, oldest first."""

    def add_item(self, number: int) -> None:
        """Put issue `number` on the board, raising if it is not an issue of this repository."""

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[JobMark, str | None] | None = None,
    ) -> None:
        """Record the value in the Item's job record, with `marks` set or cleared in the same
        write, then set or clear the field.

        The record comes first, so a field a write may have changed is never left without the
        record of the job's value: by the record alone, a write that stops between the two
        reads as the job's value a person changed since, so a job that has to tell the two
        apart also reads whether the field changed. A board field takes one of its board
        options; the Release takes an existing Release's version. Anything else, or an Item no
        longer on the board, raises before the store changes anything. The record keeps what
        the store set for the Item's other fields, even when `item` was read before an earlier
        write.
        """

    def delete_release(self, version: str) -> None:
        """Delete the Release of `version`, raising if there is none. Its issues lose their Release."""

    def issues(self) -> list[IssueRecord]:
        """Every issue of the repository, open and closed, on the board or not; never pull requests."""

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""

    def close_issue(self, number: int, reason: CloseReason, comment: str) -> None:
        """Comment on issue `number`, then close it for `reason`, raising if it is not an issue."""

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The text of the repository file at `path` on `ref` (the default branch when None),
        raising `GitHubFileNotFoundError` when there is no such file."""

    # ── The board itself ──
    # No operation edits an existing board's options. GitHub's option input takes no id, so
    # any option list sent gives every option a new id and clears it from every card. A person
    # renames, adds and removes options in the board's field settings, which keep the ids.

    def board(self) -> Board | None:
        """The configured board, or None when its owner has no board with that number."""

    def create_board(self, title: str, fields: Sequence[FieldSpec]) -> Board:
        """Create a board titled `title` with `fields`, linked to the repository, and return it.

        A field the new board already has, such as Status, takes the spec's options in place
        of its own. Those options get new ids, which costs nothing on a board no card is on.
        """

    def board_fields(self) -> list[BoardField]:
        """Every field on the board, with each single-select option's id, color and description."""

    def delete_field(self, name: str) -> None:
        """Delete the board field `name`, raising if the board has none."""

    def cards(self) -> list[Card]:
        """Everything on the board: Items, pull requests, draft issues and other repositories' issues."""

    def set_card_field(self, card: Card, field: ItemField, value: str | None) -> None:
        """Set or clear a board field on any card, then record the value in its job record.

        The Release is not a board field and raises; so do a value that is not one of the
        field's options and a card no longer on the board, before the store changes anything.
        """

    def remove_card(self, card: Card) -> None:
        """Take `card` off the board, raising if it is not on it."""

    def workflows(self) -> list[Workflow]:
        """The board's built-in workflows."""

    # ── What the release rules read and write (#740) ──

    def set_marks(
        self,
        item: Item,
        marks: Mapping[JobMark, str | None],
        *,
        recorded: Mapping[ItemField, str | None] | None = None,
        forgotten: Collection[ItemField] = (),
    ) -> None:
        """Set or clear a job's marks in the Item's job record in one write, changing none of
        its fields.

        The same write can record a value for a field (`recorded`), or drop the value the record
        holds for one (`forgotten`), as for a field no job has set: so a job takes back the
        record of a field write it began and can't show it made. It raises like `set_field`
        before the store changes anything: for an Item no longer on the board, or a board with
        no job record field.
        """

    def run_record(self) -> JobRecord:
        """The run record: the run record card's job record, empty while the board has none."""

    def set_run_record(self, marks: Mapping[JobMark, str | None]) -> None:
        """Set or clear marks in the run record in one write, putting the run record card on
        the board first when it has none. A board with no job record field raises before any
        write."""

    def release_changes(self, number: int) -> list[Change]:
        """Every time issue `number` joined or left a Release, oldest first, as its own events
        report it."""

    def dependencies(self, number: int) -> list[Dependency]:
        """The issues issue `number` waits on through GitHub's blocked-by links, open and closed."""

    def status_changed_at(self, number: int) -> datetime | None:
        """When the Item's Status on the board last changed, or None when it has none."""

    def open_pull_requests(self) -> list[PullRequest]:
        """Every open pull request of the repository, with its last update and last commit."""

    def release_pull_requests(self, version: str) -> list[PullRequest]:
        """Every pull request, open, closed or merged, with the `release` label and the milestone
        of the Release of `version`, raising if there is no such Release."""

    def merged_pull_requests(self, base: str) -> list[MergedPullRequest]:
        """Every pull request merged into branch `base`, oldest first, with the paths each
        changed; a read that can't complete raises and returns no part of the list."""

    def release_published(self, version: str) -> bool:
        """Whether GitHub Release `vX.Y.Z` of `version` is published; a draft is not."""

    def default_branch(self) -> Branch:
        """The repository's default branch and its head commit."""

    def branch(self, name: str) -> str | None:
        """The head commit of branch `name`, or None when there is no such branch."""

    def create_branch(self, name: str, sha: str) -> None:
        """Create branch `name` at commit `sha`, raising if it already exists."""

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""

    def comments_on(self, number: int) -> list[str]:
        """The body of every comment on issue `number`, oldest first."""

    # ── What intake reads and writes (#742) ──

    def close_as_duplicate(self, number: int, original: int, comment: str | None) -> None:
        """Comment on issue `number` unless `comment` is None (a retry whose comment is already
        there), then close it as a duplicate of issue `original`, raising if either is not an
        issue of this repository."""

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number`, oldest first, from its timeline."""

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue `number`, keeping its other labels."""

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether GitHub confirms the evidence: the advisory exists, the run of this repository
        failed, or the commit exists in this repository."""

    def count_issues(self, query: IssueQuery) -> int:
        """How many issues of the repository match `query`, never pull requests."""

    def graphql_spend(self) -> GraphQLSpend | None:
        """The GraphQL points the run spent and the points left, read from GraphQL itself; None
        for a store that spends none."""
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
    that returns the in-memory adapter. Without a board, Release operations work, and Item
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
    "BOARD_FIELDS",
    "RELEASE_CHANGE_KINDS",
    "Board",
    "BoardEntry",
    "BoardField",
    "Branch",
    "Candidate",
    "Card",
    "CardKind",
    "Change",
    "ChangeKind",
    "CloseReason",
    "Closure",
    "Dependency",
    "Evidence",
    "EvidenceKind",
    "FieldOption",
    "FieldSpec",
    "GitHubState",
    "IssueQuery",
    "IssueRecord",
    "Item",
    "ItemField",
    "JobMark",
    "JobRecord",
    "MergedPullRequest",
    "PullRequest",
    "PullRequestState",
    "Release",
    "RoadmapStore",
    "Workflow",
    "as_utc",
    "field_options",
    "find_release",
    "get_roadmap_store",
    "in_release",
    "is_release_pull_request",
    "is_release_title",
    "join_items",
    "parse_release_version",
    "release_cut_branch",
    "release_edits",
    "release_title",
    "require_board_field",
    "require_field",
    "require_job_record_field",
    "require_new_release",
    "require_option",
    "require_release",
    "select_candidates",
    "with_marks",
]
