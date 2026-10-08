"""The GitHub roadmap store: Releases, Items and board fields read and written through `gh`.

Every command goes through an injected runner that defaults to `run_gh`. REST listings are read
a full page at a time until a page is short, and each page must be a JSON list: `run_gh`'s own
paging (`api --paginate`) ends a listing at a page that is empty or not JSON as if it were the
last. The board comes from the store's own paged GraphQL query (`board_read`): each read passes
a Projects filter at the source, leaves archived items out, checks the budget first and charges
each page's reported points, and is checked against the total for the same filter, so a short
read is caught; a count that changes during the read is read again once before the read fails.
A poll reads three listings a page at a time, newest first, and stops after the first page that
ends before the time it reads from (#1360): the issue events, the pull requests by their last
update, for the cuts and un-cuts of release pull requests, and the GitHub Releases, for the
ships, these two `DEFAULT_ROADMAP_POLL_LISTING_PER_PAGE` at a time, since each entry is large.
Every one is REST; the milestones are read only when a GitHub Release was published in that
time, to find the Release its tag names.

The store reads the board listing once for each filter, and the board's fields once, and keeps
both for its life, one command or one Service round (#1361): every reader of a filter shares its
listing, and the store's own writes keep it current with the values they sent and the cards
they add. A close drops the listings, because the board's own workflow then changes the closed
issue's card. A write reads only the card it writes, by node id (`RoadmapBoardCard`, about one
point), so the job record it writes joins the one the card holds then, a card gone or archived
raises before any write, and the points that read reports below the reserve refuse the write.
A field someone changed since the store read the card raises `RoadmapCardChangedError` before
any write, unless the card already holds the value the write sends: the job planned without
that change, and ADR 0002 forbids reverting it, so the job fails and the next store plans again.
Every board write is `gh project item-edit` by node ids (`--id`, `--project-id`, `--field-id`,
and an option's id), which sends only the mutation; given a card's URL or a field's name, gh
first reads the board's first 100 items with all their field values, about 101 points.
`item-add` and `item-create` return the card they make (`--format json`), which the store writes
to without looking for it in a listing that can lag the add by minutes. `item-add` names the card
an issue already has, archived or not: the store reads that card once and restores an archived one
with `gh project item-archive --undo`, so it comes back with the fields it holds (#1403).

The board's own shape (its node id, its fields with their option ids, colors and descriptions,
and its workflows) comes from GraphQL. So do the default branch, pull requests with their last
commit, and when an Item's Status last changed, which is the Status value's `updatedAt`: the
board's timelines hold no status-change events (#768). A GraphQL connection is read in one
request of up to its limit, and one longer than that raises. New fields, and the options of a
board just created, are written with a GraphQL request on stdin. GitHub's option input takes no
id, so the adapter never sends an option list to a board that already has cards. Issue events
carry the Item's job record from the board listing, and those of the actor a caller leaves out
read none. The run record card is the board's draft issue titled
`CONST_ROADMAP_RUN_RECORD_TITLE`, found by that title in the board listing.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_API_HTTP_STATUS_RE,
    CONST_GH_ISSUE_EVENT_CHANGE_KINDS,
    CONST_GH_PROJECT_ITEM_ISSUE_TYPE,
    CONST_GH_PROJECT_JOB_RECORD_FIELD,
    CONST_GH_PROJECT_SINGLE_SELECT_TYPE,
    CONST_GH_PROJECT_TEXT_TYPE,
    CONST_GH_RAW_CONTENT_ACCEPT,
    CONST_ROADMAP_OPEN_ITEMS_FILTER,
    CONST_ROADMAP_RUN_RECORD_BODY,
    CONST_ROADMAP_RUN_RECORD_TITLE,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_ISSUE_TIMELINE_LIMIT,
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_OPEN_PULL_REQUEST_LIMIT,
    DEFAULT_GH_PROJECT_FIELD_LIMIT,
    DEFAULT_GH_PROJECT_ITEM_PAGE_POINTS,
    DEFAULT_GH_PROJECT_ITEMS_PER_ISSUE,
    DEFAULT_GH_PROJECT_LIST_LIMIT,
    DEFAULT_GH_PROJECT_OPTION_COLOR,
    DEFAULT_GH_PROJECT_WORKFLOW_LIMIT,
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_RELEASE_LABEL,
    DEFAULT_ROADMAP_POLL_LISTING_PER_PAGE,
)
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.github.projects import check_github_rate_limit_error
from devops_cli.github.rate_limiter import gh_request_resource, run_gh
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
    BOARD_FIELDS,
    RELEASE_CHANGE_KINDS,
    AddedItem,
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
    MergedPullRequest,
    PullRequest,
    PullRequestState,
    RefineRecordKey,
    Release,
    RoadmapStore,
    Workflow,
    as_utc,
    cuts_its_release,
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
    require_unchanged,
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
    updated_at: datetime | None = None
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
            updated_at=self.updated_at,
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
    open_prs: _PullRequestConnectionPayload = Field(
        validation_alias=AliasChoices(
            AliasPath("data", "repository", "openPrs"),
            AliasPath("data", "repository", "pullRequests"),
        )
    )
    recent_prs: _PullRequestConnectionPayload = Field(
        default_factory=lambda: _PullRequestConnectionPayload(nodes=[], totalCount=0),
        validation_alias=AliasPath("data", "repository", "recentPrs"),
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


class _IsPrivatePayload(BaseModel):
    is_private: bool = Field(validation_alias=AliasPath("data", "repository", "isPrivate"))


class _RefPayload(BaseModel):
    sha: str = Field(validation_alias=AliasPath("object", "sha"))


class _GitHubReleasePayload(BaseModel):
    draft: bool


class _ListedReleasePayload(BaseModel):
    """A GitHub Release as the REST listing `repos/{repo}/releases` gives it, newest first by
    `created_at`, its tag's time, which can be a little before it was published."""

    tag_name: str
    draft: bool
    created_at: datetime
    published_at: datetime | None = None

    def shipped_at(self, cutoff: datetime) -> datetime | None:
        """When it was published, if at or after `cutoff`; a draft is not published."""
        published = None if self.draft else self.published_at
        return published if published is not None and published >= cutoff else None


