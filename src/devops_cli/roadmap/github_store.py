"""The GitHub roadmap store: milestones, Items and board fields read and written through `gh`,
and REST listings read through the GitHub session.

Every gh command goes through an injected runner that defaults to `run_gh`. The REST listings
(milestones, issues, issue events and comments) are read through the session the store is
given, else the process's, with its `paginate()` (#983): it follows GitHub's `Link: rel="next"`,
raises on a page that holds no list and on a listing past its page cap, so a listing never ends
short without saying so, and it requests a page only when the store reads on into it. A
milestone is a planning bucket with any title: the store reads every milestone, identifies it by
its number and orders the milestones by due date, then by number. No title is read as a version.

The board comes from the store's own paged GraphQL query (`board_read`): each read passes a
Projects filter at the source, leaves archived items out, checks the budget first and charges
each page's reported points, and is checked against the total for the same filter, so a short
read is caught; a count that changes during the read is read again once before the read fails.
A poll reads the repository's issue events newest first and stops at the first event older
than the time it reads from, requesting no later page (#1360). The newest commit that changed a
path is one `gh api` read of the commits listing, one commit a page, which the store makes once
for each path (#2005).

The store reads the board listing once for each filter, and the board's fields once, and keeps
both for its life, one command or one Service round (#1361): every reader of a filter shares its
listing, and the store's own writes keep it current with the values they sent and the cards
they add. A write reads only the card it writes, by node id (`RoadmapBoardCard`,
about one point), so the job record it writes joins the one the card holds then, a card gone or
archived raises before any write, and the points that read reports below the reserve refuse the
write. Within one process, `_JOB_RECORD_LOCK` holds each job-record write from that read to its
write, so the Service's two lanes, which open a store each, never write back a record the other
has changed since it was read (#1532).

A field someone changed since the store read the card raises `RoadmapCardChangedError` before
any write, unless the card already holds the value the write sends: the job planned without
that change, and ADR 0002 forbids a revert of it, so the job fails and the next store plans
again. Every board write is `gh project item-edit` by node ids (`--id`, `--project-id`,
`--field-id`, and an option's id), which sends only the mutation; given a card's URL or a
field's name, gh first reads the board's first 100 items with all their field values, about 101
points. `item-add` returns the card it makes (`--format json`), which the store writes to
without a look for it in a listing that can lag the add by minutes. `item-add` names the card an
issue already has, archived or not: the store reads that card once and restores an archived one
with `gh project item-archive --undo`, so it comes back with the fields it holds (#1403).

The board's node id and its fields, with their option ids, colors and descriptions, come from
GraphQL. A GraphQL connection is read in one request of up to its limit, and one longer than
that raises. Issue events carry the Item's job record from the board listing, and those of the
actor a caller leaves out read none.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from datetime import date, datetime
from http import HTTPStatus
from typing import Any, Protocol
from urllib.parse import quote

from pydantic import AliasPath, BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_ISSUE_EVENT_CHANGE_KINDS,
    CONST_GH_PROJECT_ITEM_ISSUE_TYPE,
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
    CONST_GH_PROJECT_SINGLE_SELECT_TYPE,
    CONST_GH_RAW_CONTENT_ACCEPT,
    CONST_ROADMAP_OPEN_ITEMS_FILTER,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_ISSUE_TIMELINE_LIMIT,
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_PROJECT_FIELD_LIMIT,
    DEFAULT_GH_PROJECT_ITEM_PAGE_POINTS,
    DEFAULT_GH_PROJECT_OPTION_COLOR,
    DEFAULT_GH_REST_PER_PAGE,
)
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.github.error_classifier import (
    classify_gh_failure,
    gh_http_status,
    is_gh_owner_lookup_failure,
)
from devops_cli.github.owner_lookup import owner_lookup_failure
from devops_cli.github.rate_limiter import gh_request_resource, run_gh
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.board_read import (
    BoardBudgetPayload,
    BoardCardPayload,
    BoardItemsPage,
    GraphQLBudget,
    GraphQLBudgetPayload,
    GraphQLSpend,
    board_budget_args,
    board_card_args,
    board_items_args,
    graphql_budget_args,
    item_list_key,
    read_cost,
    require_budget,
    require_floor,
    require_write_floor,
    spend_between,
)
from devops_cli.roadmap.store import (
    AddedItem,
    BoardEntry,
    BoardField,
    Candidate,
    Change,
    ChangeKind,
    Closure,
    Evidence,
    EvidenceKind,
    FieldOption,
    GitHubState,
    IssueComment,
    IssueRecord,
    Item,
    ItemField,
    JobRecord,
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
    with_marks,
)

logger = logging.getLogger(__name__)

_JOB_RECORD_LOCK = threading.Lock()
"""Held from the read of a card to the write of its job record, across every store in the
process: the Service's lanes each open a store, and mark the same cards (#1532)."""


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


class ListingSession(Protocol):
    """Reads a REST listing page by page, as `GitHubSession.paginate` does (#983)."""

    def paginate(self, path: str, *, iterable_key: str | None = ...) -> Iterator[Any]: ...


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

    def milestone(self) -> Milestone:
        return Milestone(
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
    milestone: str | None = Field(default=None, validation_alias=AliasPath("milestone", "title"))
    pull_request: dict[str, Any] | None = None
    author_association: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    sub_issues: int = Field(default=0, validation_alias=AliasPath("sub_issues_summary", "total"))

    def record(self) -> IssueRecord:
        return IssueRecord(
            number=self.number,
            title=self.title,
            url=self.html_url,
            body=self.body or "",
            state=self.state,
            state_reason=self.state_reason,
            labels=tuple(label.name for label in self.labels),
            milestone=self.milestone,
            pull_request=self.pull_request is not None,
            author_association=self.author_association,
            created_at=self.created_at,
            updated_at=self.updated_at,
            closed_at=self.closed_at,
            sub_issues=self.sub_issues,
        )


class _EventPayload(BaseModel):
    event: str
    created_at: datetime
    number: int | None = Field(default=None, validation_alias=AliasPath("issue", "number"))
    pull_request: dict[str, Any] | None = Field(
        default=None, validation_alias=AliasPath("issue", "pull_request")
    )
    actor: str | None = Field(default=None, validation_alias=AliasPath("actor", "login"))
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
            label=self.label,
        )


