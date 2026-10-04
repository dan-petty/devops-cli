"""The GitHub roadmap store: Releases, Items and board fields read and written through `gh`.

Every command goes through an injected runner that defaults to `run_gh`, and no read is
cached. REST listings are read a full page at a time until a page is short, and each page must
be a JSON list: `run_gh`'s own paging (`api --paginate`) ends a listing at a page that is empty
or not JSON as if it were the last. The board comes from `gh project item-list`, which pages itself and
reports a total, so a short read is caught. Issue events are read a page at a time, newest
first, so the read stops at the first event older than it needs.

The board's own shape (its fields with their option ids, colors and descriptions, and its
workflows) comes from GraphQL, because `gh project field-list` gives no option colors or
descriptions. So do the default branch, pull requests with their last commit, and when an
Item's Status last changed, which is the Status value's `updatedAt`: the board's timelines hold
no status-change events (#768). A GraphQL connection is read in one request of up to its limit,
and one longer than that raises. New fields, and the options of a board just created, are
written with a GraphQL request on stdin. GitHub's option input takes no id, so the adapter never
sends an option list to a board that already has cards. A card is edited by its node ids, which
reach draft issues and other repositories' cards too. Issue events carry the Item's job record
from the board as it is when they are read. The run record card is the board's draft issue
titled `CONST_ROADMAP_RUN_RECORD_TITLE`, found by that title in the board listing.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Collection, Iterator, Mapping, Sequence
from datetime import UTC, date, datetime
from http import HTTPStatus
from itertools import takewhile
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from pydantic import AliasPath, BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_API_HTTP_STATUS_RE,
    CONST_GH_ISSUE_EVENT_CHANGE_KINDS,
    CONST_GH_PROJECT_ITEM_ISSUE_TYPE,
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
    CONST_GH_PROJECT_SINGLE_SELECT_TYPE,
    CONST_GH_PROJECT_TEXT_TYPE,
    CONST_GH_RAW_CONTENT_ACCEPT,
    CONST_ROADMAP_RUN_RECORD_BODY,
    CONST_ROADMAP_RUN_RECORD_TITLE,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_ISSUE_TIMELINE_LIMIT,
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_OPEN_PULL_REQUEST_LIMIT,
    DEFAULT_GH_PROJECT_FIELD_LIMIT,
    DEFAULT_GH_PROJECT_ITEM_LIMIT,
    DEFAULT_GH_PROJECT_ITEMS_PER_ISSUE,
    DEFAULT_GH_PROJECT_LIST_LIMIT,
    DEFAULT_GH_PROJECT_OPTION_COLOR,
    DEFAULT_GH_PROJECT_WORKFLOW_LIMIT,
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_RELEASE_LABEL,
)
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.github.projects import check_github_rate_limit_error
from devops_cli.github.rate_limiter import run_gh
from devops_cli.roadmap.store import (
    BOARD_FIELDS,
    Board,
    BoardEntry,
    BoardField,
    Branch,
    Candidate,
    Card,
    CardKind,
    Change,
    ChangeKind,
    CloseReason,
    Closure,
    Dependency,
    Evidence,
    EvidenceKind,
    FieldOption,
    FieldSpec,
    GitHubState,
    IssueQuery,
    IssueRecord,
    Item,
    ItemField,
    JobMark,
    JobRecord,
    PullRequest,
    Release,
    RoadmapStore,
    Workflow,
    as_utc,
    field_options,
    find_release,
    is_release_title,
    join_items,
    release_edits,
    release_title,
    require_board_field,
    require_field,
    require_job_record_field,
    require_new_release,
    require_option,
    require_release,
    select_candidates,
    with_marks,
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
    closed_at: datetime | None = None

    def release(self) -> Release:
        return Release(
            number=self.number,
            title=self.title,
            description=self.description or "",
            state=self.state,
            due_on=self.due_on.date() if self.due_on else None,
            open_issues=self.open_issues,
            closed_issues=self.closed_issues,
            closed_at=self.closed_at,
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
    node_id: str | None = None
    author_association: str | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None

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
            author_association=self.author_association,
            created_at=self.created_at,
            closed_at=self.closed_at,
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
    issue_release: str | None = Field(
        default=None, validation_alias=AliasPath("issue", "milestone", "title")
    )
    label: str | None = Field(default=None, validation_alias=AliasPath("label", "name"))

    def change(self) -> Change | None:
        """The Item change this event reports, or None for pull requests and other events.

        A milestone event sets the Release: it carries the Release joined or left, and the
        Release the issue is in now. Any other event carries the issue's Release now.
        """
        kind = CONST_GH_ISSUE_EVENT_CHANGE_KINDS.get(self.event)
        if kind is None or self.number is None or self.pull_request is not None:
            return None
        moved = self.release is not None
        return Change(
            kind=ChangeKind(kind),
            number=self.number,
            actor=self.actor,
            at=self.created_at,
            release=self.release if moved else self.issue_release,
            label=self.label,
            field=ItemField.RELEASE if moved else None,
            value=self.issue_release if moved else None,
        )


class _DependencyPayload(BaseModel):
    number: int
    html_url: str
    repository_url: str
    state: GitHubState
    release: str | None = Field(default=None, validation_alias=AliasPath("milestone", "title"))

    def dependency(self) -> Dependency:
        """The issue as a Dependency, its repository read from `repository_url`'s last two parts."""
        owner, name = urlsplit(self.repository_url).path.rstrip("/").split("/")[-2:]
        return Dependency(
            number=self.number,
            url=self.html_url,
            repository=f"{owner}/{name}",
            state=self.state,
            release=self.release,
        )


