"""The GitHub roadmap store: Releases, Items and board fields read and written through `gh`.

Every command goes through an injected runner that defaults to `run_gh`, and no read is
cached. REST listings put their endpoint directly after `api --paginate` and ask for full
pages, because `run_gh` pages whatever argument follows `api` and stops at the first page
shorter than it expects. The board comes from `gh project item-list`, which pages itself and
reports a total, so a short read is caught. Issue events are read a page at a time, newest
first, so the read stops at the first event older than it needs.

The board's own shape (its fields with their option ids, colors and descriptions, and its
workflows) comes from GraphQL, because `gh project field-list` gives no option colors or
descriptions. New fields, and the options of a board just created, are written with a GraphQL
request on stdin. GitHub's option input takes no id, so the adapter never sends an option list
to a board that already has cards. A card is edited by its node ids, which reach draft issues
and other repositories' cards too.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterator, Sequence
from datetime import date, datetime
from itertools import takewhile
from typing import Any, Protocol
from urllib.parse import quote

from pydantic import AliasPath, BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_ISSUE_EVENT_CHANGE_KINDS,
    CONST_GH_PROJECT_ITEM_ISSUE_TYPE,
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
    CONST_GH_PROJECT_SINGLE_SELECT_TYPE,
    CONST_GH_PROJECT_TEXT_TYPE,
    CONST_GH_RAW_CONTENT_ACCEPT,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_PROJECT_FIELD_LIMIT,
    DEFAULT_GH_PROJECT_ITEM_LIMIT,
    DEFAULT_GH_PROJECT_LIST_LIMIT,
    DEFAULT_GH_PROJECT_OPTION_COLOR,
    DEFAULT_GH_PROJECT_WORKFLOW_LIMIT,
    DEFAULT_GH_REST_PER_PAGE,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.projects import check_github_rate_limit_error
from devops_cli.github.rate_limiter import run_gh
from devops_cli.roadmap.store import (
    BOARD_FIELDS,
    Board,
    BoardEntry,
    BoardField,
    Candidate,
    Card,
    CardKind,
    Change,
    ChangeKind,
    CloseReason,
    FieldOption,
    FieldSpec,
    GitHubState,
    IssueRecord,
    Item,
    ItemField,
    JobRecord,
    Release,
    RoadmapStore,
    Workflow,
    as_utc,
    field_options,
    find_release,
    is_release_title,
    join_items,
    release_edits,
    require_board_field,
    require_field,
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
        self,
        args: list[str],
        *,
        input: str | None = ...,
        check: bool = ...,
        quiet: bool = ...,
        use_cache: bool = ...,
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
    body: str | None = None
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
            body=self.body or "",
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

    id: str
    content_type: str | None = Field(default=None, validation_alias=AliasPath("content", "type"))
    content_number: int | None = Field(
        default=None, validation_alias=AliasPath("content", "number")
    )
    content_repository: str | None = Field(
        default=None, validation_alias=AliasPath("content", "repository")
    )
    content_url: str | None = Field(default=None, validation_alias=AliasPath("content", "url"))

    def is_issue_of(self, repo: str) -> bool:
        """Report whether this item is an issue of `repo`, not a pull request, draft or other repo's."""
        return (
            self.content_type == CONST_GH_PROJECT_ITEM_ISSUE_TYPE
            and self.content_number is not None
            and (self.content_repository or "").lower() == repo.lower()
        )

    def values(self) -> dict[str, Any]:
        """The card's board fields and job record, keyed as `BoardEntry` and `Card` hold them."""
        extra = self.model_extra or {}
        fields = {
            f.name.lower(): _text_value(extra.get(_item_list_key(f.value))) for f in BOARD_FIELDS
        }
        record = extra.get(_item_list_key(CONST_GH_PROJECT_JOB_RECORD_FIELD))
        return fields | {"job_record": decode_job_record(_text_value(record))}

    def entry(self) -> BoardEntry:
        """The board's fields and job record for this issue."""
        return BoardEntry.model_validate(self.values() | {"number": self.content_number})

    def card(self) -> Card:
        """The card, whatever it holds."""
        return Card.model_validate(
            self.values()
            | {
                "id": self.id,
                "kind": CardKind(self.content_type or CardKind.DRAFT_ISSUE),
                "number": self.content_number,
                "url": self.content_url,
                "repository": self.content_repository,
            }
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


class _ProjectPayload(BaseModel):
    id: str
    number: int
    title: str
    url: str

    def board(self) -> Board:
        return Board.model_validate(self.model_dump())


class _ProjectListingPayload(BaseModel):
    projects: list[_ProjectPayload]
    total_count: int = Field(alias="totalCount")


class _OptionPayload(BaseModel):
    id: str
    name: str
    color: str = DEFAULT_GH_PROJECT_OPTION_COLOR
    description: str = ""


class _FieldNodePayload(BaseModel):
    """A board field as GraphQL gives it; a field that isn't single-select has no options."""

    id: str
    name: str
    data_type: str = Field(alias="dataType")
    options: list[_OptionPayload] = Field(default_factory=list)

    def field(self) -> BoardField:
        return BoardField(
            id=self.id,
            name=self.name,
            single_select=self.data_type == CONST_GH_PROJECT_SINGLE_SELECT_TYPE,
            options=tuple(FieldOption.model_validate(o.model_dump()) for o in self.options),
        )


class _FieldConnectionPayload(BaseModel):
    nodes: list[_FieldNodePayload]
    total_count: int = Field(alias="totalCount")


class _BoardFieldsPayload(BaseModel):
    fields: _FieldConnectionPayload = Field(
        validation_alias=AliasPath("data", "repositoryOwner", "projectV2", "fields")
    )


class _WorkflowConnectionPayload(BaseModel):
    nodes: list[Workflow]
    total_count: int = Field(alias="totalCount")


class _WorkflowsPayload(BaseModel):
    workflows: _WorkflowConnectionPayload = Field(
        validation_alias=AliasPath("data", "repositoryOwner", "projectV2", "workflows")
    )


class _UpdatedFieldPayload(BaseModel):
    field: _FieldNodePayload = Field(
        validation_alias=AliasPath("data", "updateProjectV2Field", "projectV2Field")
    )


_MILESTONE = TypeAdapter(_MilestonePayload)
_MILESTONES = TypeAdapter(list[_MilestonePayload])
_ISSUE = TypeAdapter(_IssuePayload)
_ISSUES = TypeAdapter(list[_IssuePayload])
_EVENTS = TypeAdapter(list[_EventPayload])
_BOARD = TypeAdapter(_BoardListingPayload)
_FIELDS = TypeAdapter(_FieldListingPayload)
_JOB_RECORD = TypeAdapter(JobRecord)
_PROJECT = TypeAdapter(_ProjectPayload)
_PROJECTS = TypeAdapter(_ProjectListingPayload)
_BOARD_FIELDS = TypeAdapter(_BoardFieldsPayload)
_WORKFLOWS = TypeAdapter(_WorkflowsPayload)
_UPDATED_FIELD = TypeAdapter(_UpdatedFieldPayload)

# The board is found by its owner's login and number; `ProjectV2Owner` covers users and
# organizations alike.
_OWNED_BOARD = (
    "query($owner: String!, $number: Int!, $first: Int!) {{ repositoryOwner(login: $owner) {{ "
    "... on ProjectV2Owner {{ projectV2(number: $number) {{ {selection} }} }} }} }}"
)
_FIELD_SELECTION = (
    "... on ProjectV2FieldCommon { id name dataType } "
    "... on ProjectV2SingleSelectField { options { id name color description } }"
)
_FIELDS_QUERY = _OWNED_BOARD.format(
    selection=f"fields(first: $first) {{ totalCount nodes {{ {_FIELD_SELECTION} }} }}"
)
_WORKFLOWS_QUERY = _OWNED_BOARD.format(
    selection="workflows(first: $first) { totalCount nodes { number name enabled } }"
)
_UPDATE_OPTIONS_MUTATION = (
    "mutation($fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) { "
    "updateProjectV2Field(input: {fieldId: $fieldId, singleSelectOptions: $options}) { "
    f"projectV2Field {{ {_FIELD_SELECTION} }} }} }}"
)
_CREATE_FIELD_MUTATION = (
    "mutation($input: CreateProjectV2FieldInput!) { createProjectV2Field(input: $input) { "
    "projectV2Field { ... on ProjectV2FieldCommon { id } } } }"
)


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


def _option_input(option: FieldOption) -> dict[str, str]:
    """An option as `ProjectV2SingleSelectFieldOptionInput` takes it: name, color, description.

    That input defines no id, and GitHub rejects a request that sends a field it doesn't
    define, so an option's id never goes out.
    """
    return {"name": option.name, "color": option.color, "description": option.description}


def option_update_request(field_id: str, options: Sequence[FieldOption]) -> dict[str, Any]:
    """The GraphQL request that makes `options` the whole option list of the field `field_id`.

    Every option it sends gets a new id, and every card loses its value for the field, so the
    adapter sends it only to a board it has just created.
    """
    return {
        "query": _UPDATE_OPTIONS_MUTATION,
        "variables": {"fieldId": field_id, "options": [_option_input(o) for o in options]},
    }


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

    def delete_release(self, version: str) -> None:
        """Delete the Release of `version`, raising if there is none."""
        deleted = require_release(self.releases(), version, "roadmap.release.delete")
        self._write(
            ["api", "-X", "DELETE", f"repos/{self._repo}/milestones/{deleted.number}"],
            f"delete Release {deleted.title}",
        )

    # ── Issues ──

    def issues(self) -> list[IssueRecord]:
        """Every issue, open and closed, on the board or not; never pull requests."""
        return [issue for issue in self._read_issues("state=all") if not issue.pull_request]

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""
        fields = [("title", title), ("body", body), *(("labels[]", label) for label in labels)]
        flags = [part for name, value in fields for part in ("-f", f"{name}={value}")]
        written = self._write(
            ["api", "-X", "POST", f"repos/{self._repo}/issues", *flags],
            f"open the issue {title[:64]!r}",
        )
        return self._validate(written, _ISSUE, "issue after it was opened").record()

    def close_issue(self, number: int, reason: CloseReason, comment: str) -> None:
        """Comment on issue `number`, then close it for `reason`."""
        if self._read_issue(number).pull_request is not None:
            raise GitHubOperationError(
                f"#{number} in {self._repo} is a pull request, not an issue.",
                operation="roadmap.issue.close",
                details={"repo": self._repo[:256], "number": number},
            )
        issue = f"repos/{self._repo}/issues/{number}"
        self._write(
            ["api", "-X", "POST", f"{issue}/comments", "-f", f"body={comment}"],
            f"comment on #{number}",
        )
        self._write(
            ["api", "-X", "PATCH", issue, "-f", "state=closed", "-f", f"state_reason={reason}"],
            f"close #{number}",
        )

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The raw text of `path` on `ref` through the contents API, raising when it can't be read."""
        query = f"?ref={quote(ref, safe='')}" if ref else ""
        endpoint = f"repos/{self._repo}/contents/{quote(path)}{query}"
        proc = self._run(["api", "-H", CONST_GH_RAW_CONTENT_ACCEPT, endpoint])
        if proc.returncode != 0:
            raise self._failure(
                proc, f"read {path} at {ref or 'the default branch'}", "roadmap.read"
            )
        return proc.stdout or ""

    # ── The board ──

    def board(self) -> Board | None:
        """The configured board, or None when its owner has no board with that number."""
        owner, number = self._require_board()
        listing = self._read(
            [
                "project",
                "list",
                "--owner",
                owner,
                "--closed",
                "--format",
                "json",
                "--limit",
                str(DEFAULT_GH_PROJECT_LIST_LIMIT),
            ],
            _PROJECTS,
            f"{owner}'s boards",
        )
        self._require_whole(len(listing.projects), listing.total_count, f"{owner}'s boards")
        return next((p.board() for p in listing.projects if p.number == number), None)

    def create_board(self, title: str, fields: Sequence[FieldSpec]) -> Board:
        """Create a board titled `title`, link it to the repository, then give it `fields`."""
        owner, _ = self._require_board()
        written = self._write(
            ["project", "create", "--owner", owner, "--title", title, "--format", "json"],
            f"create the board {title[:64]!r}",
        )
        created = self._validate(written, _PROJECT, "board after it was created").board()
        self._write(
            ["project", "link", str(created.number), "--owner", owner, "--repo", self._repo],
            f"link board #{created.number}",
        )
        current = {
            board_field.name: board_field for board_field in self._read_fields(created.number)
        }
        for spec in fields:
            self._create_or_align_field(created, current.get(spec.name), spec)
        return created

    def board_fields(self) -> list[BoardField]:
        """Every field on the board, with each option's id, color and description."""
        return self._read_fields(self._require_board()[1])

    def delete_field(self, name: str) -> None:
        """Delete the board field `name`, raising if the board has none."""
        deleted = require_field(self.board_fields(), name, "roadmap.board.delete_field")
        self._write(["project", "field-delete", "--id", deleted.id], f"delete the {name} field")

    def cards(self) -> list[Card]:
        """Everything on the board, whatever it holds and whichever repository it belongs to."""
        return [board_item.card() for board_item in self._read_board_listing().items]

    def set_card_field(self, card: Card, field: ItemField, value: str | None) -> None:
        """Set or clear a board field on any card by its node ids, then record it."""
        require_board_field(field)
        board = self._require_existing_board()
        fields = self.board_fields()
        require_job_record_field(field_options(fields))
        require_option(field_options(fields), field, value)
        current = self._require_card(card, "roadmap.card.set_field")
        target = require_field(fields, field.value, "roadmap.card.set_field")
        option_id = next((option.id for option in target.options if option.name == value), None)
        change = ["--single-select-option-id", option_id] if option_id else ["--clear"]
        record = require_field(fields, CONST_GH_PROJECT_JOB_RECORD_FIELD, "roadmap.card.set_field")
        edits = (
            (target, change),
            (record, ["--text", encode_job_record(current.job_record | {field: value})]),
        )
        for board_field, flags in edits:
            self._write(
                [
                    "project",
                    "item-edit",
                    "--id",
                    card.id,
                    "--project-id",
                    board.id,
                    "--field-id",
                    board_field.id,
                    *flags,
                ],
                f"set {board_field.name} on card {card.id}",
            )

    def remove_card(self, card: Card) -> None:
        """Take `card` off the board, raising if it is not on it."""
        owner, number = self._require_board()
        self._require_card(card, "roadmap.card.remove")
        self._write(
            ["project", "item-delete", str(number), "--owner", owner, "--id", card.id],
            f"remove card {card.id} from board #{number}",
        )

    def workflows(self) -> list[Workflow]:
        """The board's built-in workflows."""
        owner, number = self._require_board()
        payload = self._read(
            self._board_query(_WORKFLOWS_QUERY, owner, number, DEFAULT_GH_PROJECT_WORKFLOW_LIMIT),
            _WORKFLOWS,
            f"board #{number} workflows",
        )
        connection = payload.workflows
        self._require_whole(len(connection.nodes), connection.total_count, "board workflows")
        return list(connection.nodes)

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

    def _read_board_listing(self) -> _BoardListingPayload:
        """Every card on the board, raising on a short read."""
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
        return listing

    def _read_board(self) -> dict[int, BoardEntry]:
        """The board's issues of this repository, by number."""
        items = self._read_board_listing().items
        entries = (item.entry() for item in items if item.is_issue_of(self._repo))
        return {entry.number: entry for entry in entries}

    def _require_existing_board(self) -> Board:
        found = self.board()
        if found is None:
            owner, number = self._require_board()
            raise GitHubOperationError(
                f"{owner} has no board #{number}.",
                operation="roadmap.board",
                details={"owner": owner[:256], "number": number},
            )
        return found

    def _require_card(self, card: Card, operation: str) -> Card:
        """The card as the board holds it now, raising when it is no longer on the board."""
        found = next((current for current in self.cards() if current.id == card.id), None)
        if found is None:
            raise GitHubOperationError(
                f"Card {card.id} is not on the board.",
                operation=operation,
                details={"repo": self._repo[:256], "card": card.id[:256]},
            )
        return found

    def _board_query(self, query: str, owner: str, number: int, first: int) -> list[str]:
        return [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-F",
            f"number={number}",
            "-F",
            f"first={first}",
        ]

    def _read_fields(self, number: int) -> list[BoardField]:
        """Board `number`'s fields through GraphQL, which alone gives option colors and descriptions."""
        owner, _ = self._require_board()
        payload = self._read(
            self._board_query(_FIELDS_QUERY, owner, number, DEFAULT_GH_PROJECT_FIELD_LIMIT),
            _BOARD_FIELDS,
            f"board #{number} fields",
        )
        connection = payload.fields
        self._require_whole(len(connection.nodes), connection.total_count, "board fields")
        return [node.field() for node in connection.nodes]

    def _create_or_align_field(
        self, board: Board, current: BoardField | None, spec: FieldSpec
    ) -> None:
        """Create the spec's field, or give a field the new board already has the spec's options.

        The new board holds no cards, so the new option ids its options get cost no value.
        """
        if current is None:
            data_type = (
                CONST_GH_PROJECT_SINGLE_SELECT_TYPE
                if spec.single_select
                else CONST_GH_PROJECT_TEXT_TYPE
            )
            options = (
                {"singleSelectOptions": [_option_input(o) for o in spec.options]}
                if spec.single_select
                else {}
            )
            created = {"projectId": board.id, "dataType": data_type, "name": spec.name}
            request = {"query": _CREATE_FIELD_MUTATION, "variables": {"input": created | options}}
            self._graphql(request, f"create the {spec.name} field")
        elif current.single_select and spec.single_select:
            self._replace_options(current, spec.options)

    def _replace_options(self, current: BoardField, options: Sequence[FieldOption]) -> BoardField:
        written = self._graphql(
            option_update_request(current.id, options), f"replace the {current.name} options"
        )
        updated = self._validate(written, _UPDATED_FIELD, f"{current.name} field after its update")
        return updated.field.field()

    def _graphql(self, request: dict[str, Any], action: str) -> str:
        """Send a GraphQL write on stdin, so option lists need no flag encoding."""
        proc = self._run(["api", "graphql", "--input", "-"], input=json.dumps(request))
        if proc.returncode != 0:
            raise self._failure(proc, action, "roadmap.write")
        return proc.stdout or ""

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

    def _run(self, args: list[str], input: str | None = None) -> subprocess.CompletedProcess[str]:
        return self._runner(args, input=input, check=False, quiet=True, use_cache=False)

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


__all__ = [
    "GhRunner",
    "GitHubRoadmapStore",
    "decode_job_record",
    "encode_job_record",
    "option_update_request",
]
