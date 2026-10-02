"""The GitHub roadmap store: Releases, Items and board fields read and written through `gh`.

Every command goes through an injected runner that defaults to `run_gh`, and no read is
cached. REST listings put their endpoint directly after `api --paginate` and ask for full
pages, because `run_gh` pages whatever argument follows `api` and stops at the first page
shorter than it expects. The board comes from `gh project item-list`, which pages itself and
reports a total, so a short read is caught. Issue events are read a page at a time, newest
first, so the read stops at the first event older than it needs.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterator
from datetime import date, datetime
from itertools import takewhile
from typing import Any, Protocol

from pydantic import AliasPath, BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_ISSUE_EVENT_CHANGE_KINDS,
    CONST_GH_PROJECT_ITEM_ISSUE_TYPE,
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_PROJECT_FIELD_LIMIT,
    DEFAULT_GH_PROJECT_ITEM_LIMIT,
    DEFAULT_GH_REST_PER_PAGE,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.projects import check_github_rate_limit_error
from devops_cli.github.rate_limiter import run_gh
from devops_cli.roadmap.store import (
    BOARD_FIELDS,
    BoardEntry,
    Candidate,
    Change,
    ChangeKind,
    GitHubState,
    IssueRecord,
    Item,
    ItemField,
    JobRecord,
    Release,
    RoadmapStore,
    as_utc,
    find_release,
    is_release_title,
    join_items,
    release_edits,
    require_job_record_field,
    require_new_release,
    require_option,
    require_release,
    select_candidates,
)

logger = logging.getLogger(__name__)


class GhRunner(Protocol):
    """Runs one `gh` command the way `run_gh` does, returning the finished process."""

    def __call__(
        self, args: list[str], *, check: bool = ..., quiet: bool = ..., use_cache: bool = ...
    ) -> subprocess.CompletedProcess[str]: ...


# ── Payloads gh returns ───────────────────────────────────────────────────────


class _NamedPayload(BaseModel):
    name: str


class _MilestonePayload(BaseModel):
    number: int
    title: str
    description: str | None = None
    state: GitHubState
    open_issues: int = 0
    closed_issues: int = 0
    due_on: datetime | None = None

    def release(self) -> Release:
        return Release(
            number=self.number,
            title=self.title,
            description=self.description or "",
            state=self.state,
            due_on=self.due_on.date() if self.due_on else None,
            open_issues=self.open_issues,
            closed_issues=self.closed_issues,
        )


class _IssuePayload(BaseModel):
    number: int
    title: str
    html_url: str
    state: GitHubState
    state_reason: str | None = None
    labels: list[_NamedPayload] = Field(default_factory=list)
    release: str | None = Field(default=None, validation_alias=AliasPath("milestone", "title"))
    pull_request: dict[str, Any] | None = None

    def record(self) -> IssueRecord:
        return IssueRecord(
            number=self.number,
            title=self.title,
            url=self.html_url,
            state=self.state,
            state_reason=self.state_reason,
            labels=tuple(label.name for label in self.labels),
            release=self.release,
            pull_request=self.pull_request is not None,
        )


class _EventPayload(BaseModel):
    event: str
    created_at: datetime
    number: int | None = Field(default=None, validation_alias=AliasPath("issue", "number"))
    pull_request: dict[str, Any] | None = Field(
        default=None, validation_alias=AliasPath("issue", "pull_request")
    )
    actor: str | None = Field(default=None, validation_alias=AliasPath("actor", "login"))
    release: str | None = Field(default=None, validation_alias=AliasPath("milestone", "title"))
    label: str | None = Field(default=None, validation_alias=AliasPath("label", "name"))

    def change(self) -> Change | None:
        """The Item change this event reports, or None for pull requests and other events."""
        kind = CONST_GH_ISSUE_EVENT_CHANGE_KINDS.get(self.event)
        if kind is None or self.number is None or self.pull_request is not None:
            return None
        return Change(
            kind=ChangeKind(kind),
            number=self.number,
            actor=self.actor,
            at=self.created_at,
            release=self.release,
            label=self.label,
        )


class _BoardItemPayload(BaseModel):
    """One board item. gh keys each field's value by the field's name, so those stay extra."""

    model_config = ConfigDict(extra="allow")

    content_type: str | None = Field(default=None, validation_alias=AliasPath("content", "type"))
    content_number: int | None = Field(
        default=None, validation_alias=AliasPath("content", "number")
    )
    content_repository: str | None = Field(
        default=None, validation_alias=AliasPath("content", "repository")
    )

    def is_issue_of(self, repo: str) -> bool:
        """Report whether this item is an issue of `repo`, not a pull request, draft or other repo's."""
        return (
            self.content_type == CONST_GH_PROJECT_ITEM_ISSUE_TYPE
            and self.content_number is not None
            and (self.content_repository or "").lower() == repo.lower()
        )

    def entry(self) -> BoardEntry:
        """The board's fields and job record for this issue."""
        values = self.model_extra or {}
        fields = {
            f.name.lower(): _text_value(values.get(_item_list_key(f.value))) for f in BOARD_FIELDS
        }
        record = values.get(_item_list_key(CONST_GH_PROJECT_JOB_RECORD_FIELD))
        return BoardEntry.model_validate(
            fields
            | {"number": self.content_number, "job_record": decode_job_record(_text_value(record))}
        )