class _PullRequestNodePayload(BaseModel):
    """A pull request as the GraphQL selection `_PULL_REQUEST_SELECTION` gives it."""

    number: int
    url: str
    state: str
    is_draft: bool = Field(alias="isDraft")
    base: str = Field(alias="baseRefName")
    head: str = Field(alias="headRefName")
    body: str = ""
    updated_at: datetime = Field(alias="updatedAt")
    labels: list[_NamedPayload] = Field(validation_alias=AliasPath("labels", "nodes"))
    release: str | None = Field(default=None, validation_alias=AliasPath("milestone", "title"))
    commits: list[dict[str, Any]] = Field(validation_alias=AliasPath("commits", "nodes"))

    def pull_request(self) -> PullRequest:
        last_commit = self.commits[-1]["commit"]["committedDate"] if self.commits else None
        return PullRequest(
            number=self.number,
            url=self.url,
            state=self.state,
            draft=self.is_draft,
            base=self.base,
            head=self.head,
            body=self.body,
            labels=tuple(label.name for label in self.labels),
            release=self.release,
            updated_at=self.updated_at,
            last_commit_at=last_commit,
        )


class _PullRequestConnectionPayload(BaseModel):
    nodes: list[_PullRequestNodePayload]
    total_count: int = Field(alias="totalCount")


class _OpenPullRequestsPayload(BaseModel):
    connection: _PullRequestConnectionPayload = Field(
        validation_alias=AliasPath("data", "repository", "pullRequests")
    )


class _ReleasePullRequestsPayload(BaseModel):
    connection: _PullRequestConnectionPayload = Field(
        validation_alias=AliasPath("data", "repository", "milestone", "pullRequests")
    )


class _ProjectStatusPayload(BaseModel):
    """One board card of an issue: which board, and when its Status last changed."""

    number: int = Field(validation_alias=AliasPath("project", "number"))
    owner: str | None = Field(default=None, validation_alias=AliasPath("project", "owner", "login"))
    status_changed_at: datetime | None = Field(
        default=None, validation_alias=AliasPath("fieldValueByName", "updatedAt")
    )


class _ProjectStatusConnectionPayload(BaseModel):
    nodes: list[_ProjectStatusPayload]
    total_count: int = Field(alias="totalCount")


class _IssueStatusPayload(BaseModel):
    cards: _ProjectStatusConnectionPayload = Field(
        validation_alias=AliasPath("data", "repository", "issue", "projectItems")
    )


class _DefaultBranchPayload(BaseModel):
    name: str = Field(validation_alias=AliasPath("data", "repository", "defaultBranchRef", "name"))
    sha: str = Field(
        validation_alias=AliasPath("data", "repository", "defaultBranchRef", "target", "oid")
    )


class _RefPayload(BaseModel):
    sha: str = Field(validation_alias=AliasPath("object", "sha"))


class _GitHubReleasePayload(BaseModel):
    draft: bool


class _CommentPayload(BaseModel):
    body: str = ""


class _TimelineNodePayload(BaseModel):
    """A `ClosedEvent` or `ReopenedEvent` as `_CLOSURES_QUERY` selects it."""

    typename: str = Field(alias="__typename")
    created_at: datetime = Field(alias="createdAt")
    state_reason: str | None = Field(default=None, alias="stateReason")
    duplicate_of: int | None = Field(
        default=None, validation_alias=AliasPath("duplicateOf", "number")
    )

    def closure(self) -> Closure:
        closed = self.typename == "ClosedEvent"
        return Closure(
            kind=ChangeKind.CLOSED if closed else ChangeKind.REOPENED,
            at=self.created_at,
            reason=self.state_reason.lower() if self.state_reason else None,
            duplicate_of=self.duplicate_of,
        )