class _UpdatedPullRequestPayload(BaseModel):
    """A pull request as the REST listing `repos/{repo}/pulls?state=all&sort=updated` gives it,
    with its repository's default branch, so the rule for a Release's pull request needs no
    GraphQL read."""

    number: int
    html_url: str
    state: PullRequestState
    draft: bool = False
    labels: list[_NamedPayload] = Field(default_factory=list)
    release: str | None = Field(default=None, validation_alias=AliasPath("milestone", "title"))
    opener: str | None = Field(default=None, validation_alias=AliasPath("user", "login"))
    base: str = Field(validation_alias=AliasPath("base", "ref"))
    default_branch: str = Field(validation_alias=AliasPath("base", "repo", "default_branch"))
    head: str = Field(validation_alias=AliasPath("head", "ref"))
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None

    def pull_request(self) -> PullRequest:
        """The pull request, merged when the listing gives it a merge time."""
        merged = self.merged_at is not None
        return PullRequest(
            number=self.number,
            url=self.html_url,
            state=PullRequestState.MERGED if merged else self.state,
            draft=self.draft,
            base=self.base,
            head=self.head,
            labels=tuple(label.name for label in self.labels),
            release=self.release,
            updated_at=self.updated_at,
        )

    def changes(self, cutoff: datetime) -> list[Change]:
        """The cut its opening made and the un-cut its close unmerged made, those at or after
        `cutoff`, when it is a Release's pull request: a cut names who opened it, and an un-cut
        no one, as the listing names no closer."""
        pull_request = self.pull_request()
        if not cuts_its_release(pull_request, self.default_branch):
            return []
        found = [(ChangeKind.RELEASE_CUT, self.opener, self.created_at)]
        if pull_request.state is PullRequestState.CLOSED and self.closed_at is not None:
            found.append((ChangeKind.RELEASE_UNCUT, None, self.closed_at))
        return [
            Change(kind=kind, number=self.number, actor=actor, at=at, release=self.release)
            for kind, actor, at in found
            if at >= cutoff
        ]


class _PullRequestCommitPayload(BaseModel):
    sha: str


class _ClosedPullRequestPayload(BaseModel):
    """A closed pull request as the REST listing `repos/{repo}/pulls?state=closed` gives it."""

    number: int
    html_url: str
    title: str = ""
    body: str | None = None
    labels: list[_NamedPayload] = Field(default_factory=list)
    release: str | None = Field(default=None, validation_alias=AliasPath("milestone", "title"))
    merged_at: datetime | None = None
    merge_commit_sha: str | None = None
    head: _PullRequestCommitPayload

    def merged(self, changed_paths: Sequence[str]) -> MergedPullRequest:
        return MergedPullRequest(
            number=self.number,
            url=self.html_url,
            title=self.title,
            body=self.body or "",
            labels=tuple(label.name for label in self.labels),
            release=self.release,
            merge_commit=self.merge_commit_sha or "",
            head_commit=self.head.sha,
            changed_paths=tuple(changed_paths),
        )


class _PullRequestFilePayload(BaseModel):
    filename: str


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
        fields = {f.name.lower(): self.field_value(f.value) for f in BOARD_FIELDS}
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
        """The board's fields and job record for this issue, with its card's node id."""
        return BoardEntry.model_validate(
            self.values() | {"number": self.content_number, "card_id": self.id}
        )

    def written(self, field_name: str, value: str | None) -> _BoardItemPayload:
        """The card as it is once the store has written `value` to the field `field_name`."""
        return self.model_copy(update={item_list_key(field_name): value})

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


class _AddedCardPayload(BaseModel):
    """What `gh project item-add`, `item-create` or `item-archive --undo` prints with `--format
    json`: the card it made, named or restored."""

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
        """Each field's option names by field name; a field that isn't single-select has none."""
        return {field.name: tuple(option.name for option in field.options) for field in self.fields}


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
_BOARD_PAGE = TypeAdapter(BoardItemsPage)
_BOARD_BUDGET = TypeAdapter(BoardBudgetPayload)
_GRAPHQL_BUDGET = TypeAdapter(GraphQLBudgetPayload)
_BOARD_ITEMS = TypeAdapter(list[_BoardItemPayload])
_BOARD_ITEM = TypeAdapter(_BoardItemPayload)
_BOARD_CARD = TypeAdapter(BoardCardPayload)
_ADDED_CARD = TypeAdapter(_AddedCardPayload)
_JOB_RECORD = TypeAdapter(JobRecord)
# The job record keys this version reads; the others are a newer version's, kept as they are.
_JOB_RECORD_KEYS = frozenset(key.value for key in (*ItemField, *JobMark, *RefineRecordKey))
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
_IS_PRIVATE = TypeAdapter(_IsPrivatePayload)
_REF = TypeAdapter(_RefPayload)
_GITHUB_RELEASE = TypeAdapter(_GitHubReleasePayload)
_LISTED_RELEASES = TypeAdapter(list[_ListedReleasePayload])
_UPDATED_PULL_REQUESTS = TypeAdapter(list[_UpdatedPullRequestPayload])
_COMMENTS = TypeAdapter(list[_CommentPayload])
_CLOSED_PULL_REQUESTS = TypeAdapter(list[_ClosedPullRequestPayload])
_PULL_REQUEST_FILES = TypeAdapter(list[_PullRequestFilePayload])
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
    selection=f"id fields(first: $first) {{ totalCount nodes {{ {_FIELD_SELECTION} }} }}"
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
    selection=(
        f"openPrs: pullRequests(states: [OPEN], first: $first) {{ {_PULL_REQUEST_SELECTION} }} "
        "recentPrs: pullRequests(states: [MERGED], orderBy: {field: CREATED_AT, direction: DESC}, first: $first) "
        f"{{ {_PULL_REQUEST_SELECTION} }}"
    ),
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