class _IsPrivatePayload(BaseModel):
    is_private: bool = Field(validation_alias=AliasPath("data", "repository", "isPrivate"))


class _CommentPayload(BaseModel):
    body: str = ""
    created_at: datetime

    def comment(self) -> IssueComment:
        return IssueComment(body=self.body, created_at=self.created_at)


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


class _CommitPayload(BaseModel):
    """A commit as the commits listing gives it: when its committer made it."""

    committed_at: datetime = Field(validation_alias=AliasPath("commit", "committer", "date"))


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

    def is_issue_of(self, repo: str) -> bool:
        """Report whether this item is an issue of `repo`, not a pull request, draft or other repo's."""
        return (
            self.content_type == CONST_GH_PROJECT_ITEM_ISSUE_TYPE
            and self.content_number is not None
            and (self.content_repository or "").lower() == repo.lower()
        )

    def values(self) -> dict[str, Any]:
        """The card's board fields and job record, keyed as `BoardEntry` holds them."""
        fields = {f.name.lower(): self.field_value(f.value) for f in ItemField}
        return fields | {"job_record": decode_job_record(self.job_record_text(), card=self.name())}

    def field_value(self, field_name: str) -> str | None:
        """The value the card holds for the board field `field_name`, None when it has none."""
        return _text_value((self.model_extra or {}).get(item_list_key(field_name)))

    def name(self) -> str:
        """The card as an error names it: its issue's number, or its node id."""
        return f"#{self.content_number}" if self.content_number else f"card {self.id}"

    def job_record_text(self) -> str | None:
        """The job record as the board's text field holds it."""
        return self.field_value(CONST_GH_PROJECT_JOB_RECORD_FIELD)

    def recorded(self, changes: JobRecord) -> str:
        """The job record with `changes` made, as the text field takes it, keeping every key of
        the record held now that this version does not know."""
        held = self.job_record_text()
        record = decode_job_record(held, card=self.name()) | dict(changes)
        return encode_job_record(record, over=held, card=self.name())

    def entry(self) -> BoardEntry:
        """The board's fields and job record for this issue, with its card's node id."""
        return BoardEntry.model_validate(
            self.values() | {"number": self.content_number, "card_id": self.id}
        )

    def written(self, field_name: str, value: str | None) -> _BoardItemPayload:
        """The card as it is once the store has written `value` to the field `field_name`."""
        return self.model_copy(update={item_list_key(field_name): value})


class _AddedCardPayload(BaseModel):
    """What `gh project item-add` or `item-archive --undo` prints with `--format json`: the card
    it named or restored."""

    id: str


class _BoardFieldPayload(BaseModel):
    name: str
    options: list[_NamedPayload] = Field(default_factory=list)


class FieldListingPayload(BaseModel):
    """The reply to `field_list_args`: every board field, with its options by name. Project
    reconcile reads it (#892); the store reads its fields through GraphQL instead."""

    fields: list[_BoardFieldPayload]
    total_count: int = Field(alias="totalCount")

    def options(self) -> dict[str, tuple[str, ...]]:
        """Each field's option names by field name; a field that is not single-select has none."""
        return {field.name: tuple(option.name for option in field.options) for field in self.fields}


class _OptionPayload(BaseModel):
    id: str
    name: str
    color: str = DEFAULT_GH_PROJECT_OPTION_COLOR
    description: str = ""


class _FieldNodePayload(BaseModel):
    """A board field as GraphQL gives it; a field that is not single-select has no options."""

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
    board_id: str = Field(validation_alias=AliasPath("data", "repositoryOwner", "projectV2", "id"))
    fields: _FieldConnectionPayload = Field(
        validation_alias=AliasPath("data", "repositoryOwner", "projectV2", "fields")
    )


class _BoardSchema(BaseModel):
    """The board's node id and its fields, which every write addresses by id."""

    model_config = ConfigDict(frozen=True)

    board_id: str
    fields: tuple[BoardField, ...]

    def options(self) -> dict[str, tuple[str, ...]]:
        """Each field's option names by field name."""
        return field_options(self.fields)

    def field(self, name: str, operation: str) -> BoardField:
        """The field named `name`, raising when the board has none."""
        return require_field(self.fields, name, operation)


_MILESTONE = TypeAdapter(_MilestonePayload)
_ISSUE = TypeAdapter(_IssuePayload)
_EVENT = TypeAdapter(_EventPayload)
_BOARD_PAGE = TypeAdapter(BoardItemsPage)
_BOARD_BUDGET = TypeAdapter(BoardBudgetPayload)
_GRAPHQL_BUDGET = TypeAdapter(GraphQLBudgetPayload)
_BOARD_ITEMS = TypeAdapter(list[_BoardItemPayload])
_BOARD_ITEM = TypeAdapter(_BoardItemPayload)
_BOARD_CARD = TypeAdapter(BoardCardPayload)
_ADDED_CARD = TypeAdapter(_AddedCardPayload)
_JOB_RECORD = TypeAdapter(JobRecord)
# The job record keys this version reads; the others are another version's, kept as they are.
_JOB_RECORD_KEYS = frozenset(key.value for key in (*ItemField, *RefineRecordKey))
_BOARD_FIELDS = TypeAdapter(_BoardFieldsPayload)
_IS_PRIVATE = TypeAdapter(_IsPrivatePayload)
_COMMENT = TypeAdapter(_CommentPayload)
_TIMELINE = TypeAdapter(_TimelinePayload)
_WORKFLOW_RUN = TypeAdapter(_WorkflowRunPayload)
_COMMITS = TypeAdapter(list[_CommitPayload])
_ANY_OBJECT = TypeAdapter(dict[str, Any])

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
    selection=f"id fields(first: $first) {{ totalCount nodes {{ {_FIELD_SELECTION} }} }}"
)
_REPOSITORY = (
    "query($owner: String!, $name: String!{params}) {{ "
    "repository(owner: $owner, name: $name) {{ {selection} }} }}"
)
_IS_PRIVATE_QUERY = _REPOSITORY.format(params="", selection="isPrivate")
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


def _text_value(raw: object) -> str | None:
    return raw if isinstance(raw, str) and raw else None