class _TimelinePayload(BaseModel):
    nodes: list[_TimelineNodePayload] = Field(
        validation_alias=AliasPath("data", "repository", "issue", "timelineItems", "nodes")
    )
    total_count: int = Field(
        validation_alias=AliasPath("data", "repository", "issue", "timelineItems", "totalCount")
    )


class _WorkflowRunPayload(BaseModel):
    conclusion: str | None = None


class _SearchPayload(BaseModel):
    total_count: int
    incomplete_results: bool = False


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
    content_title: str | None = Field(default=None, validation_alias=AliasPath("content", "title"))

    def is_issue_of(self, repo: str) -> bool:
        """Report whether this item is an issue of `repo`, not a pull request, draft or other repo's."""
        return (
            self.content_type == CONST_GH_PROJECT_ITEM_ISSUE_TYPE
            and self.content_number is not None
            and (self.content_repository or "").lower() == repo.lower()
        )

    def is_run_record(self) -> bool:
        """Report whether this item is the run record card: the draft issue with its title."""
        return (
            self.content_type == CardKind.DRAFT_ISSUE
            and self.content_title == CONST_ROADMAP_RUN_RECORD_TITLE
        )

    def values(self) -> dict[str, Any]:
        """The card's board fields and job record, keyed as `BoardEntry` and `Card` hold them."""
        extra = self.model_extra or {}
        fields = {
            f.name.lower(): _text_value(extra.get(_item_list_key(f.value))) for f in BOARD_FIELDS
        }
        return fields | {"job_record": decode_job_record(self.job_record_text(), card=self.name())}

    def name(self) -> str:
        """The card as an error names it: its issue's number, or its node id."""
        return f"#{self.content_number}" if self.content_number else f"card {self.id}"

    def job_record_text(self) -> str | None:
        """The job record as the board's text field holds it."""
        extra = self.model_extra or {}
        return _text_value(extra.get(_item_list_key(CONST_GH_PROJECT_JOB_RECORD_FIELD)))

    def recorded(
        self,
        changes: Mapping[ItemField, str | None] | Mapping[JobMark, str | None] | JobRecord,
        forgotten: Collection[ItemField] = (),
    ) -> str:
        """The job record with `changes` made and the values of `forgotten` dropped, as the text
        field takes it, keeping every key of the record held now that this version doesn't
        know."""
        held = self.job_record_text()
        record = decode_job_record(held, card=self.name()) | dict(changes)
        kept = {key: value for key, value in record.items() if key not in forgotten}
        return encode_job_record(kept, over=held, card=self.name())

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
# The job record keys this version reads; the others are a newer version's, kept as they are.
_JOB_RECORD_KEYS = frozenset(key.value for key in (*ItemField, *JobMark))
_PROJECT = TypeAdapter(_ProjectPayload)
_PROJECTS = TypeAdapter(_ProjectListingPayload)
_BOARD_FIELDS = TypeAdapter(_BoardFieldsPayload)
_WORKFLOWS = TypeAdapter(_WorkflowsPayload)
_UPDATED_FIELD = TypeAdapter(_UpdatedFieldPayload)
_DEPENDENCIES = TypeAdapter(list[_DependencyPayload])
_OPEN_PULL_REQUESTS = TypeAdapter(_OpenPullRequestsPayload)
_RELEASE_PULL_REQUESTS = TypeAdapter(_ReleasePullRequestsPayload)
_ISSUE_STATUS = TypeAdapter(_IssueStatusPayload)
_DEFAULT_BRANCH = TypeAdapter(_DefaultBranchPayload)
_REF = TypeAdapter(_RefPayload)
_GITHUB_RELEASE = TypeAdapter(_GitHubReleasePayload)
_COMMENTS = TypeAdapter(list[_CommentPayload])
_TIMELINE = TypeAdapter(_TimelinePayload)
_WORKFLOW_RUN = TypeAdapter(_WorkflowRunPayload)
_ANY_OBJECT = TypeAdapter(dict[str, Any])
_SEARCH = TypeAdapter(_SearchPayload)

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
_REPOSITORY = (
    "query($owner: String!, $name: String!{params}) {{ "
    "repository(owner: $owner, name: $name) {{ {selection} }} }}"
)
_PULL_REQUEST_SELECTION = (
    "totalCount nodes { number url state isDraft baseRefName headRefName body updatedAt "
    "labels(first: 100) { nodes { name } } milestone { title } "
    "commits(last: 1) { nodes { commit { committedDate } } } }"
)
_OPEN_PULL_REQUESTS_QUERY = _REPOSITORY.format(
    params=", $first: Int!",
    selection=f"pullRequests(states: OPEN, first: $first) {{ {_PULL_REQUEST_SELECTION} }}",
)
_RELEASE_PULL_REQUESTS_QUERY = _REPOSITORY.format(
    params=", $number: Int!, $first: Int!",
    selection=(
        "milestone(number: $number) { pullRequests(first: $first, "
        f"labels: {json.dumps([DEFAULT_RELEASE_LABEL])}) {{ {_PULL_REQUEST_SELECTION} }} }}"
    ),
)
_ISSUE_STATUS_QUERY = _REPOSITORY.format(
    params=", $number: Int!, $first: Int!",
    selection=(
        "issue(number: $number) { projectItems(first: $first) { totalCount nodes { "
        "project { number owner { ... on User { login } ... on Organization { login } } } "
        'fieldValueByName(name: "Status") { '
        "... on ProjectV2ItemFieldSingleSelectValue { updatedAt } } } } }"
    ),
)
_DEFAULT_BRANCH_QUERY = _REPOSITORY.format(
    params="", selection="defaultBranchRef { name target { oid } }"
)
_CLOSURES_QUERY = _REPOSITORY.format(
    params=", $first: Int!, $number: Int!",
    selection=(
        "issue(number: $number) { timelineItems(first: $first, "
        "itemTypes: [CLOSED_EVENT, REOPENED_EVENT]) { totalCount nodes { __typename "
        "... on ClosedEvent { createdAt stateReason duplicateOf { "
        "... on Issue { number } ... on PullRequest { number } } } "
        "... on ReopenedEvent { createdAt } } } }"
    ),
)
_CLOSE_AS_DUPLICATE_MUTATION = (
    "mutation($issue: ID!, $original: ID!) { closeIssue(input: {issueId: $issue, "
    "stateReason: DUPLICATE, duplicateIssueId: $original}) { issue { number } } }"
)
# How REST search names each close reason in its `reason:` qualifier.
_SEARCH_REASONS: Mapping[CloseReason, str] = {
    CloseReason.COMPLETED: "completed",
    CloseReason.NOT_PLANNED: '"not planned"',
    CloseReason.DUPLICATE: "duplicate",
}