def listing_page_args(
    endpoint: str, page: int | str, per_page: int = DEFAULT_GH_REST_PER_PAGE
) -> list[str]:
    """The `gh` arguments that read page `page` of the REST listing `endpoint`, `per_page`
    entries a page, a full page by default."""
    separator = "&" if "?" in endpoint else "?"
    return ["api", f"{endpoint}{separator}per_page={per_page}&page={page}"]


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


def board_workflows_args(owner: str, number: Number) -> list[str]:
    """The GraphQL read of board `number`'s built-in workflows."""
    return board_query_args(_WORKFLOWS_QUERY, owner, number, DEFAULT_GH_PROJECT_WORKFLOW_LIMIT)


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


def project_list_args(owner: str) -> list[str]:
    """`gh project list`: every board of `owner`, closed ones included."""
    limit = str(DEFAULT_GH_PROJECT_LIST_LIMIT)
    return ["project", "list", "--owner", owner, "--closed", "--format", "json", "--limit", limit]


def project_create_args(owner: str, title: str) -> list[str]:
    return ["project", "create", "--owner", owner, "--title", title, "--format", "json"]


def project_link_args(owner: str, number: Number, repo: str) -> list[str]:
    return ["project", "link", str(number), "--owner", owner, "--repo", repo]


def field_delete_args(field_id: str) -> list[str]:
    return ["project", "field-delete", "--id", field_id]


def item_add_args(owner: str, number: Number, url: str) -> list[str]:
    """`gh project item-add` of the issue at `url`, printing the card it adds, or the card the
    issue already has."""
    return ["project", "item-add", str(number), "--owner", owner, "--url", url, "--format", "json"]


def item_edit_args(
    owner: str, number: Number, url: str, field_name: str, change: Sequence[str]
) -> list[str]:
    """`gh project item-edit` on the issue at `url`, by the field's name. gh resolves both names
    by reading the board's first 100 items with every field value (about 101 points), so the
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


def run_record_card_args(owner: str, number: Number) -> list[str]:
    """`gh project item-create`: the run record card, a draft issue, printing the card."""
    return [
        "project",
        "item-create",
        str(number),
        "--owner",
        owner,
        "--title",
        CONST_ROADMAP_RUN_RECORD_TITLE,
        "--body",
        CONST_ROADMAP_RUN_RECORD_BODY,
        "--format",
        "json",
    ]


def item_delete_args(owner: str, number: Number, card_id: str) -> list[str]:
    return ["project", "item-delete", str(number), "--owner", owner, "--id", card_id]


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
"""A GraphQL write, its request on stdin, so option lists need no flag encoding."""


def graphql_request(query: str, variables: Mapping[str, Any]) -> str:
    """The stdin of a `GRAPHQL_INPUT_ARGS` write."""
    return json.dumps({"query": query, "variables": dict(variables)})


def create_field_request(project_id: str, name: str, data_type: str, options: object = None) -> str:
    """The stdin of the `createProjectV2Field` write that gives board `project_id` a field;
    `options`, for a single-select field, its `singleSelectOptions`."""
    created: dict[str, object] = {"projectId": project_id, "dataType": data_type, "name": name}
    extra = {"singleSelectOptions": options} if options is not None else {}
    return graphql_request(_CREATE_FIELD_MUTATION, {"input": created | extra})


def field_spec_request(project_id: str, spec: FieldSpec) -> str:
    """The `createProjectV2Field` write that gives board `project_id` the spec's field."""
    if spec.single_select:
        options = [_option_input(o) for o in spec.options]
        return create_field_request(
            project_id, spec.name, CONST_GH_PROJECT_SINGLE_SELECT_TYPE, options
        )
    return create_field_request(project_id, spec.name, CONST_GH_PROJECT_TEXT_TYPE)


def close_as_duplicate_request(issue_id: str, original_id: str) -> str:
    return graphql_request(
        _CLOSE_AS_DUPLICATE_MUTATION, {"issue": issue_id, "original": original_id}
    )


def issue_args(repo: str, number: Number) -> list[str]:
    return ["api", f"repos/{repo}/issues/{number}"]


def repository_issue_events_endpoint(repo: str) -> str:
    """The REST listing of every issue event of `repo`, newest first."""
    return f"repos/{repo}/issues/events"


def updated_pull_requests_endpoint(repo: str) -> str:
    """The REST listing of `repo`'s pull requests, open and closed, by their last update,
    newest first."""
    return f"repos/{repo}/pulls?state=all&sort=updated&direction=desc"


def github_releases_endpoint(repo: str) -> str:
    """The REST listing of `repo`'s GitHub Releases, newest first."""
    return f"repos/{repo}/releases"