def _malformed_job_record(text: str, card: str) -> GitHubOperationError:
    return GitHubOperationError(
        f"The job record of {card} is not a JSON object whose known keys hold text, so the "
        f"store cannot tell what a job set on it: {text[:256]!r}. Clear the card's "
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

    A key it does not know, such as one another version writes, is left out here and kept by
    every write (`encode_job_record`). A record that is not a JSON object, or gives a known key
    a value that is not text or null, raises: read as empty, it would make its Item look as if
    no job had ever set a field on it.
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
    record it replaces (`over`) that this version does not know."""
    found = _record_object(over, card) if over else {}
    kept = {key: value for key, value in found.items() if key not in _JOB_RECORD_KEYS}
    return json.dumps(kept | {key.value: value for key, value in record.items()}, sort_keys=True)


def _wire_value(value: str | date) -> str:
    """A milestone field as GitHub's REST API takes it; a due date becomes a timestamp."""
    return f"{value.isoformat()}T00:00:00Z" if isinstance(value, date) else str(value)


def repository_file_args(repo: str, path: str, *, ref: str | None) -> list[str]:
    """The `gh` arguments that read the raw text of `path` on `ref` through the contents API."""
    query = f"?ref={quote(ref, safe='')}" if ref else ""
    return ["api", "-H", CONST_GH_RAW_CONTENT_ACCEPT, f"repos/{repo}/contents/{quote(path)}{query}"]


def milestones_endpoint(repo: str) -> str:
    """The REST listing of every milestone of `repo`, open and closed."""
    return f"repos/{repo}/milestones?state=all"


def issues_endpoint(repo: str, query: str = "state=all") -> str:
    """The REST listing of `repo`'s issues that `query` selects, every one by default."""
    return f"repos/{repo}/issues?{query}"


def listing_path(endpoint: str, per_page: int = DEFAULT_GH_REST_PER_PAGE) -> str:
    """The path the GitHub session reads the REST listing `endpoint` from, `per_page` entries
    a page, a full page by default; the session follows each page's `Link: rel="next"`."""
    separator = "&" if "?" in endpoint else "?"
    return f"/{endpoint}{separator}per_page={per_page}"


# The argument builders below are pure: the store runs what they return, and a dry run's request
# plan (`roadmap/request_plan.py`) lists the same argv with a placeholder in angle brackets
# wherever a value needs a read (#1125). A number may be given as such a placeholder.
Number = int | str


def _segment(value: str) -> str:
    """`value` as one URL path segment; a placeholder stays readable."""
    return value if value.startswith("<") and value.endswith(">") else quote(value, safe="")


def repository_query_args(repo: str, query: str, **variables: Number) -> list[str]:
    """A GraphQL read about `repo`, with its integer variables."""
    owner, name = repo.split("/", 1)
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
    ] + typed


def board_query_args(query: str, owner: str, number: Number, first: int) -> list[str]:
    """A GraphQL read about board `number` of `owner`, asking for up to `first` nodes."""
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


def board_fields_args(owner: str, number: Number) -> list[str]:
    """The GraphQL read of board `number`'s node id and fields, with each option's id, color and
    description; it reads no item, so it costs about one point."""
    return board_query_args(_FIELDS_QUERY, owner, number, DEFAULT_GH_PROJECT_FIELD_LIMIT)


def field_list_args(owner: str, number: Number) -> list[str]:
    """`gh project field-list`: every board field's options by name. gh also reads the board's
    first 100 items with every field value (about 101 points), so the store never sends it;
    project reconcile does (#892)."""
    limit = str(DEFAULT_GH_PROJECT_FIELD_LIMIT)
    return [
        "project",
        "field-list",
        str(number),
        "--owner",
        owner,
        "--format",
        "json",
        "--limit",
        limit,
    ]


def item_add_args(owner: str, number: Number, url: str) -> list[str]:
    """`gh project item-add` of the issue at `url`, printing the card it adds, or the card the
    issue already has."""
    return ["project", "item-add", str(number), "--owner", owner, "--url", url, "--format", "json"]


def item_edit_args(
    owner: str, number: Number, url: str, field_name: str, change: Sequence[str]
) -> list[str]:
    """`gh project item-edit` on the issue at `url`, by the field's name. gh resolves both names
    with a read of the board's first 100 items with every field value (about 101 points), so the
    store edits by node ids (`card_edit_args`); project reconcile sends this (#892)."""
    return [
        "project",
        "item-edit",
        str(number),
        "--owner",
        owner,
        "--url",
        url,
        "--field",
        field_name,
        *change,
    ]


def card_edit_args(
    card_id: str, project_id: str, field_id: str, change: Sequence[str]
) -> list[str]:
    """`gh project item-edit` on any card, by node ids: gh sends only the mutation."""
    return [
        "project",
        "item-edit",
        "--id",
        card_id,
        "--project-id",
        project_id,
        "--field-id",
        field_id,
        *change,
    ]


def item_unarchive_args(owner: str, number: Number, card_id: str) -> list[str]:
    """`gh project item-archive --undo` of card `card_id`, printing the card it restores."""
    return [
        "project",
        "item-archive",
        str(number),
        "--owner",
        owner,
        "--id",
        card_id,
        "--undo",
        "--format",
        "json",
    ]


GRAPHQL_INPUT_ARGS: tuple[str, ...] = ("api", "graphql", "--input", "-")
"""A GraphQL write, its request on stdin."""


def graphql_request(query: str, variables: Mapping[str, Any]) -> str:
    """The stdin of a `GRAPHQL_INPUT_ARGS` write."""
    return json.dumps({"query": query, "variables": dict(variables)})


def issue_args(repo: str, number: Number) -> list[str]:
    return ["api", f"repos/{repo}/issues/{number}"]


def repository_issue_events_endpoint(repo: str) -> str:
    """The REST listing of every issue event of `repo`, newest first."""
    return f"repos/{repo}/issues/events"


def comments_endpoint(repo: str, number: Number) -> str:
    return f"repos/{repo}/issues/{number}/comments"


def milestone_edit_args(repo: str, number: Number, fields: Sequence[tuple[str, str]]) -> list[str]:
    """The REST write that changes `fields` of milestone `number`."""
    flags = [part for name, value in fields for part in ("-f", f"{name}={value}")]
    return ["api", "-X", "PATCH", f"repos/{repo}/milestones/{number}", *flags]