class _BoardListingPayload(BaseModel):
    items: list[_BoardItemPayload]
    total_count: int = Field(alias="totalCount")


class _BoardFieldPayload(BaseModel):
    name: str
    options: list[_NamedPayload] = Field(default_factory=list)


class _FieldListingPayload(BaseModel):
    fields: list[_BoardFieldPayload]
    total_count: int = Field(alias="totalCount")


_MILESTONE = TypeAdapter(_MilestonePayload)
_MILESTONES = TypeAdapter(list[_MilestonePayload])
_ISSUE = TypeAdapter(_IssuePayload)
_ISSUES = TypeAdapter(list[_IssuePayload])
_EVENTS = TypeAdapter(list[_EventPayload])
_BOARD = TypeAdapter(_BoardListingPayload)
_FIELDS = TypeAdapter(_FieldListingPayload)
_JOB_RECORD = TypeAdapter(JobRecord)


def _item_list_key(field_name: str) -> str:
    """The key `gh project item-list` gives a field's value: the name, first letter lower-cased."""
    return field_name[:1].lower() + field_name[1:]


def _text_value(raw: object) -> str | None:
    return raw if isinstance(raw, str) and raw else None


def decode_job_record(text: str | None) -> JobRecord:
    """Read a job record. One that isn't valid JSON of known fields reads as no record."""
    if not text:
        return {}
    try:
        return _JOB_RECORD.validate_json(text)
    except MalformedPayloadError:
        logger.warning("Ignoring a malformed job record: %s", text[:256])
        return {}


def encode_job_record(record: JobRecord) -> str:
    """Write a job record as the JSON the board's text field holds."""
    return json.dumps({field.value: value for field, value in record.items()}, sort_keys=True)


def _wire_value(value: str | date) -> str:
    """A milestone field as GitHub's REST API takes it; a due date becomes a timestamp."""
    return f"{value.isoformat()}T00:00:00Z" if isinstance(value, date) else str(value)


def _releases_among(milestones: list[_MilestonePayload]) -> Iterator[Release]:
    for milestone in milestones:
        if is_release_title(milestone.title):
            yield milestone.release()
        else:
            logger.warning("Skipping milestone %r: its title is not a version.", milestone.title)


# ── Adapter ───────────────────────────────────────────────────────────────────