def _item_list_key(field_name: str) -> str:
    """The key `gh project item-list` gives a field's value: the name, first letter lower-cased."""
    return field_name[:1].lower() + field_name[1:]


def _text_value(raw: object) -> str | None:
    return raw if isinstance(raw, str) and raw else None


def _malformed_job_record(text: str, card: str) -> GitHubOperationError:
    return GitHubOperationError(
        f"The job record of {card} is not a JSON object whose known keys hold text, so the "
        f"store can't tell what a job set on it: {text[:256]!r}. Clear the card's "
        f"{CONST_GH_PROJECT_JOB_RECORD_FIELD} field or restore it.",
        operation="roadmap.read",
        details={"card": card[:256]},
    )


def _record_object(text: str, card: str) -> dict[str, Any]:
    """The job record's JSON object, raising when the text is not one."""
    try:
        found = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _malformed_job_record(text, card) from exc
    if not isinstance(found, dict):
        raise _malformed_job_record(text, card)
    return found


def decode_job_record(text: str | None, *, card: str = "a card") -> JobRecord:
    """Read a job record: the keys this version knows.

    A key it doesn't know, such as one a newer version writes, is left out here and kept by
    every write (`encode_job_record`). A record that is not a JSON object, or gives a known key
    a value that is not text or null, raises: read as empty, it would make its Item look as if
    no job had ever placed or admitted it.
    """
    if not text:
        return {}
    found = _record_object(text, card)
    known = {key: value for key, value in found.items() if key in _JOB_RECORD_KEYS}
    try:
        return _JOB_RECORD.validate_python(known)
    except MalformedPayloadError as exc:
        raise _malformed_job_record(text, card) from exc


def encode_job_record(record: JobRecord, *, over: str | None = None, card: str = "a card") -> str:
    """Write a job record as the JSON the board's text field holds, keeping each key of the
    record it replaces (`over`) that this version doesn't know."""
    found = _record_object(over, card) if over else {}
    kept = {key: value for key, value in found.items() if key not in _JOB_RECORD_KEYS}
    return json.dumps(kept | {key.value: value for key, value in record.items()}, sort_keys=True)


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


def _search_time(moment: datetime) -> str:
    """A time as REST search's `created:` and `closed:` qualifiers take it: ISO 8601 in UTC."""
    return as_utc(moment).astimezone(UTC).isoformat(timespec="seconds")


def repository_file_args(repo: str, path: str, *, ref: str | None) -> list[str]:
    """The `gh` arguments that read the raw text of `path` on `ref` through the contents API."""
    query = f"?ref={quote(ref, safe='')}" if ref else ""
    return ["api", "-H", CONST_GH_RAW_CONTENT_ACCEPT, f"repos/{repo}/contents/{quote(path)}{query}"]