def create_issue_args(repo: str, title: str, body: str, labels: Sequence[str] = ()) -> list[str]:
    fields = [("title", title), ("body", body), *(("labels[]", label) for label in labels)]
    flags = [part for name, value in fields for part in ("-f", f"{name}={value}")]
    return ["api", "-X", "POST", f"repos/{repo}/issues", *flags]


def write_issue_body_args(repo: str, number: Number, body: str) -> list[str]:
    """The `gh` arguments that write `body` as the body of issue `number`."""
    return ["api", "-X", "PATCH", f"repos/{repo}/issues/{number}", "-f", f"body={body}"]


def comment_args(repo: str, number: Number, body: str) -> list[str]:
    return ["api", "-X", "POST", comments_endpoint(repo, number), "-f", f"body={body}"]


def label_args(repo: str, number: Number, label: str) -> list[str]:
    return ["api", "-X", "POST", f"repos/{repo}/issues/{number}/labels", "-f", f"labels[]={label}"]


def advisory_args(value: str) -> list[str]:
    return ["api", f"advisories/{_segment(value)}"]


def workflow_run_args(repo: str, value: str) -> list[str]:
    return ["api", f"repos/{repo}/actions/runs/{_segment(value)}"]


def commit_args(repo: str, value: str) -> list[str]:
    return ["api", f"repos/{repo}/commits/{_segment(value)}"]


def path_commits_args(repo: str, path: str) -> list[str]:
    """The `gh` arguments that read the newest commit on the default branch that changed
    `path`: the commits listing gives the newest first, and one a page."""
    return ["api", f"repos/{repo}/commits?path={_segment(path)}&per_page=1"]


def is_private_args(repo: str) -> list[str]:
    """The `gh` arguments that query whether `repo` is private."""
    return repository_query_args(repo, _IS_PRIVATE_QUERY)


def closures_args(repo: str, number: Number) -> list[str]:
    return repository_query_args(
        repo, _CLOSURES_QUERY, first=DEFAULT_GH_ISSUE_TIMELINE_LIMIT, number=number
    )


# ── Adapter ───────────────────────────────────────────────────────────────────


