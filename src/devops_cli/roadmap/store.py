"""The roadmap store: the one interface roadmap jobs read and write Items, Releases and board fields through.

An Item is an issue of this repository that is on the board. A Release is a milestone whose
title parses as a version. A Candidate is an open issue of this repository that is not on the
board yet. A Card is anything on the board: an Item, a pull request, a draft issue or another
repository's issue. Both adapters keep the same promises: reads page through every result, a
read that can't complete raises instead of returning an empty or partial result, and no read is
cached.

Every Item and Card field write also records the value it set in the card's job record, so a
job can tell a person's change from its own by comparing a field with its record (ADR 0002).
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol, cast, runtime_checkable

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_PROJECT_JOB_RECORD_FIELD
from devops_cli.config.defaults import DEFAULT_GH_PROJECT_OPTION_COLOR
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.validation import InvalidVersionError

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


class ChangeKind(StrEnum):
    """What happened to an Item, as the repository's issue events report it."""

    JOINED_RELEASE = "joined_release"
    LEFT_RELEASE = "left_release"
    LABELED = "labeled"
    UNLABELED = "unlabeled"
    CLOSED = "closed"
    REOPENED = "reopened"


JobRecord = dict[ItemField, str | None]

# ── Models ────────────────────────────────────────────────────────────────────


def parse_release_version(version: str) -> Version:
    """Parse a Release version, with or without its leading `v`."""
    try:
        return Version(version)
    except InvalidVersion as exc:
        raise InvalidVersionError(version[:256], tool_name="release") from exc


def is_release_title(title: str) -> bool:
    """Report whether a milestone title parses as a version, which makes the milestone a Release."""
    try:
        Version(title)
    except InvalidVersion:
        return False
    return True


def release_title(version: str) -> str:
    """The milestone title a Release of `version` carries: the normalized version after a `v`."""
    return f"v{parse_release_version(version)}"


class Release(BaseModel):
    """A milestone whose title parses as a version."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    description: str = ""
    state: GitHubState = GitHubState.OPEN
    due_on: date | None = None
    open_issues: int = 0
    closed_issues: int = 0

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
    """One change to an Item, with who made it and when."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    number: int
    actor: str | None
    at: datetime
    release: str | None = None
    label: str | None = None


class IssueRecord(BaseModel):
    """What the repository's issue listing says about one issue or pull request."""

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


# ── Rules both adapters apply ─────────────────────────────────────────────────


def as_utc(moment: datetime) -> datetime:
    """Read a naive time as UTC, so it compares with GitHub's timestamps."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def in_release(title: str | None, version: Version) -> bool:
    """Report whether a milestone title names the Release of `version`."""
    return title is not None and is_release_title(title) and Version(title) == version


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

    def set_field(self, item: Item, field: ItemField, value: str | None) -> None:
        """Set or clear one of the Item's fields, then record the value in its job record.

        A board field takes one of its board options; the Release takes an existing Release's
        version. Anything else, or an Item no longer on the board, raises before the store
        changes anything. The record keeps what the store set for the Item's other fields, even
        when `item` was read before an earlier write.
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
        """The text of the repository file at `path` on `ref` (the default branch when None)."""

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


def get_roadmap_store(
    repo: str, *, board_owner: str | None = None, board_number: int | None = None
) -> RoadmapStore:
    """Open the roadmap store for `repo`.

    Every caller builds its store here, so a test replaces this one function with a fixture
    that returns the in-memory adapter. Without a board, Release operations work, and Item
    reads and writes raise.
    """
    from devops_cli.roadmap.github_store import GitHubRoadmapStore

    return GitHubRoadmapStore(repo, board_owner=board_owner, board_number=board_number)


__all__ = [
    "BOARD_FIELDS",
    "Board",
    "BoardEntry",
    "BoardField",
    "Candidate",
    "Card",
    "CardKind",
    "Change",
    "ChangeKind",
    "CloseReason",
    "FieldOption",
    "FieldSpec",
    "GitHubState",
    "IssueRecord",
    "Item",
    "ItemField",
    "JobRecord",
    "Release",
    "RoadmapStore",
    "Workflow",
    "as_utc",
    "field_options",
    "find_release",
    "get_roadmap_store",
    "in_release",
    "is_release_title",
    "join_items",
    "parse_release_version",
    "release_edits",
    "release_title",
    "require_board_field",
    "require_field",
    "require_job_record_field",
    "require_new_release",
    "require_option",
    "require_release",
    "select_candidates",
]