class GitHubRoadmapStore(RoadmapStore):
    """The roadmap on GitHub, read and written as whoever `gh` is logged in as.

    Without a board, Release operations work, and Item reads and writes raise.
    """

    def __init__(
        self,
        repo: str,
        *,
        board_owner: str | None = None,
        board_number: int | None = None,
        runner: GhRunner = run_gh,
    ) -> None:
        self._repo = repo
        self._board: tuple[str, int] | None = (
            (board_owner, board_number) if board_owner and board_number else None
        )
        self._runner = runner

    # ── Releases ──

    def releases(self) -> list[Release]:
        """Every Release, sorted by version; milestones that aren't versions are skipped."""
        milestones = self._read_listing(
            f"repos/{self._repo}/milestones?state=all", _MILESTONES, "milestones"
        )
        return sorted(_releases_among(milestones), key=lambda release: release.version)

    def release(self, version: str) -> Release | None:
        """The Release of `version`, with or without its leading `v`, or None."""
        return find_release(self.releases(), version)

    def create_release(
        self,
        version: str,
        *,
        description: str = "",
        due_on: date | None = None,
        state: GitHubState = GitHubState.OPEN,
    ) -> Release:
        """Create the Release of `version`, raising if it already exists."""
        title = require_new_release(self.releases(), version, "roadmap.release.create")
        fields: dict[str, str | date | None] = {
            "title": title,
            "description": description,
            "due_on": due_on,
            "state": state,
        }
        return self._write_milestone(
            ["api", "-X", "POST", f"repos/{self._repo}/milestones"],
            {name: value for name, value in fields.items() if value is not None},
            f"create Release {title}",
        )

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
        releases = self.releases()
        current = require_release(releases, version, "roadmap.release.edit")
        edits = release_edits(
            releases, current, title=title, description=description, due_on=due_on, state=state
        )
        if not edits:
            return current
        return self._write_milestone(
            ["api", "-X", "PATCH", f"repos/{self._repo}/milestones/{current.number}"],
            edits,
            f"edit Release {current.title}",
        )

    def close_release(self, version: str) -> Release:
        """Close the Release of `version`, raising if there is none."""
        return self.edit_release(version, state=GitHubState.CLOSED)

    # ── Items ──

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is not on the board."""
        board = self._read_board()
        if number not in board:
            return None
        issue = self._read_issue(number)
        return next(iter(join_items([issue.record()], board)), None)

    def items(self, *, release: str | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the Release of `release`."""
        board = self._read_board()
        if release is None:
            return join_items(self._read_issues("state=all"), board)
        found = self.release(release)
        if found is None:
            return []
        return join_items(self._read_issues(f"milestone={found.number}&state=all"), board)

    def backlog(self) -> list[Item]:
        """The open Items in no Release."""
        board = self._read_board()
        return join_items(self._read_issues("milestone=none&state=open"), board)

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""
        board = self._read_board()
        return select_candidates(self._read_issues("state=open"), board)

    def changes_since(self, since: datetime) -> list[Change]:
        """The Item changes made at or after `since`, oldest first, read newest first."""
        cutoff = as_utc(since)
        changes: list[Change] = []
        for page in range(1, DEFAULT_GH_MAX_PAGINATED_PAGES + 1):
            events = self._read(
                [
                    "api",
                    f"repos/{self._repo}/issues/events"
                    f"?per_page={DEFAULT_GH_REST_PER_PAGE}&page={page}",
                ],
                _EVENTS,
                "issue events",
            )
            recent = list(takewhile(lambda event: event.created_at >= cutoff, events))
            changes.extend(change for event in recent if (change := event.change()) is not None)
            if len(recent) < len(events) or len(events) < DEFAULT_GH_REST_PER_PAGE:
                return changes[::-1]
        raise GitHubOperationError(
            f"The issue events of {self._repo} since {cutoff.isoformat()} run past "
            f"{DEFAULT_GH_MAX_PAGINATED_PAGES} pages, so the read can't complete.",
            operation="roadmap.read",
            details={"repo": self._repo[:256]},
        )

    def add_item(self, number: int) -> None:
        """Put issue `number` on the board, raising if it is not an issue of this repository."""
        owner, board_number = self._require_board()
        issue = self._read_issue(number)
        if issue.pull_request is not None:
            raise GitHubOperationError(
                f"#{number} in {self._repo} is a pull request, and only issues are Items.",
                operation="roadmap.item.add",
                details={"repo": self._repo[:256], "number": number},
            )
        self._write(
            ["project", "item-add", str(board_number), "--owner", owner, "--url", issue.html_url],
            f"add #{number} to the board",
        )

    def set_field(self, item: Item, field: ItemField, value: str | None) -> None:
        """Set or clear one of the Item's fields, then record the value in its job record.

        The value joins the job record the board holds now, not the one `item` was read with,
        so two writes from one read both stay recorded.
        """
        options = self._read_board_options()
        require_job_record_field(options)
        entry = self._read_board().get(item.number)
        if entry is None:
            raise GitHubOperationError(
                f"#{item.number} is not on the board.",
                operation="roadmap.item.set_field",
                details={"repo": self._repo[:256], "number": item.number},
            )
        if field is ItemField.RELEASE:
            recorded = self._place_in_release(item, value)
        else:
            require_option(options, field, value)
            change = ["--value", value] if value is not None else ["--clear"]
            self._edit_board_field(item, field.value, change)
            recorded = value
        self._edit_board_field(
            item,
            CONST_GH_PROJECT_JOB_RECORD_FIELD,
            ["--text", encode_job_record(entry.job_record | {field: recorded})],
        )

    # ── Writes ──

    def _place_in_release(self, item: Item, version: str | None) -> str | None:
        """Set or clear the issue's milestone, returning the Release title it now carries."""
        target = (
            require_release(self.releases(), version, "roadmap.item.set_field")
            if version is not None
            else None
        )
        self._write(
            [
                "api",
                "-X",
                "PATCH",
                f"repos/{self._repo}/issues/{item.number}",
                "-F",
                f"milestone={target.number if target else 'null'}",
            ],
            f"set the Release of #{item.number}",
        )
        return target.title if target else None

    def _edit_board_field(self, item: Item, field_name: str, change: list[str]) -> None:
        owner, board_number = self._require_board()
        self._write(
            [
                "project",
                "item-edit",
                str(board_number),
                "--owner",
                owner,
                "--url",
                item.url,
                "--field",
                field_name,
                *change,
            ],
            f"set {field_name} on #{item.number}",
        )

    def _write_milestone(
        self, command: list[str], fields: dict[str, str | date], action: str
    ) -> Release:
        flags = [
            part
            for name, value in fields.items()
            for part in ("-f", f"{name}={_wire_value(value)}")
        ]
        written = self._write([*command, *flags], action)
        return self._validate(written, _MILESTONE, f"milestone after {action}").release()

    def _write(self, args: list[str], action: str) -> str:
        proc = self._run(args)
        if proc.returncode != 0:
            raise self._failure(proc, action, "roadmap.write")
        return proc.stdout or ""

    # ── Reads ──

    def _require_board(self) -> tuple[str, int]:
        if self._board is None:
            raise GitHubOperationError(
                f"No board is configured for {self._repo}, so its Items can't be read or written.",
                operation="roadmap.board",
                details={"repo": self._repo[:256]},
            )
        return self._board

    def _read_board(self) -> dict[int, BoardEntry]:
        """The board's issues of this repository, by number, raising on a short read."""
        owner, number = self._require_board()
        listing = self._read(
            [
                "project",
                "item-list",
                str(number),
                "--owner",
                owner,
                "--format",
                "json",
                "--limit",
                str(DEFAULT_GH_PROJECT_ITEM_LIMIT),
            ],
            _BOARD,
            f"board #{number}",
        )
        self._require_whole(len(listing.items), listing.total_count, f"board #{number} items")
        entries = (item.entry() for item in listing.items if item.is_issue_of(self._repo))
        return {entry.number: entry for entry in entries}

    def _read_board_options(self) -> dict[str, tuple[str, ...]]:
        """Every board field's options by field name; fields that aren't single-select have none."""
        owner, number = self._require_board()
        listing = self._read(
            [
                "project",
                "field-list",
                str(number),
                "--owner",
                owner,
                "--format",
                "json",
                "--limit",
                str(DEFAULT_GH_PROJECT_FIELD_LIMIT),
            ],
            _FIELDS,
            f"board #{number} fields",
        )
        self._require_whole(len(listing.fields), listing.total_count, f"board #{number} fields")
        return {
            board_field.name: tuple(option.name for option in board_field.options)
            for board_field in listing.fields
        }

    def _read_issue(self, number: int) -> _IssuePayload:
        return self._read(
            ["api", f"repos/{self._repo}/issues/{number}"], _ISSUE, f"issue #{number}"
        )

    def _read_issues(self, query: str) -> list[IssueRecord]:
        issues = self._read_listing(f"repos/{self._repo}/issues?{query}", _ISSUES, "issues")
        return [issue.record() for issue in issues]

    def _read_listing[PayloadT](
        self, endpoint: str, adapter: TypeAdapter[PayloadT], what: str
    ) -> PayloadT:
        """Read every page of a REST listing; the endpoint follows `api --paginate` directly."""
        return self._read(
            ["api", "--paginate", f"{endpoint}&per_page={DEFAULT_GH_REST_PER_PAGE}"], adapter, what
        )

    def _read[PayloadT](
        self, args: list[str], adapter: TypeAdapter[PayloadT], what: str
    ) -> PayloadT:
        proc = self._run(args)
        if proc.returncode != 0:
            raise self._failure(proc, f"read {what}", "roadmap.read")
        return self._validate(proc.stdout or "", adapter, what)

    def _validate[PayloadT](self, text: str, adapter: TypeAdapter[PayloadT], what: str) -> PayloadT:
        try:
            return adapter.validate_json(text)
        except MalformedPayloadError as exc:
            raise GitHubOperationError(
                f"GitHub returned malformed {what} for {self._repo}.",
                operation="roadmap.read",
                details={"repo": self._repo[:256], "error": str(exc)[:256]},
            ) from exc

    def _require_whole(self, received: int, total: int, what: str) -> None:
        if received < total:
            raise GitHubOperationError(
                f"Read {received} of {total} {what}, so the read is incomplete.",
                operation="roadmap.read",
                details={"repo": self._repo[:256], "received": received, "total": total},
            )

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return self._runner(args, check=False, quiet=True, use_cache=False)

    def _failure(
        self, proc: subprocess.CompletedProcess[str], action: str, operation: str
    ) -> GitHubOperationError:
        """The error for a failed gh command; a rate limit raises `GitHubRateLimitError` instead."""
        output = f"{proc.stderr or ''} {proc.stdout or ''}".strip()
        check_github_rate_limit_error(output, operation=operation)
        return GitHubOperationError(
            f"Could not {action} in {self._repo} (exit {proc.returncode}): {output[:256]}",
            operation=operation,
            details={"repo": self._repo[:256], "exit_code": proc.returncode},
        )


__all__ = ["GhRunner", "GitHubRoadmapStore", "decode_job_record", "encode_job_record"]