def issue_search_text(repo: str, query: IssueQuery) -> str:
    """The REST search text for `query`: `repo`'s issues, narrowed by each condition."""
    terms = [f"repo:{repo}", "is:issue"]
    terms += [f"is:{query.state}"] if query.state else []
    terms += [f"label:{json.dumps(label)}" for label in query.labels]
    terms += [f"created:>={_search_time(query.created_since)}"] if query.created_since else []
    terms += [f"closed:>={_search_time(query.closed_since)}"] if query.closed_since else []
    terms += [f"reason:{_SEARCH_REASONS[query.reason]}"] if query.reason else []
    terms += ["comments:0"] if query.uncommented else []
    return " ".join(terms)


def issue_count_args(repo: str, query: IssueQuery) -> list[str]:
    """The `gh` arguments of the REST search whose `total_count` counts `query`'s issues."""
    q = issue_search_text(repo, query)
    return ["api", "-X", "GET", "search/issues", "-f", f"q={q}", "-F", "per_page=1"]


def milestones_endpoint(repo: str) -> str:
    """The REST listing of every milestone of `repo`, open and closed."""
    return f"repos/{repo}/milestones?state=all"


def issues_endpoint(repo: str, query: str = "state=all") -> str:
    """The REST listing of `repo`'s issues that `query` selects, every one by default."""
    return f"repos/{repo}/issues?{query}"