def issue_events_endpoint(repo: str, number: Number) -> str:
    return f"repos/{repo}/issues/{number}/events"


def merged_pull_requests_endpoint(repo: str, base: str) -> str:
    """The REST listing of `repo`'s closed pull requests into `base`, oldest first; the merged
    ones are those with a merge time."""
    return f"repos/{repo}/pulls?state=closed&base={quote(base, safe='')}&sort=created&direction=asc"


def pull_request_files_endpoint(repo: str, number: Number) -> str:
    """The REST listing of the files pull request `number` changed."""
    return f"repos/{repo}/pulls/{number}/files"


def comments_endpoint(repo: str, number: Number) -> str:
    return f"repos/{repo}/issues/{number}/comments"


def dependencies_endpoint(repo: str, number: Number) -> str:
    return f"repos/{repo}/issues/{number}/dependencies/blocked_by"


def milestone_args(
    repo: str, method: str, number: Number | None = None, fields: Sequence[tuple[str, str]] = ()
) -> list[str]:
    """A milestone write: POST to create one, PATCH or DELETE milestone `number`."""
    path = f"repos/{repo}/milestones" + (f"/{number}" if number is not None else "")
    flags = [part for name, value in fields for part in ("-f", f"{name}={value}")]
    return ["api", "-X", method, path, *flags]


def issue_milestone_args(repo: str, number: Number, milestone: Number | None) -> list[str]:
    """Set issue `number`'s milestone, or clear it when `milestone` is None."""
    value = "null" if milestone is None else milestone
    return ["api", "-X", "PATCH", f"repos/{repo}/issues/{number}", "-F", f"milestone={value}"]


def create_issue_args(repo: str, title: str, body: str, labels: Sequence[str] = ()) -> list[str]:
    fields = [("title", title), ("body", body), *(("labels[]", label) for label in labels)]
    flags = [part for name, value in fields for part in ("-f", f"{name}={value}")]
    return ["api", "-X", "POST", f"repos/{repo}/issues", *flags]


def close_issue_args(repo: str, number: Number, reason: str) -> list[str]:
    return [
        "api",
        "-X",
        "PATCH",
        f"repos/{repo}/issues/{number}",
        "-f",
        "state=closed",
        "-f",
        f"state_reason={reason}",
    ]


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


def release_tag_args(repo: str, tag: str) -> list[str]:
    tag = tag if tag.startswith("<") else quote(tag)
    return ["api", f"repos/{repo}/releases/tags/{tag}"]


def branch_ref_args(repo: str, name: str) -> list[str]:
    name = name if name.startswith("<") else quote(name)
    return ["api", f"repos/{repo}/git/ref/heads/{name}"]


def create_branch_args(repo: str, name: str, sha: str) -> list[str]:
    return [
        "api",
        "-X",
        "POST",
        f"repos/{repo}/git/refs",
        "-f",
        f"ref=refs/heads/{name}",
        "-f",
        f"sha={sha}",
    ]


def open_pull_requests_args(repo: str) -> list[str]:
    return repository_query_args(
        repo, _OPEN_PULL_REQUESTS_QUERY, first=DEFAULT_GH_OPEN_PULL_REQUEST_LIMIT
    )


def release_pull_requests_args(repo: str, milestone: Number) -> list[str]:
    return repository_query_args(
        repo,
        _RELEASE_PULL_REQUESTS_QUERY,
        number=milestone,
        first=DEFAULT_GH_OPEN_PULL_REQUEST_LIMIT,
    )


def issue_status_args(repo: str, number: Number) -> list[str]:
    return repository_query_args(
        repo, _ISSUE_STATUS_QUERY, number=number, first=DEFAULT_GH_PROJECT_ITEMS_PER_ISSUE
    )


def default_branch_args(repo: str) -> list[str]:
    return repository_query_args(repo, _DEFAULT_BRANCH_QUERY)


def is_private_args(repo: str) -> list[str]:
    """The `gh` arguments that query whether `repo` is private."""
    return repository_query_args(repo, _IS_PRIVATE_QUERY)


def closures_args(repo: str, number: Number) -> list[str]:
    return repository_query_args(
        repo, _CLOSURES_QUERY, first=DEFAULT_GH_ISSUE_TIMELINE_LIMIT, number=number
    )


def _releases_among(milestones: list[_MilestonePayload]) -> Iterator[Release]:
    for milestone in milestones:
        if is_release_title(milestone.title):
            yield milestone.release()
        else:
            logger.warning("Skipping milestone %r: its title is not a version.", milestone.title)


# ── Adapter ───────────────────────────────────────────────────────────────────