class GitHubRoadmapStore(RoadmapStore):
    """The roadmap on GitHub, read and written as whoever `gh` is logged in as.

    Without a board, milestone operations work, and Item reads and writes raise. One store lives
    for one command or one Service round: it keeps the board's fields, and the listing of each
    filter it read, for its life.
    """

    def __init__(
        self,
        repo: str,
        *,
        board_owner: str | None = None,
        board_number: int | None = None,
        runner: GhRunner = run_gh,
        session: ListingSession | None = None,
        board_filter: str = "",
    ) -> None:
        self._repo = repo
        # The REST listings are read through this session, or the process's when it is None.
        self._session = session
        self._board_filter = board_filter
        # The first and last GraphQL budgets a response reported, and what a board page cost.
        self._first_budget: GraphQLBudget | None = None
        self._last_budget: GraphQLBudget | None = None
        # Whether the store has sent a GraphQL request, as `run_gh` paces it (#1400).
        self._sent_graphql = False
        self._page_points = DEFAULT_GH_PROJECT_ITEM_PAGE_POINTS
        self._board: tuple[str, int] | None = (
            (board_owner, board_number) if board_owner and board_number else None
        )
        self._runner = runner
        # The board's node id and fields, and its listing by filter, read once when first needed.
        self._schema: _BoardSchema | None = None
        self._listings: dict[str, list[_BoardItemPayload]] = {}
        # When the newest commit that changed each path refine reads was made (#2005).
        self._path_changes: dict[str, datetime | None] = {}

    # ── Milestones ──

    def milestones(self) -> list[Milestone]:
        """Every milestone, open and closed, by due date and then by number."""
        listing = self._listing(milestones_endpoint(self._repo), _MILESTONE, "milestones")
        return sorted((payload.milestone() for payload in listing), key=milestone_order)

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
        """Change only the given fields of the milestone `name` names, raising if there is none."""
        milestones = self.milestones()
        current = require_milestone(milestones, name, "roadmap.milestone.edit")
        edits = milestone_edits(
            milestones, current, title=title, description=description, due_on=due_on, state=state
        )
        if not edits:
            return current
        wire = [(field_name, _wire_value(value)) for field_name, value in edits.items()]
        action = f"edit milestone #{current.number}"
        written = self._write(milestone_edit_args(self._repo, current.number, wire), action)
        return self._validate(written, _MILESTONE, f"milestone after {action}").milestone()

    def close_milestone(self, name: str) -> Milestone:
        """Close the milestone `name` names, raising if there is none."""
        return self.edit_milestone(name, state=GitHubState.CLOSED)

    # ── Items ──

    def item(self, number: int) -> Item | None:
        """The Item numbered `number`, or None when that issue is not on the board."""
        board = self._read_board()
        if number not in board:
            return None
        issue = self._read_issue(number)
        return next(iter(join_items([issue.record()], board)), None)

    def items(self, *, milestone: int | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the milestone numbered `milestone`."""
        board = self._read_board()
        query = "state=all" if milestone is None else f"milestone={milestone}&state=all"
        return join_items(self._read_issues(query), board)

    def backlog(self) -> list[Item]:
        """The open Items in no milestone."""
        board = self._read_board(CONST_ROADMAP_OPEN_ITEMS_FILTER)
        return join_items(self._read_issues("milestone=none&state=open"), board)

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""
        board = self._read_board(CONST_ROADMAP_OPEN_ITEMS_FILTER)
        return select_candidates(self._read_issues("state=open"), board)

    def changes_since(self, since: datetime, *, except_actor: str | None = None) -> list[Change]:
        """The Item changes the issue events report at or after `since`, oldest first (#1360).
        Those `except_actor` made are left out before any job record is read; an empty actor
        leaves out nothing."""
        cutoff = as_utc(since)
        skipped = except_actor or None
        events = self._listing(
            repository_issue_events_endpoint(self._repo),
            _EVENT,
            "issue events",
            ends=lambda event: event.created_at < cutoff,
        )
        changes = [
            change
            for event in reversed(events)
            if (change := event.change()) is not None
            and change.at >= cutoff
            and (skipped is None or change.actor != skipped)
        ]
        return self._with_job_records(changes)

    def add_item(self, number: int) -> AddedItem:
        """Put issue `number` on the board and return its Item, raising if it is not an issue
        of this repository. The card is the one `item-add` names, the issue's own when it is on
        the board already, restored and marked `restored` when it is archived, and its fields
        come from one read of that card, never from the board listing, which can show a new card
        minutes late."""
        owner, board_number = self._require_board()
        issue = self._read_issue(number)
        if issue.pull_request is not None:
            raise GitHubOperationError(
                f"#{number} in {self._repo} is a pull request, and only issues are Items.",
                operation="roadmap.item.add",
                details={"repo": self._repo[:256], "number": number},
            )
        written = self._write(
            item_add_args(owner, board_number, issue.html_url), f"add #{number} to the board"
        )
        added = self._validate(written, _ADDED_CARD, f"card of #{number} after it was added")
        card, restored = self._active_card(added.id, number)
        self._added(card, is_open=issue.state is GitHubState.OPEN)
        item = join_items([issue.record()], {number: card.entry()})[0]
        return AddedItem.model_validate(item.model_dump() | {"restored": restored})

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[Any, str | None] | None = None,
    ) -> None:
        """Record the value in the Item's job record, with `marks`, then set or clear the field.

        GitHub takes the two as separate calls, and the record goes first: a run that stops
        between them leaves the field as it was and the record naming the job's value, never
        a field the job changed with no record of it. The value joins the job record the card
        holds now, read by its node id just before the write, not the one `item` was read with,
        so two writes from one read both stay recorded. A board field someone changed since the
        store read the card raises before any write, unless the card already holds `value`, so
        a job never reverts a change it did not see (ADR 0002).
        """
        operation = "roadmap.item.set_field"
        options = self._read_schema().options()
        require_job_record_field(options)
        require_option(options, field, value)
        with _JOB_RECORD_LOCK:
            card = self._require_entry(item, operation, field, value)
            text = card.recorded(with_marks({field: value}, marks or {}))
            card = self._edit_card(card, CONST_GH_PROJECT_JOB_RECORD_FIELD, text, operation)
            self._edit_card(card, field.value, value, operation)

    def set_marks(self, item: Item, marks: Mapping[Any, str | None]) -> None:
        """Set or clear a job's marks in the Item's job record, as its card holds it now, in one
        write."""
        operation = "roadmap.item.set_marks"
        require_job_record_field(self._read_schema().options())
        with _JOB_RECORD_LOCK:
            card = self._require_entry(item, operation)
            text = card.recorded(with_marks({}, marks))
            self._edit_card(card, CONST_GH_PROJECT_JOB_RECORD_FIELD, text, operation)

    # ── Issues ──

    def issues(self) -> list[IssueRecord]:
        """Every issue, open and closed, on the board or not; never pull requests."""
        return [issue for issue in self._read_issues("state=all") if not issue.pull_request]

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""
        written = self._write(
            create_issue_args(self._repo, title, body, labels), f"open the issue {title[:64]!r}"
        )
        return self._validate(written, _ISSUE, "issue after it was opened").record()

    def read_issue_body(self, number: int) -> str:
        """The body of issue `number`, raising if it is not an issue of this repository."""
        issue = self._read_issue(number)
        if issue.pull_request is not None:
            raise GitHubOperationError(
                f"#{number} in {self._repo} is a pull request, not an issue.",
                operation="roadmap.issue.read_body",
                details={"repo": self._repo[:256], "number": number},
            )
        return issue.body or ""

    def write_issue_body(self, number: int, body: str) -> None:
        """Write `body` as the body of issue `number`, raising if it is not an issue of this repository."""
        if self._read_issue(number).pull_request is not None:
            raise GitHubOperationError(
                f"#{number} in {self._repo} is a pull request, not an issue.",
                operation="roadmap.issue.write_body",
                details={"repo": self._repo[:256], "number": number},
            )
        self._write(write_issue_body_args(self._repo, number, body), f"write body of #{number}")

    def comments_on(self, number: int) -> list[IssueComment]:
        """Every comment on issue `number`, oldest first."""
        listing = self._listing(
            comments_endpoint(self._repo, number), _COMMENT, f"#{number} comments"
        )
        return [comment.comment() for comment in listing]

    def path_changed_at(self, path: str) -> datetime | None:
        """When the newest commit on the default branch that changed `path` was made, or None
        when no commit changed it, read once for the store's life (#2005)."""
        if path not in self._path_changes:
            commits = self._read(
                path_commits_args(self._repo, path), _COMMITS, f"the commits of {path}"
            )
            self._path_changes[path] = commits[0].committed_at if commits else None
        return self._path_changes[path]

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""
        self._write(comment_args(self._repo, number, body), f"comment on #{number}")

    # ── What intake reads and writes ──

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number` from its timeline, oldest first."""
        timeline = self._read(closures_args(self._repo, number), _TIMELINE, f"#{number} timeline")
        self._require_whole(len(timeline.nodes), timeline.total_count, f"#{number} closes")
        return [node.closure() for node in timeline.nodes]

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue `number`; GitHub keeps its other labels."""
        self._write(label_args(self._repo, number, label), f"label #{number} {label}")

    def evidence_holds(self, evidence: Evidence) -> bool:
        """Whether GitHub confirms the evidence. The value is one path segment of its endpoint,
        so no value reaches another resource; a commit GitHub cannot resolve answers 422."""
        if evidence.kind is EvidenceKind.ADVISORY:
            return (
                self._read_or_none(advisory_args(evidence.value), _ANY_OBJECT, "advisory")
                is not None
            )
        if evidence.kind is EvidenceKind.FAILED_RUN:
            run = self._read_or_none(
                workflow_run_args(self._repo, evidence.value), _WORKFLOW_RUN, "run"
            )
            return run is not None and run.conclusion == "failure"
        commit = self._read_or_none(
            commit_args(self._repo, evidence.value),
            _ANY_OBJECT,
            "commit",
            absent=(HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY),
        )
        return commit is not None

    def repository_file(self, path: str, *, ref: str | None = None) -> str:
        """The raw text of `path` on `ref` through the contents API, raising when it cannot be read."""
        proc = self._run(repository_file_args(self._repo, path, ref=ref))
        where = f"{path} at {ref or 'the default branch'}"
        if proc.returncode == 0:
            return proc.stdout or ""
        if gh_http_status(proc.stderr or "") == HTTPStatus.NOT_FOUND:
            raise GitHubFileNotFoundError(
                f"{self._repo} has no {where}.",
                operation="roadmap.read",
                details={"repo": self._repo[:256], "path": path[:256]},
            )
        raise self._failure(proc, f"read {where}", "roadmap.read")

    def repository_is_private(self) -> bool:
        """Whether the repository is private."""
        return self._read(
            is_private_args(self._repo), _IS_PRIVATE, f"{self._repo} visibility"
        ).is_private

    # ── Writes ──

    def _with_job_records(self, changes: list[Change]) -> list[Change]:
        """The changes, each with its Item's job record from the board, when one is configured.
        A poll that finds no change reads no board."""
        if self._board is None or not changes:
            return changes
        board = self._read_board()
        return [
            change.model_copy(update={"job_record": board[change.number].job_record})
            if change.number in board
            else change
            for change in changes
        ]

    def _require_entry(
        self, item: Item, operation: str, field: ItemField | None = None, value: str | None = None
    ) -> _BoardItemPayload:
        """The Item's card as it is now, read by its node id, raising before any write when the
        Item has none, or it is gone, archived or another issue's, when the points left are
        below the reserve, or when someone changed `field` since the store read the card."""
        return self._require_card_node(
            item.card_id,
            f"#{item.number}",
            operation,
            number=item.number,
            field=field,
            value=value,
            held=None if field is None else item.field_value(field),
        )

    def _require_card_node(
        self,
        card_id: str | None,
        name: str,
        operation: str,
        *,
        number: int | None = None,
        field: ItemField | None = None,
        value: str | None = None,
        held: str | None = None,
    ) -> _BoardItemPayload:
        """The card `card_id` as it is now, from one read by its node id, raising before any
        write when it is gone or archived, or not issue `number`'s when one is given, when that
        read leaves fewer points than the reserve, or when the write of `value` to `field` would
        revert a change made since the store read the card: the value read is the card's in the
        store's listings, which its own writes keep current, or `held`, the caller's, when no
        listing holds the card. The listings take the card's job record as it is now, and keep
        its fields as the store read them."""
        if not card_id:
            raise self._not_on_board(name, operation)
        card, budget = self._read_card(card_id, name)
        if card is None:
            raise self._not_on_board(name, operation)
        require_write_floor(budget, name)
        if number is not None and not (
            card.is_issue_of(self._repo) and card.content_number == number
        ):
            raise self._not_on_board(name, operation)
        if field is not None:
            read = {listed.field_value(field.value) for listed in self._listed(card.id)}
            now = card.field_value(field.value)
            require_unchanged(card.name(), field, read or {held}, now, value, operation)
        self._remember(card.id, CONST_GH_PROJECT_JOB_RECORD_FIELD, card.job_record_text())
        return card

    def _active_card(self, card_id: str, number: int) -> tuple[_BoardItemPayload, bool]:
        """Card `card_id`, which `item-add` named for issue `number`, from one read by its node
        id, restored with `item-archive --undo` when it is archived, and whether it was;
        raising when it is gone or another issue's, when the read leaves fewer points than the
        reserve before a restore, or when the restore names another card. A person archived it,
        as nothing here archives a card: the restore undoes only that, and the card keeps its
        fields (#1403)."""
        owner, board_number = self._require_board()
        read = self._read_card_node(card_id, f"#{number}")
        card = self._card_payload(read.listed(archived=True), f"#{number}")
        if card is None or card.content_number != number:
            raise GitHubOperationError(
                f"Board #{board_number} does not hold card {card_id} that #{number} was just "
                "added as.",
                operation="roadmap.item.add",
                details={"repo": self._repo[:256], "number": number, "card": card_id[:256]},
            )
        if read.is_archived():
            require_write_floor(read.rate_limit, f"#{number}")
            written = self._write(
                item_unarchive_args(owner, board_number, card_id),
                f"restore the archived card of #{number}",
            )
            restored = self._validate(written, _ADDED_CARD, f"card of #{number} it restored")
            if restored.id != card_id:
                raise GitHubOperationError(
                    f"Restoring card {card_id} of #{number} on board #{board_number} answered "
                    f"with card {restored.id[:256]}.",
                    operation="roadmap.item.add",
                    details={"repo": self._repo[:256], "number": number, "card": card_id[:256]},
                )
        return card, read.is_archived()

    def _read_card(self, card_id: str, name: str) -> tuple[_BoardItemPayload | None, GraphQLBudget]:
        """Card `card_id` from one GraphQL read by its node id, None when GitHub holds no such
        card or it is archived, and the budget the read reported; any other failure raises."""
        read = self._read_card_node(card_id, name)
        return self._card_payload(read.listed(), name), read.rate_limit

    def _read_card_node(self, card_id: str, name: str) -> BoardCardPayload:
        """GitHub's answer to one read of card `card_id` by its node id, its budget noted; a
        failure other than GitHub holding no such card raises."""
        what = f"the card of {name}"
        proc = self._run(board_card_args(card_id))
        if proc.returncode == 0:
            read = self._validate(proc.stdout or "", _BOARD_CARD, what)
        else:
            read = self._gone_card(proc, what)
        self._note_budget(read.rate_limit)
        return read

    def _card_payload(self, listed: dict[str, Any] | None, name: str) -> _BoardItemPayload | None:
        """A card read's item as the store holds a listed card, or None."""
        if listed is None:
            return None
        return self._validate(json.dumps(listed), _BOARD_ITEM, f"the card of {name}")

    def _gone_card(self, proc: subprocess.CompletedProcess[str], what: str) -> BoardCardPayload:
        """A failed card read's answer when GitHub says only that the node does not exist, which
        `gh` reports by exiting 1 with the answer on stdout; any other failure raises."""
        try:
            read = _BOARD_CARD.validate_json(proc.stdout or "")
        except MalformedPayloadError:
            raise self._failure(proc, f"read {what}", "roadmap.read") from None
        if not read.is_gone():
            raise self._failure(proc, f"read {what}", "roadmap.read")
        return read

    def _not_on_board(self, name: str, operation: str) -> GitHubOperationError:
        return GitHubOperationError(
            f"{name} is not on the board.",
            operation=operation,
            details={"repo": self._repo[:256], "card": name[:256]},
        )

    def _edit_card(
        self, card: _BoardItemPayload, field_name: str, value: str | None, operation: str
    ) -> _BoardItemPayload:
        """Write `value` to the board field `field_name` on `card` by node ids: text for the job
        record, an option's id for a single-select field, a clear for None. The listings the
        store holds take the value it sent."""
        schema = self._read_schema()
        board_field = schema.field(field_name, operation)
        self._write(
            card_edit_args(card.id, schema.board_id, board_field.id, _change(board_field, value)),
            f"set {field_name} on {card.name()}",
        )
        self._remember(card.id, field_name, value)
        return card.written(field_name, value)

    def _listed(self, card_id: str) -> list[_BoardItemPayload]:
        """Card `card_id` in each listing the store holds it in, as the store read it."""
        return [
            listed for items in self._listings.values() for listed in items if listed.id == card_id
        ]

    def _remember(self, card_id: str, field_name: str, value: str | None) -> None:
        """Hold `value` as card `card_id`'s field `field_name` in every listing the store holds
        the card in; its other fields stay as the store read them."""
        for listing in self._listings.values():
            listing[:] = [
                listed.written(field_name, value) if listed.id == card_id else listed
                for listed in listing
            ]

    def _added(self, card: _BoardItemPayload, *, is_open: bool) -> None:
        """Hold a card the store added in each listing that selects it: the unfiltered one,
        which selects every card not archived, and the open items' when its issue is open; a
        listing that already holds the card keeps it as the store read it. Any other listing,
        whose filter the store cannot judge, is read again when next needed."""
        kept = {"", CONST_ROADMAP_OPEN_ITEMS_FILTER} if is_open else {""}
        self._listings = {
            query: listing if any(listed.id == card.id for listed in listing) else [*listing, card]
            for query, listing in self._listings.items()
            if query in kept
        }

    def _write(self, args: list[str], action: str) -> str:
        proc = self._run(args)
        if proc.returncode != 0:
            raise self._failure(proc, action, "roadmap.write")
        return proc.stdout or ""

    # ── Reads ──

    def _require_board(self) -> tuple[str, int]:
        if self._board is None:
            raise GitHubOperationError(
                f"No board is configured for {self._repo}, so its Items cannot be read or written.",
                operation="roadmap.board",
                details={"repo": self._repo[:256]},
            )
        return self._board

    def _read_board_listing(self, board_filter: str | None = None) -> list[_BoardItemPayload]:
        """The board's items that `board_filter`, or the job's filter, selects, archived ones
        left out: read the first time the store needs that filter, and kept for its life."""
        query = self._board_filter if board_filter is None else board_filter
        if query not in self._listings:
            self._listings[query] = self._fetch_board_listing(query)
        return self._listings[query]

    def _fetch_board_listing(self, query: str) -> list[_BoardItemPayload]:
        """One read of the items `query` selects, refusing before any page when the budget cannot
        cover the read and raising on a short read. A count that changes during the read is read
        again once."""
        owner, number = self._require_board()
        texts = MESSAGES.roadmap
        what = (
            texts.board_items_filtered.format(number=number, query=query)
            if query
            else texts.board_items.format(number=number)
        )
        probe = self._read(board_budget_args(owner, number, query), _BOARD_BUDGET, what)
        self._note_budget(probe.rate_limit)
        require_budget(
            probe.rate_limit, read_cost(probe.items.total_count, self._page_points), what
        )
        counts: list[int] = []
        for attempt in range(2):
            listing, totals = self._read_board_pages(owner, number, query, what)
            counts.extend(totals)
            if set(totals) == {len(listing)}:
                return self._validate(json.dumps(listing), _BOARD_ITEMS, what)
            if attempt == 0:
                logger.info(texts.board_reread.format(what=what, counts=_counts(totals, listing)))
        if len(set(counts)) == 1:
            self._require_whole(len(listing), counts[0], what)
        raise GitHubOperationError(
            texts.board_count_changed.format(what=what, counts=_counts(counts, listing)),
            operation="roadmap.read",
            details={"repo": self._repo[:256], "counts": counts[:16]},
        )

    def _read_board_pages(
        self, owner: str, number: int, query: str, what: str
    ) -> tuple[list[dict[str, Any]], list[int]]:
        """Every page of one read, each item once by its id, and the total each page reported.

        Before each page after the first, a read with fewer points left than the floor stops.
        """
        listing: dict[str, dict[str, Any]] = {}
        totals: list[int] = []
        after: str | None = None
        for page in range(1, DEFAULT_GH_MAX_PAGINATED_PAGES + 1):
            if page > 1 and self._last_budget is not None:
                require_floor(self._last_budget, what, page)
            read = self._read(
                board_items_args(owner, number, query, after=after),
                _BOARD_PAGE,
                f"{what} (page {page})",
            )
            self._note_budget(read.rate_limit)
            self._page_points = max(self._page_points, read.rate_limit.cost)
            totals.append(read.items.total_count)
            listing.update((entry["id"], entry) for entry in read.listed())
            after = read.next_cursor()
            if after is None:
                return list(listing.values()), totals
        raise GitHubOperationError(
            f"The {what} run past {DEFAULT_GH_MAX_PAGINATED_PAGES} pages, so the read cannot "
            "complete.",
            operation="roadmap.read",
            details={"repo": self._repo[:256], "read": what[:256]},
        )

    def _note_budget(self, budget: GraphQLBudget) -> None:
        """Keep the first and last GraphQL budgets a response reported."""
        self._first_budget = self._first_budget or budget
        self._last_budget = budget

    def graphql_spend(self, *, read: bool = True) -> GraphQLSpend | None:
        """The GraphQL points this store's run spent and the points left, read from GraphQL;
        None, with no request sent, when the store has sent no GraphQL request (#1400). With
        `read` False, as after a budget refusal, the spend runs to the last budget a response
        reported, and no request is sent; None when no response reported one."""
        if not self._sent_graphql:
            return None
        if not read:
            last = self._last_budget
            return None if last is None else spend_between(self._first_budget or last, last)
        budget = self._read(graphql_budget_args(), _GRAPHQL_BUDGET, "the GraphQL budget")
        self._note_budget(budget.rate_limit)
        return spend_between(self._first_budget or budget.rate_limit, budget.rate_limit)

    def _read_board(self, board_filter: str | None = None) -> dict[int, BoardEntry]:
        """The board's issues of this repository that the filter selects, by number."""
        items = self._read_board_listing(board_filter)
        return {
            item.content_number: item.entry()
            for item in items
            if item.is_issue_of(self._repo) and item.content_number is not None
        }

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
        if gh_http_status(proc.stderr or "") in absent:
            return None
        raise self._failure(proc, f"read {what}", "roadmap.read")

    def _read_schema(self) -> _BoardSchema:
        """The configured board's node id and fields through GraphQL, which alone gives option
        colors and descriptions, read the first time a store needs them."""
        if self._schema is None:
            owner, number = self._require_board()
            payload = self._read(
                board_fields_args(owner, number), _BOARD_FIELDS, f"board #{number} fields"
            )
            connection = payload.fields
            self._require_whole(len(connection.nodes), connection.total_count, "board fields")
            self._schema = _BoardSchema(
                board_id=payload.board_id, fields=tuple(node.field() for node in connection.nodes)
            )
        return self._schema

    def _graphql(self, request: str, action: str) -> str:
        """Send a GraphQL write, its request on stdin."""
        proc = self._run(list(GRAPHQL_INPUT_ARGS), input=request)
        if proc.returncode != 0:
            raise self._failure(proc, action, "roadmap.write")
        return proc.stdout or ""

    def _read_issue(self, number: int) -> _IssuePayload:
        return self._read(issue_args(self._repo, number), _ISSUE, f"issue #{number}")

    def _read_issues(self, query: str) -> list[IssueRecord]:
        issues = self._listing(issues_endpoint(self._repo, query), _ISSUE, "issues")
        return [issue.record() for issue in issues]

    def _listing[EntryT](
        self,
        endpoint: str,
        adapter: TypeAdapter[EntryT],
        what: str,
        *,
        ends: Callable[[EntryT], bool] | None = None,
    ) -> list[EntryT]:
        """Every entry of the REST listing `endpoint`, read through the GitHub session. With
        `ends`, the read stops at the first entry `ends` holds for and requests no later page: a
        listing read newest first ends at the first entry older than the time it reads from
        (#1360).

        The session follows each page's `Link: rel="next"` and raises on a failed page, a page
        that holds no list and a listing past its page cap, so the listing is never taken as
        whole when it is not; an entry that is not the shape `adapter` reads raises here.
        """
        listing: list[EntryT] = []
        for found in self._listing_session().paginate(listing_path(endpoint)):
            entry = self._validate_entry(found, adapter, what)
            listing.append(entry)
            if ends is not None and ends(entry):
                break
        return listing

    def _listing_session(self) -> ListingSession:
        """The session the REST listings are read through: the store's, else the process's."""
        return get_github_session() if self._session is None else self._session

    def _validate_entry[EntryT](
        self, found: Any, adapter: TypeAdapter[EntryT], what: str
    ) -> EntryT:
        try:
            return adapter.validate_python(found)
        except MalformedPayloadError as exc:
            raise GitHubOperationError(
                f"GitHub returned malformed {what} for {self._repo}.",
                operation="roadmap.read",
                details={"repo": self._repo[:256], "error": str(exc)[:256]},
            ) from exc

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
        self._sent_graphql = self._sent_graphql or gh_request_resource(args) == "graphql"
        return self._runner(args, input=input, check=False, quiet=True, use_cache=False)

    def _failure(
        self, proc: subprocess.CompletedProcess[str], action: str, operation: str
    ) -> GitHubOperationError:
        """The error for a failed gh command: the class the gh classifier names from gh's
        stderr, such as `GitHubRateLimitError`, else a failure to do `action`. gh's stdout holds
        GitHub's answer, possibly partial data with item titles, and is never classified."""
        output = f"{proc.stderr or ''} {proc.stdout or ''}".strip()
        stderr = proc.stderr or ""
        classified = classify_gh_failure(stderr, exit_code=proc.returncode, operation=operation)
        if classified is not None and is_gh_owner_lookup_failure(stderr):
            # The store's `--owner <login>` commands have no `@me` fallback (#983).
            failed = f"Could not {action} in {self._repo}"
            return owner_lookup_failure(
                classified, read=self._run, failed=failed, operation=operation
            )
        return classified or GitHubOperationError(
            f"Could not {action} in {self._repo} (exit {proc.returncode}): {output[:256]}",
            operation=operation,
            details={"repo": self._repo[:256], "exit_code": proc.returncode},
        )


def _change(board_field: BoardField, value: str | None) -> list[str]:
    """The `item-edit` flags that write `value` to `board_field`: its text for a text field,
    the option's id for a single-select one, and a clear for None."""
    if value is None:
        return ["--clear"]
    if not board_field.single_select:
        return ["--text", value]
    found = next((o.id for o in board_field.options if o.name == value and o.id), None)
    if found is None:
        raise GitHubOperationError(
            f"The board's {board_field.name} field has no option {value[:64]!r} to write.",
            operation="roadmap.write",
            details={"field": board_field.name[:256], "value": value[:256]},
        )
    return ["--single-select-option-id", found]


def _counts(totals: Sequence[int], listing: Sequence[object]) -> str:
    """The totals a read saw, then what it received."""
    return ", ".join(str(total) for total in totals) + f"; received {len(listing)}"


__all__ = [
    "GRAPHQL_INPUT_ARGS",
    "FieldListingPayload",
    "GhRunner",
    "GitHubRoadmapStore",
    "ListingSession",
    "advisory_args",
    "board_fields_args",
    "board_query_args",
    "card_edit_args",
    "closures_args",
    "comment_args",
    "comments_endpoint",
    "commit_args",
    "create_issue_args",
    "decode_job_record",
    "encode_job_record",
    "field_list_args",
    "graphql_request",
    "is_private_args",
    "issue_args",
    "issues_endpoint",
    "item_add_args",
    "item_edit_args",
    "item_unarchive_args",
    "label_args",
    "listing_path",
    "milestone_edit_args",
    "milestones_endpoint",
    "path_commits_args",
    "repository_file_args",
    "repository_issue_events_endpoint",
    "repository_query_args",
    "workflow_run_args",
    "write_issue_body_args",
]
