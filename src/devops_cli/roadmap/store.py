"""The roadmap store: the one interface roadmap jobs read and write Items, Releases and board fields through.

An Item is an issue of this repository that is on the board. A Release is a milestone whose
title parses as a version. A Candidate is an open issue of this repository that is not on the
board yet. Both adapters keep the same promises: reads page through every result, a read that
can't complete raises instead of returning an empty or partial result, and no read is cached.

Every Item write also records the value it set in the Item's job record, so a job can tell a
person's change from its own by comparing a field with its record (ADR 0002).
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol, cast, runtime_checkable

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_PROJECT_JOB_RECORD_FIELD
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
    "BoardEntry",
    "Candidate",
    "Change",
    "ChangeKind",
    "GitHubState",
    "IssueRecord",
    "Item",
    "ItemField",
    "JobRecord",
    "Release",
    "RoadmapStore",
    "as_utc",
    "find_release",
    "get_roadmap_store",
    "in_release",
    "is_release_title",
    "join_items",
    "parse_release_version",
    "release_edits",
    "release_title",
    "require_job_record_field",
    "require_new_release",
    "require_option",
    "require_release",
    "select_candidates",
]