class GitHubRoadmapStore(RoadmapStore):
    """The roadmap on GitHub, read and written as whoever `gh` is logged in as.

    Without a board, Release operations work, and Item reads and writes raise. One store lives
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
        board_filter: str = "",
    ) -> None:
        self._repo = repo
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
            "POST",
            None,
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
            "PATCH", current.number, edits, f"edit Release {current.title}"
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
        board = self._read_board(CONST_ROADMAP_OPEN_ITEMS_FILTER)
        return join_items(self._read_issues("milestone=none&state=open"), board)

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that are not on the board."""
        board = self._read_board(CONST_ROADMAP_OPEN_ITEMS_FILTER)
        return select_candidates(self._read_issues("state=open"), board)

    def changes_since(self, since: datetime, *, except_actor: str | None = None) -> list[Change]:
        """The changes made at or after `since`, oldest first: the Item changes the issue events
        report, the cuts and un-cuts of release pull requests, and the ships of GitHub Releases
        whose tag names a Release (#1360). Those `except_actor` made are left out before any job
        record is read; an empty actor leaves out nothing, and a ship or an un-cut, which names
        no actor, is never left out."""
        cutoff = as_utc(since)
        skipped = except_actor or None
        events = self._read_listing(
            repository_issue_events_endpoint(self._repo),
            _EVENTS,
            "issue events",
            ends=lambda event: event.created_at < cutoff,
        )
        pull_requests = self._read_listing(
            updated_pull_requests_endpoint(self._repo),
            _UPDATED_PULL_REQUESTS,
            "pull requests",
            ends=lambda pull_request: pull_request.updated_at < cutoff,
            per_page=DEFAULT_ROADMAP_POLL_LISTING_PER_PAGE,
        )
        changes = [
            change
            for event in reversed(events)
            if (change := event.change()) is not None and change.at >= cutoff
        ]
        changes += [change for listed in pull_requests for change in listed.changes(cutoff)]
        changes += self._ships_since(cutoff)
        kept = [change for change in changes if skipped is None or change.actor != skipped]
        return self._with_job_records(sorted(kept, key=lambda change: change.at))

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
        if field is ItemField.RELEASE:
            target = self._release_for(value)
            recorded = target.title if target else None
        else:
            require_option(options, field, value)
            recorded = value
        written = None if field is ItemField.RELEASE else field
        card = self._require_entry(item, operation, written, value)
        text = card.recorded(with_marks({field: recorded}, marks or {}))
        card = self._edit_card(card, CONST_GH_PROJECT_JOB_RECORD_FIELD, text, operation)
        if field is ItemField.RELEASE:
            self._place_in_release(item, target)
        else:
            self._edit_card(card, field.value, value, operation)

    def set_marks(
        self,
        item: Item,
        marks: Mapping[Any, str | None],
        *,
        recorded: Mapping[ItemField, str | None] | None = None,
        forgotten: Collection[ItemField] = (),
    ) -> None:
        """Set or clear a job's marks in the Item's job record, as its card holds it now, and
        record or forget a value for a field, in one write."""
        operation = "roadmap.item.set_marks"
        require_job_record_field(self._read_schema().options())
        card = self._require_entry(item, operation)
        changes: JobRecord = {}
        for item_field, value in (recorded or {}).items():
            changes[item_field] = value
        text = card.recorded(with_marks(changes, marks), forgotten)
        self._edit_card(card, CONST_GH_PROJECT_JOB_RECORD_FIELD, text, operation)

    def run_record(self) -> JobRecord:
        """The run record card's job record, empty while the board has no such card."""
        card = self._run_record_card()
        return card.card().job_record if card else {}

    def set_run_record(self, marks: Mapping[Any, str | None]) -> None:
        """Set or clear marks in the run record card's job record, as the card holds it now,
        creating the card first when the board has none."""
        operation = "roadmap.run_record"
        require_job_record_field(self._read_schema().options())
        listed = self._run_record_card()
        card = (
            self._require_card_node(listed.id, f"Run record card {listed.id}", operation)
            if listed
            else self._create_run_record_card()
        )
        text = card.recorded(marks)
        self._edit_card(card, CONST_GH_PROJECT_JOB_RECORD_FIELD, text, operation)

    def release_changes(self, number: int) -> list[Change]:
        """Every time issue `number` joined or left a Release, from its own events."""
        events = self._read_listing(
            issue_events_endpoint(self._repo, number), _EVENTS, f"#{number} events"
        )
        moves = (ChangeKind.JOINED_RELEASE, ChangeKind.LEFT_RELEASE)
        changes = (event.model_copy(update={"number": number}).change() for event in events)
        return [change for change in changes if change is not None and change.kind in moves]

    def delete_release(self, version: str) -> None:
        """Delete the Release of `version`, raising if there is none."""
        deleted = require_release(self.releases(), version, "roadmap.release.delete")
        self._write(
            milestone_args(self._repo, "DELETE", deleted.number), f"delete Release {deleted.title}"
        )

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

    def close_issue(self, number: int, reason: CloseReason, comment: str) -> None:
        """Comment on issue `number`, then close it for `reason`. The board's own workflow then
        changes the issue's card, so the store drops the listings it read and reads the board
        again when next needed."""
        if self._read_issue(number).pull_request is not None:
            raise GitHubOperationError(
                f"#{number} in {self._repo} is a pull request, not an issue.",
                operation="roadmap.issue.close",
                details={"repo": self._repo[:256], "number": number},
            )
        self.comment(number, comment)
        self._write(close_issue_args(self._repo, number, reason), f"close #{number}")
        self._listings = {}

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

    def comments_on(self, number: int) -> list[str]:
        """The body of every comment on issue `number`, oldest first."""
        listing = self._read_listing(
            comments_endpoint(self._repo, number), _COMMENTS, f"#{number} comments"
        )
        return [comment.body for comment in listing]

    def comment(self, number: int, body: str) -> None:
        """Comment `body` on issue `number`."""
        self._write(comment_args(self._repo, number, body), f"comment on #{number}")

    # ── What intake reads and writes ──

    def close_as_duplicate(self, number: int, original: int, comment: str | None) -> None:
        """Comment on issue `number` unless `comment` is None, then close it as a duplicate of
        `original` through GraphQL, which alone sets the original (`duplicateIssueId`). Both are
        read first, so a pull request on either side raises before any write. The board's own
        workflow then changes the issue's card, so the store drops the listings it read."""
        node_ids = [self._require_issue_node(n, "roadmap.issue.close") for n in (number, original)]
        if comment is not None:
            self.comment(number, comment)
        self._graphql(
            close_as_duplicate_request(node_ids[0], node_ids[1]),
            f"close #{number} as a duplicate of #{original}",
        )
        self._listings = {}

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
        so no value reaches another resource; a commit GitHub can't resolve answers 422."""
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

    def repository_is_private(self) -> bool:
        """Whether the repository is private."""
        return self._read(
            is_private_args(self._repo), _IS_PRIVATE, f"{self._repo} visibility"
        ).is_private

    # ── The board ──

    def board(self) -> Board | None:
        """The configured board, or None when its owner has no board with that number."""
        owner, number = self._require_board()
        listing = self._read(project_list_args(owner), _PROJECTS, f"{owner}'s boards")
        self._require_whole(len(listing.projects), listing.total_count, f"{owner}'s boards")
        return next((p.board() for p in listing.projects if p.number == number), None)

    def create_board(self, title: str, fields: Sequence[FieldSpec]) -> Board:
        """Create a board titled `title`, link it to the repository, then give it `fields`."""
        owner, _ = self._require_board()
        written = self._write(project_create_args(owner, title), f"create the board {title[:64]!r}")
        created = self._validate(written, _PROJECT, "board after it was created").board()
        self._write(
            project_link_args(owner, created.number, self._repo), f"link board #{created.number}"
        )
        current = {
            board_field.name: board_field
            for board_field in self._read_fields(created.number).fields
        }
        for spec in fields:
            self._create_or_align_field(created, current.get(spec.name), spec)
        return created

    def board_fields(self) -> list[BoardField]:
        """Every field on the board, with each option's id, color and description."""
        return list(self._read_schema().fields)

    def delete_field(self, name: str) -> None:
        """Delete the board field `name`, raising if the board has none."""
        schema = self._read_schema()
        deleted = schema.field(name, "roadmap.board.delete_field")
        self._write(field_delete_args(deleted.id), f"delete the {name} field")
        kept = tuple(board_field for board_field in schema.fields if board_field.id != deleted.id)
        self._schema = schema.model_copy(update={"fields": kept})

    def cards(self) -> list[Card]:
        """Everything on the board, whatever it holds and whichever repository it belongs to."""
        return [board_item.card() for board_item in self._read_board_listing()]

    def set_card_field(self, card: Card, field: ItemField, value: str | None) -> None:
        """Set or clear a board field on any card by its node ids, then record it; a field
        someone changed since the store read the card raises before any write, unless the card
        already holds `value`."""
        operation = "roadmap.card.set_field"
        require_board_field(field)
        options = self._read_schema().options()
        require_job_record_field(options)
        require_option(options, field, value)
        current = self._require_card_node(
            card.id,
            f"Card {card.id}",
            operation,
            field=field,
            value=value,
            held=card.field_value(field),
        )
        current = self._edit_card(current, field.value, value, operation)
        text = current.recorded({field: value})
        self._edit_card(current, CONST_GH_PROJECT_JOB_RECORD_FIELD, text, operation)

    def remove_card(self, card: Card) -> None:
        """Take `card` off the board, raising if it is not on it."""
        owner, number = self._require_board()
        self._require_card_node(card.id, f"Card {card.id}", "roadmap.card.remove")
        self._write(
            item_delete_args(owner, number, card.id), f"remove card {card.id} from board #{number}"
        )
        for listing in self._listings.values():
            listing[:] = [listed for listed in listing if listed.id != card.id]

    def workflows(self) -> list[Workflow]:
        """The board's built-in workflows."""
        owner, number = self._require_board()
        payload = self._read(
            board_workflows_args(owner, number), _WORKFLOWS, f"board #{number} workflows"
        )
        connection = payload.workflows
        self._require_whole(len(connection.nodes), connection.total_count, "board workflows")
        return list(connection.nodes)

    # ── What the release rules read and write ──

    def dependencies(self, number: int) -> list[Dependency]:
        """The issues issue `number` waits on through GitHub's blocked-by links."""
        listing = self._read_listing(
            dependencies_endpoint(self._repo, number),
            _DEPENDENCIES,
            f"#{number} dependencies",
        )
        return [payload.dependency() for payload in listing]

    def status_changed_at(self, number: int) -> datetime | None:
        """The `updatedAt` of the Item's Status on the configured board, or None without one."""
        owner, board_number = self._require_board()
        payload = self._read(
            issue_status_args(self._repo, number), _ISSUE_STATUS, f"#{number} board cards"
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
        """Every open pull request and recent merged pull requests, from one GraphQL read."""
        payload = self._read(
            open_pull_requests_args(self._repo), _OPEN_PULL_REQUESTS, "open pull requests"
        )
        self._require_whole(
            len(payload.open_prs.nodes), payload.open_prs.total_count, "open pull requests"
        )
        prs_by_number: dict[int, PullRequest] = {
            node.number: node.pull_request() for node in payload.open_prs.nodes
        }
        for node in payload.recent_prs.nodes:
            if node.number not in prs_by_number:
                prs_by_number[node.number] = node.pull_request()
        return list(prs_by_number.values())

    def release_pull_requests(self, version: str) -> list[PullRequest]:
        """The pull requests with the `release` label in the Release's milestone."""
        release = require_release(self.releases(), version, "roadmap.release.pull_requests")
        payload = self._read(
            release_pull_requests_args(self._repo, release.number),
            _RELEASE_PULL_REQUESTS,
            f"{release.title} release pull requests",
        )
        return self._pull_requests(payload.connection, f"{release.title} release pull requests")

    def merged_pull_requests(self, base: str) -> list[MergedPullRequest]:
        """Every pull request merged into `base`, oldest first, each with the paths it changed;
        each listing is read a full page at a time, and a failed page raises."""
        closed = self._read_listing(
            merged_pull_requests_endpoint(self._repo, base),
            _CLOSED_PULL_REQUESTS,
            f"pull requests into {base}",
        )
        return [
            pull_request.merged(
                [
                    changed.filename
                    for changed in self._read_listing(
                        pull_request_files_endpoint(self._repo, pull_request.number),
                        _PULL_REQUEST_FILES,
                        f"#{pull_request.number} files",
                    )
                ]
            )
            for pull_request in closed
            if pull_request.merged_at is not None
        ]

    def release_published(self, version: str) -> bool:
        """Whether GitHub Release `vX.Y.Z` is published: it exists and is not a draft."""
        tag = release_title(version)
        found = self._read_or_none(
            release_tag_args(self._repo, tag),
            _GITHUB_RELEASE,
            f"GitHub Release {tag}",
        )
        return found is not None and not found.draft

    def default_branch(self) -> Branch:
        """The default branch and its head commit, from one GraphQL read."""
        payload = self._read(default_branch_args(self._repo), _DEFAULT_BRANCH, "default branch")
        return Branch(name=payload.name, sha=payload.sha)

    def branch(self, name: str) -> str | None:
        """The head commit of branch `name`, or None when the ref is not found."""
        found = self._read_or_none(branch_ref_args(self._repo, name), _REF, f"branch {name}")
        return found.sha if found else None

    def create_branch(self, name: str, sha: str) -> None:
        """Create branch `name` at `sha`; GitHub refuses a ref that already exists."""
        self._write(create_branch_args(self._repo, name, sha), f"create branch {name}")

    # ── Writes ──

    def _with_job_records(self, changes: list[Change]) -> list[Change]:
        """The changes, each Item change with its Item's job record from the board, when one is
        configured. A release change carries none, so a poll that finds only those reads no
        board."""
        items = [change for change in changes if change.kind not in RELEASE_CHANGE_KINDS]
        if self._board is None or not items:
            return changes
        board = self._read_board()
        return [
            change.model_copy(update={"job_record": board[change.number].job_record})
            if change.kind not in RELEASE_CHANGE_KINDS and change.number in board
            else change
            for change in changes
        ]

    def _run_record_card(self) -> _BoardItemPayload | None:
        """The run record card as the board listing holds it, or None."""
        listing = self._read_board_listing()
        return next((item for item in listing if item.is_run_record()), None)

    def _create_run_record_card(self) -> _BoardItemPayload:
        """Put the run record card on the board: the card `item-create` names, with no field
        set, read nothing after the create."""
        owner, number = self._require_board()
        written = self._write(run_record_card_args(owner, number), "create the run record card")
        created = self._validate(written, _ADDED_CARD, "run record card after it was created")
        content = {"type": CardKind.DRAFT_ISSUE.value, "title": CONST_ROADMAP_RUN_RECORD_TITLE}
        card = _BOARD_ITEM.validate_python({"id": created.id, "content": content})
        self._added(card, is_open=False)
        return card

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
        read leaves fewer points than the reserve, or when writing `value` to `field` would
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
        whose filter the store can't judge, is read again when next needed."""
        kept = {"", CONST_ROADMAP_OPEN_ITEMS_FILTER} if is_open else {""}
        self._listings = {
            query: listing if any(listed.id == card.id for listed in listing) else [*listing, card]
            for query, listing in self._listings.items()
            if query in kept
        }

    def _release_for(self, version: str | None) -> Release | None:
        """The Release of `version` an issue is placed in, None for the backlog; raising when
        there is no such Release."""
        if version is None:
            return None
        return require_release(self.releases(), version, "roadmap.item.set_field")

    def _place_in_release(self, item: Item, target: Release | None) -> None:
        """Set or clear the issue's milestone."""
        self._write(
            issue_milestone_args(self._repo, item.number, target.number if target else None),
            f"set the Release of #{item.number}",
        )

    def _write_milestone(
        self, method: str, number: int | None, fields: dict[str, str | date], action: str
    ) -> Release:
        wire = [(name, _wire_value(value)) for name, value in fields.items()]
        written = self._write(milestone_args(self._repo, method, number, wire), action)
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

    def _read_board_listing(self, board_filter: str | None = None) -> list[_BoardItemPayload]:
        """The board's items that `board_filter`, or the job's filter, selects, archived ones
        left out: read the first time the store needs that filter, and kept for its life."""
        query = self._board_filter if board_filter is None else board_filter
        if query not in self._listings:
            self._listings[query] = self._fetch_board_listing(query)
        return self._listings[query]

    def _fetch_board_listing(self, query: str) -> list[_BoardItemPayload]:
        """One read of the items `query` selects, refusing before any page when the budget can't
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
            f"The {what} run past {DEFAULT_GH_MAX_PAGINATED_PAGES} pages, so the read can't "
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
        return {
            number: item.entry() for number, item in self._read_board_items(board_filter).items()
        }

    def _read_board_items(self, board_filter: str | None = None) -> dict[int, _BoardItemPayload]:
        """The board's cards of this repository's issues, as listed, by number."""
        items = self._read_board_listing(board_filter)
        return {
            item.content_number: item
            for item in items
            if item.is_issue_of(self._repo) and item.content_number is not None
        }

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

    def _read_schema(self) -> _BoardSchema:
        """The configured board's node id and fields, read the first time a store needs them."""
        if self._schema is None:
            self._schema = self._read_fields(self._require_board()[1])
        return self._schema

    def _read_fields(self, number: int) -> _BoardSchema:
        """Board `number`'s node id and fields through GraphQL, which alone gives option colors
        and descriptions."""
        owner, _ = self._require_board()
        payload = self._read(
            board_fields_args(owner, number),
            _BOARD_FIELDS,
            f"board #{number} fields",
        )
        connection = payload.fields
        self._require_whole(len(connection.nodes), connection.total_count, "board fields")
        return _BoardSchema(
            board_id=payload.board_id, fields=tuple(node.field() for node in connection.nodes)
        )

    def _create_or_align_field(
        self, board: Board, current: BoardField | None, spec: FieldSpec
    ) -> None:
        """Create the spec's field, or give a field the new board already has the spec's options.

        The new board holds no cards, so the new option ids its options get cost no value.
        """
        if current is None:
            self._graphql(field_spec_request(board.id, spec), f"create the {spec.name} field")
        elif current.single_select and spec.single_select:
            self._replace_options(current, spec.options)

    def _replace_options(self, current: BoardField, options: Sequence[FieldOption]) -> BoardField:
        written = self._graphql(
            json.dumps(option_update_request(current.id, options)),
            f"replace the {current.name} options",
        )
        updated = self._validate(written, _UPDATED_FIELD, f"{current.name} field after its update")
        return updated.field.field()

    def _graphql(self, request: str, action: str) -> str:
        """Send a GraphQL write, its request on stdin, so option lists need no flag encoding."""
        proc = self._run(list(GRAPHQL_INPUT_ARGS), input=request)
        if proc.returncode != 0:
            raise self._failure(proc, action, "roadmap.write")
        return proc.stdout or ""

    def _read_issue(self, number: int) -> _IssuePayload:
        return self._read(issue_args(self._repo, number), _ISSUE, f"issue #{number}")

    def _ships_since(self, cutoff: datetime) -> list[Change]:
        """A ship for each GitHub Release published at or after `cutoff` whose tag names a
        Release. The listing is ordered by its tags' times, so every page is judged by when
        each was published, and the milestones are read only when one was published since."""
        listed = self._read_listing(
            github_releases_endpoint(self._repo),
            _LISTED_RELEASES,
            "GitHub Releases",
            ends=lambda release: release.created_at < cutoff,
            per_page=DEFAULT_ROADMAP_POLL_LISTING_PER_PAGE,
        )
        shipped = [
            (published.tag_name, at)
            for published in listed
            if (at := published.shipped_at(cutoff)) is not None
        ]
        releases = self.releases() if shipped else []
        return [
            Change(
                kind=ChangeKind.RELEASE_SHIPPED, number=0, actor=None, at=at, release=release.title
            )
            for tag, at in shipped
            if is_release_title(tag) and (release := find_release(releases, tag)) is not None
        ]

    def _read_issues(self, query: str) -> list[IssueRecord]:
        issues = self._read_listing(issues_endpoint(self._repo, query), _ISSUES, "issues")
        return [issue.record() for issue in issues]

    def _read_listing[EntryT](
        self,
        endpoint: str,
        adapter: TypeAdapter[list[EntryT]],
        what: str,
        *,
        ends: Callable[[EntryT], bool] | None = None,
        per_page: int = DEFAULT_GH_REST_PER_PAGE,
    ) -> list[EntryT]:
        """Read every page of a REST listing, `per_page` entries at a time, until a page is
        short, or, with `ends`, until a page whose last entry `ends` holds for: a listing read
        newest first ends at the first page reaching back past the time it reads from (#1360).

        Each page must be a JSON list, or the read raises, naming it: `api --paginate` would
        end the listing at a page that is empty or not JSON, as a proxy's error page is, and
        report what it read before as the whole of it.
        """
        listing: list[EntryT] = []
        for page in range(1, DEFAULT_GH_MAX_PAGINATED_PAGES + 1):
            entries = self._read(
                listing_page_args(endpoint, page, per_page), adapter, f"{what} (page {page})"
            )
            listing.extend(entries)
            if len(entries) < per_page or (ends is not None and ends(entries[-1])):
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
        self._sent_graphql = self._sent_graphql or gh_request_resource(args) == "graphql"
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
    "advisory_args",
    "board_fields_args",
    "board_query_args",
    "board_workflows_args",
    "branch_ref_args",
    "card_edit_args",
    "close_as_duplicate_request",
    "close_issue_args",
    "closures_args",
    "comment_args",
    "comments_endpoint",
    "commit_args",
    "create_branch_args",
    "create_field_request",
    "create_issue_args",
    "decode_job_record",
    "default_branch_args",
    "dependencies_endpoint",
    "encode_job_record",
    "field_delete_args",
    "field_list_args",
    "field_spec_request",
    "github_releases_endpoint",
    "graphql_request",
    "is_private_args",
    "issue_args",
    "issue_count_args",
    "issue_events_endpoint",
    "issue_milestone_args",
    "issue_search_text",
    "issue_status_args",
    "issues_endpoint",
    "item_add_args",
    "item_delete_args",
    "item_edit_args",
    "item_unarchive_args",
    "label_args",
    "listing_page_args",
    "milestone_args",
    "milestones_endpoint",
    "open_pull_requests_args",
    "option_update_request",
    "project_create_args",
    "project_link_args",
    "project_list_args",
    "release_pull_requests_args",
    "release_tag_args",
    "repository_file_args",
    "repository_issue_events_endpoint",
    "repository_query_args",
    "run_record_card_args",
    "updated_pull_requests_endpoint",
    "workflow_run_args",
    "write_issue_body_args",
]