def listing_page_args(endpoint: str, page: int | str) -> list[str]:
    """The `gh` arguments that read page `page` of the REST listing `endpoint`, a full page."""
    separator = "&" if "?" in endpoint else "?"
    return ["api", f"{endpoint}{separator}per_page={DEFAULT_GH_REST_PER_PAGE}&page={page}"]


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
        milestones = self._read_listing(milestones_endpoint(self._repo), _MILESTONES, "milestones")
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
                return self._with_job_records(changes[::-1])
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

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[JobMark, str | None] | None = None,
    ) -> None:
        """Record the value in the Item's job record, with `marks`, then set or clear the field.

        GitHub takes the two as separate calls, and the record goes first: a run that stops
        between them leaves the field as it was and the record naming the job's value, never
        a field the job changed with no record of it. The value joins the job record the board
        holds now, not the one `item` was read with, so two writes from one read both stay
        recorded.
        """
        options, entry = self._require_entry(item, "roadmap.item.set_field")
        if field is ItemField.RELEASE:
            target = self._release_for(value)
            recorded = target.title if target else None
        else:
            require_option(options, field, value)
            recorded = value
        changes = with_marks({field: recorded}, marks or {})
        self._edit_board_field(
            item, CONST_GH_PROJECT_JOB_RECORD_FIELD, ["--text", entry.recorded(changes)]
        )
        if field is ItemField.RELEASE:
            self._place_in_release(item, target)
        else:
            change = ["--value", value] if value is not None else ["--clear"]
            self._edit_board_field(item, field.value, change)

    def set_marks(
        self,
        item: Item,
        marks: Mapping[JobMark, str | None],
        *,
        recorded: Mapping[ItemField, str | None] | None = None,
        forgotten: Collection[ItemField] = (),
    ) -> None:
        """Set or clear a job's marks in the Item's job record, as held on the board now, and
        record or forget a value for a field, in one write."""
        _, entry = self._require_entry(item, "roadmap.item.set_marks")
        changes: JobRecord = {}
        for item_field, value in (recorded or {}).items():
            changes[item_field] = value
        text = entry.recorded(with_marks(changes, marks), forgotten)
        self._edit_board_field(item, CONST_GH_PROJECT_JOB_RECORD_FIELD, ["--text", text])

    def run_record(self) -> JobRecord:
        """The run record card's job record, empty while the board has no such card."""
        card = self._run_record_card()
        return card.card().job_record if card else {}

    def set_run_record(self, marks: Mapping[JobMark, str | None]) -> None:
        """Set or clear marks in the run record card's job record, creating the card first when
        the board has none. The card is found again after it is created, by its title."""
        board = self._require_existing_board()
        fields = self.board_fields()
        require_job_record_field(field_options(fields))
        record = require_field(fields, CONST_GH_PROJECT_JOB_RECORD_FIELD, "roadmap.run_record")
        card = self._run_record_card() or self._create_run_record_card()
        self._write(
            [
                "project",
                "item-edit",
                "--id",
                card.id,
                "--project-id",
                board.id,
                "--field-id",
                record.id,
                "--text",
                card.recorded(marks),
            ],
            "set the run record",
        )

    def release_changes(self, number: int) -> list[Change]:
        """Every time issue `number` joined or left a Release, from its own events."""
        events = self._read_listing(
            f"repos/{self._repo}/issues/{number}/events", _EVENTS, f"#{number} events"
        )
        moves = (ChangeKind.JOINED_RELEASE, ChangeKind.LEFT_RELEASE)
        changes = (event.model_copy(update={"number": number}).change() for event in events)
        return [change for change in changes if change is not None and change.kind in moves]

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
        self.comment(number, comment)
        self._write(
            [
                "api",
                "-X",
                "PATCH",
                f"repos/{self._repo}/issues/{number}",
                "-f",
                "state=closed",
                "-f",
                f"state_reason={reason}",
            ],
            f"close #{number}",
        )

    def comments_on(self, number: int) -> list[str]:
        """The body of every comment on issue `number`, oldest first."""
        listing = self._read_listing(
            f"repos/{self._repo}/issues/{number}/comments", _COMMENTS, f"#{number} comments"
        )
        return [comment.body for comment in listing]

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""
        self._write(
            [
                "api",
                "-X",
                "POST",
                f"repos/{self._repo}/issues/{number}/comments",
                "-f",
                f"body={body}",
            ],
            f"comment on #{number}",
        )

    # ── What intake reads and writes ──

    def close_as_duplicate(self, number: int, original: int, comment: str | None) -> None:
        """Comment on issue `number` unless `comment` is None, then close it as a duplicate of
        `original` through GraphQL, which alone sets the original (`duplicateIssueId`). Both are
        read first, so a pull request on either side raises before any write."""
        node_ids = [self._require_issue_node(n, "roadmap.issue.close") for n in (number, original)]
        if comment is not None:
            self.comment(number, comment)
        request = {
            "query": _CLOSE_AS_DUPLICATE_MUTATION,
            "variables": {"issue": node_ids[0], "original": node_ids[1]},
        }
        self._graphql(request, f"close #{number} as a duplicate of #{original}")

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number` from its timeline, oldest first."""
        query = self._repository_query(
            _CLOSURES_QUERY, first=DEFAULT_GH_ISSUE_TIMELINE_LIMIT, number=number
        )
        timeline = self._read(query, _TIMELINE, f"#{number} timeline")
        self._require_whole(len(timeline.nodes), timeline.total_count, f"#{number} closes")
        return [node.closure() for node in timeline.nodes]

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue `number`; GitHub keeps its other labels."""
        self._write(
            [
                "api",
                "-X",
                "POST",
                f"repos/{self._repo}/issues/{number}/labels",
                "-f",
                f"labels[]={label}",
            ],
            f"label #{number} {label}",
        )

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether GitHub confirms the evidence. The value is one path segment of its endpoint,
        so no value reaches another resource; a commit GitHub can't resolve answers 422."""
        segment = quote(evidence.value, safe="")
        if evidence.kind is EvidenceKind.ADVISORY:
            return (
                self._read_or_none(["api", f"advisories/{segment}"], _ANY_OBJECT, "advisory")
                is not None
            )
        if evidence.kind is EvidenceKind.FAILED_RUN:
            run = self._read_or_none(
                ["api", f"repos/{self._repo}/actions/runs/{segment}"], _WORKFLOW_RUN, "run"
            )
            return run is not None and run.conclusion == "failure"
        commit = self._read_or_none(
            ["api", f"repos/{self._repo}/commits/{segment}"],
            _ANY_OBJECT,
            "commit",
            absent=(HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY),
        )
        return commit is not None

    def count_issues(self, query: IssueQuery) -> int:
        """How many issues match `query`, from REST search's `total_count`, which spends the REST
        quota and no GraphQL points; an incomplete search raises rather than undercount."""
        found = self._read(issue_count_args(self._repo, query), _SEARCH, "issue search")
        if found.incomplete_results:
            raise GitHubOperationError(
                f"GitHub's issue search of {self._repo} came back incomplete, so the count can't "
                "be trusted; run again.",
                operation="roadmap.read",
                details={"repo": self._repo[:256]},
            )
        return found.total_count

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The raw text of `path` on `ref` through the contents API, raising when it can't be read."""
        proc = self._run(repository_file_args(self._repo, path, ref=ref))
        where = f"{path} at {ref or 'the default branch'}"
        if proc.returncode == 0:
            return proc.stdout or ""
        status = CONST_GH_API_HTTP_STATUS_RE.search(f"{proc.stderr or ''} {proc.stdout or ''}")
        if status is not None and int(status.group("status")) == HTTPStatus.NOT_FOUND:
            raise GitHubFileNotFoundError(
                f"{self._repo} has no {where}.",
                operation="roadmap.read",
                details={"repo": self._repo[:256], "path": path[:256]},
            )
        raise self._failure(proc, f"read {where}", "roadmap.read")

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
            (record, ["--text", current.recorded({field: value})]),
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

    # ── What the release rules read and write ──

    def dependencies(self, number: int) -> list[Dependency]:
        """The issues issue `number` waits on through GitHub's blocked-by links."""
        listing = self._read_listing(
            f"repos/{self._repo}/issues/{number}/dependencies/blocked_by",
            _DEPENDENCIES,
            f"#{number} dependencies",
        )
        return [payload.dependency() for payload in listing]

    def status_changed_at(self, number: int) -> datetime | None:
        """The `updatedAt` of the Item's Status on the configured board, or None without one."""
        owner, board_number = self._require_board()
        payload = self._read(
            self._repository_query(
                _ISSUE_STATUS_QUERY, number=number, first=DEFAULT_GH_PROJECT_ITEMS_PER_ISSUE
            ),
            _ISSUE_STATUS,
            f"#{number} board cards",
        )
        cards = payload.cards
        self._require_whole(len(cards.nodes), cards.total_count, f"#{number} board cards")
        return next(
            (
                card.status_changed_at
                for card in cards.nodes
                if card.number == board_number and (card.owner or "").lower() == owner.lower()
            ),
            None,
        )

    def open_pull_requests(self) -> list[PullRequest]:
        """Every open pull request, from one GraphQL read of up to its limit."""
        payload = self._read(
            self._repository_query(
                _OPEN_PULL_REQUESTS_QUERY, first=DEFAULT_GH_OPEN_PULL_REQUEST_LIMIT
            ),
            _OPEN_PULL_REQUESTS,
            "open pull requests",
        )
        return self._pull_requests(payload.connection, "open pull requests")

    def release_pull_requests(self, version: str) -> list[PullRequest]:
        """The pull requests with the `release` label in the Release's milestone."""
        release = require_release(self.releases(), version, "roadmap.release.pull_requests")
        payload = self._read(
            self._repository_query(
                _RELEASE_PULL_REQUESTS_QUERY,
                number=release.number,
                first=DEFAULT_GH_OPEN_PULL_REQUEST_LIMIT,
            ),
            _RELEASE_PULL_REQUESTS,
            f"{release.title} release pull requests",
        )
        return self._pull_requests(payload.connection, f"{release.title} release pull requests")

    def release_published(self, version: str) -> bool:
        """Whether GitHub Release `vX.Y.Z` is published: it exists and is not a draft."""
        tag = release_title(version)
        found = self._read_or_none(
            ["api", f"repos/{self._repo}/releases/tags/{quote(tag)}"],
            _GITHUB_RELEASE,
            f"GitHub Release {tag}",
        )
        return found is not None and not found.draft

    def default_branch(self) -> Branch:
        """The default branch and its head commit, from one GraphQL read."""
        payload = self._read(
            self._repository_query(_DEFAULT_BRANCH_QUERY), _DEFAULT_BRANCH, "default branch"
        )
        return Branch(name=payload.name, sha=payload.sha)

    def branch(self, name: str) -> str | None:
        """The head commit of branch `name`, or None when the ref is not found."""
        found = self._read_or_none(
            ["api", f"repos/{self._repo}/git/ref/heads/{quote(name)}"], _REF, f"branch {name}"
        )
        return found.sha if found else None

    def create_branch(self, name: str, sha: str) -> None:
        """Create branch `name` at `sha`; GitHub refuses a ref that already exists."""
        self._write(
            [
                "api",
                "-X",
                "POST",
                f"repos/{self._repo}/git/refs",
                "-f",
                f"ref=refs/heads/{name}",
                "-f",
                f"sha={sha}",
            ],
            f"create branch {name}",
        )

    # ── Writes ──

    def _with_job_records(self, changes: list[Change]) -> list[Change]:
        """The changes, each with its Item's job record from the board, when one is configured."""
        if self._board is None or not changes:
            return changes
        board = self._read_board()
        return [
            change.model_copy(update={"job_record": board[change.number].job_record})
            if change.number in board
            else change
            for change in changes
        ]

    def _run_record_card(self) -> _BoardItemPayload | None:
        """The run record card as the board holds it now, or None."""
        listing = self._read_board_listing().items
        return next((item for item in listing if item.is_run_record()), None)

    def _create_run_record_card(self) -> _BoardItemPayload:
        """Put the run record card on the board, and read it back."""
        owner, number = self._require_board()
        self._write(
            [
                "project",
                "item-create",
                str(number),
                "--owner",
                owner,
                "--title",
                CONST_ROADMAP_RUN_RECORD_TITLE,
                "--body",
                CONST_ROADMAP_RUN_RECORD_BODY,
            ],
            "create the run record card",
        )
        created = self._run_record_card()
        if created is None:
            raise GitHubOperationError(
                f"Board #{number} does not list the run record card just created.",
                operation="roadmap.run_record",
                details={"repo": self._repo[:256], "board": number},
            )
        return created

    def _require_entry(
        self, item: Item, operation: str
    ) -> tuple[dict[str, tuple[str, ...]], _BoardItemPayload]:
        """The board's options and the Item's card, raising before any write when either is missing."""
        options = self._read_board_options()
        require_job_record_field(options)
        entry = self._read_board_items().get(item.number)
        if entry is None:
            raise GitHubOperationError(
                f"#{item.number} is not on the board.",
                operation=operation,
                details={"repo": self._repo[:256], "number": item.number},
            )
        return options, entry

    def _release_for(self, version: str | None) -> Release | None:
        """The Release of `version` an issue is placed in, None for the backlog; raising when
        there is no such Release."""
        if version is None:
            return None
        return require_release(self.releases(), version, "roadmap.item.set_field")

    def _place_in_release(self, item: Item, target: Release | None) -> None:
        """Set or clear the issue's milestone."""
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
        return {number: item.entry() for number, item in self._read_board_items().items()}

    def _read_board_items(self) -> dict[int, _BoardItemPayload]:
        """The board's cards of this repository's issues, as listed, by number."""
        items = self._read_board_listing().items
        return {
            item.content_number: item
            for item in items
            if item.is_issue_of(self._repo) and item.content_number is not None
        }

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

    def _require_card(self, card: Card, operation: str) -> _BoardItemPayload:
        """The card as the board holds it now, raising when it is no longer on the board."""
        listing = self._read_board_listing().items
        found = next((current for current in listing if current.id == card.id), None)
        if found is None:
            raise GitHubOperationError(
                f"Card {card.id} is not on the board.",
                operation=operation,
                details={"repo": self._repo[:256], "card": card.id[:256]},
            )
        return found

    def _repository_query(self, query: str, **variables: int) -> list[str]:
        """A GraphQL read about this repository, with its integer variables."""
        owner, name = self._repo.split("/", 1)
        typed = [part for key, value in variables.items() for part in ("-F", f"{key}={value}")]
        return [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            *typed,
        ]

    def _pull_requests(
        self, connection: _PullRequestConnectionPayload, what: str
    ) -> list[PullRequest]:
        self._require_whole(len(connection.nodes), connection.total_count, what)
        return [node.pull_request() for node in connection.nodes]

    def _read_or_none[PayloadT](
        self,
        args: list[str],
        adapter: TypeAdapter[PayloadT],
        what: str,
        *,
        absent: Collection[HTTPStatus] = (HTTPStatus.NOT_FOUND,),
    ) -> PayloadT | None:
        """Read one REST resource, or None when GitHub answers with an `absent` status (404);
        any other failure raises."""
        proc = self._run(args)
        if proc.returncode == 0:
            return self._validate(proc.stdout or "", adapter, what)
        status = CONST_GH_API_HTTP_STATUS_RE.search(f"{proc.stderr or ''} {proc.stdout or ''}")
        if status is not None and int(status.group("status")) in absent:
            return None
        raise self._failure(proc, f"read {what}", "roadmap.read")

    def _require_issue_node(self, number: int, operation: str) -> str:
        """Issue `number`'s node id, raising when it is a pull request."""
        issue = self._read_issue(number)
        if issue.pull_request is not None or issue.node_id is None:
            raise GitHubOperationError(
                f"#{number} in {self._repo} is a pull request, not an issue.",
                operation=operation,
                details={"repo": self._repo[:256], "number": number},
            )
        return issue.node_id

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
        issues = self._read_listing(issues_endpoint(self._repo, query), _ISSUES, "issues")
        return [issue.record() for issue in issues]

    def _read_listing[EntryT](
        self, endpoint: str, adapter: TypeAdapter[list[EntryT]], what: str
    ) -> list[EntryT]:
        """Read every page of a REST listing, a full page at a time, until a page is short.

        Each page must be a JSON list, or the read raises, naming it: `api --paginate` would
        end the listing at a page that is empty or not JSON, as a proxy's error page is, and
        report what it read before as the whole of it.
        """
        listing: list[EntryT] = []
        for page in range(1, DEFAULT_GH_MAX_PAGINATED_PAGES + 1):
            entries = self._read(
                listing_page_args(endpoint, page), adapter, f"{what} (page {page})"
            )
            listing.extend(entries)
            if len(entries) < DEFAULT_GH_REST_PER_PAGE:
                return listing
        raise GitHubOperationError(
            f"The {what} of {self._repo} run past {DEFAULT_GH_MAX_PAGINATED_PAGES} pages, so "
            "the read can't complete.",
            operation="roadmap.read",
            details={"repo": self._repo[:256], "read": what[:256]},
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
    "issue_count_args",
    "issue_search_text",
    "issues_endpoint",
    "listing_page_args",
    "milestones_endpoint",
    "option_update_request",
    "repository_file_args",
]
