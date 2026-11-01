"""The GitHub roadmap store: milestones, Items and their labels read and written through `gh`,
and REST listings read through the GitHub session (ADR 0016).

Every gh command goes through an injected runner that defaults to `run_gh`. The REST listings
(milestones, issues, issue events and comments) are read through the session the store is
given, else the process's, with its `paginate()` (#983): it follows GitHub's `Link: rel="next"`,
raises on a page that holds no list and on a listing past its page cap, so a listing never ends
short without saying so, and it requests a page only when the store reads on into it. A
milestone is a planning bucket with any title: the store reads every milestone, identifies it by
its number and orders the milestones by due date, then by number. No title is read as a version.

The store reads the listing of every issue, open and closed, once for its life, one command or
one Service round (#1361): `items()`, `issues()` and `candidates()` share it, and the store's own
writes keep it current with the issues GitHub returns. A milestone's items and the backlog are
read as their own listings. A poll reads the repository's issue events newest first and stops at
the first event older than the time it reads from, requesting no later page (#1360). The newest
commit that changed a path is one `gh api` read of the commits listing, one commit a page, which
the store makes once for each path (#2005).

A field or mark write reads the issue first (`GET`), so the job record it writes joins the one
the issue holds then and a field a person changed since the store read it raises
`RoadmapItemChangedError` before any write. It then sends one `PATCH` of the issue with its
labels and its body, which holds the record block: GitHub takes both in one request, so the
field and its record never disagree. GitHub has no conditional write of an issue, so a person's
edit between the two requests is lost; within one process, `_JOB_RECORD_LOCK` holds each write
from its read to its `PATCH`, so the Service's two lanes, which open a store each, never write
back a record the other has changed since it was read (#1532). The only GraphQL reads are an
issue's closes and reopens and the repository's visibility; no request reaches a project board.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from datetime import date, datetime
from http import HTTPStatus
from typing import Any, Protocol
from urllib.parse import quote

from pydantic import AliasPath, BaseModel, Field, TypeAdapter
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_ISSUE_EVENT_CHANGE_KINDS,
    CONST_GH_RAW_CONTENT_ACCEPT,
)
from devops_cli.config.defaults import DEFAULT_GH_ISSUE_TIMELINE_LIMIT, DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.github.error_classifier import classify_gh_failure, gh_http_status
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.store import (
    Candidate,
    Change,
    ChangeKind,
    CloseReason,
    Closure,
    Evidence,
    EvidenceKind,
    GitHubState,
    IssueComment,
    IssueRecord,
    Item,
    ItemField,
    Milestone,
    OpenPull,
    RepositoryFacts,
    RepositoryLabel,
    RoadmapStore,
    already_closed,
    as_utc,
    decode_job_record,
    encode_job_record,
    find_milestone,
    is_repository_name,
    item_of,
    milestone_edits,
    milestone_order,
    relabeled,
    require_milestone,
    require_unchanged,
    require_value,
    select_candidates,
    select_items,
    split_record,
    with_record,
)

_JOB_RECORD_LOCK = threading.Lock()
"""Held from the read of an issue to the write of its job record, across every store in the
process: the Service's lanes each open a store, and mark the same Items (#1532)."""


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
    id: int = 0
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
    repository_url: str | None = None
    parent_issue_url: str | None = None

    @property
    def parent(self) -> int | None:
        """The number of the parent when it is an issue of this issue's repository: the parent's
        URL is the repository's URL, then `/issues/<number>`. A parent in another repository
        names another issue, whatever its number."""
        if self.parent_issue_url is None or self.repository_url is None:
            return None
        number = self.parent_issue_url.removeprefix(f"{self.repository_url}/issues/")
        return int(number) if number.isdecimal() else None

    @property
    def label_names(self) -> tuple[str, ...]:
        return tuple(label.name for label in self.labels)

    def split(self) -> tuple[str, dict[str, Any]]:
        """The body with its record block taken out, and the JSON object the block holds."""
        return split_record(self.body or "", issue=f"#{self.number}")

    def record(self) -> IssueRecord:
        body, held = self.split()
        return IssueRecord(
            id=self.id,
            number=self.number,
            title=self.title,
            url=self.html_url,
            body=body,
            state=self.state,
            state_reason=self.state_reason,
            labels=self.label_names,
            milestone=self.milestone,
            pull_request=self.pull_request is not None,
            author_association=self.author_association,
            created_at=self.created_at,
            updated_at=self.updated_at,
            closed_at=self.closed_at,
            sub_issues=self.sub_issues,
            parent=self.parent,
            job_record=decode_job_record(held, issue=f"#{self.number}"),
        )


class _PullPayload(BaseModel):
    number: int
    title: str
    html_url: str
    draft: bool = False
    head_ref: str = Field(validation_alias=AliasPath("head", "ref"))
    updated_at: datetime

    def pull(self) -> OpenPull:
        return OpenPull(
            number=self.number,
            title=self.title,
            url=self.html_url,
            head_ref=self.head_ref,
            draft=self.draft,
            updated_at=self.updated_at,
        )


class _LabelPayload(BaseModel):
    name: str
    color: str = ""
    description: str | None = None

    def label(self) -> RepositoryLabel:
        return RepositoryLabel(name=self.name, color=self.color, description=self.description or "")


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
        """The issue change this event reports, or None for pull requests and other events."""
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
    author_association: str | None = None

    def comment(self) -> IssueComment:
        return IssueComment(
            body=self.body,
            created_at=self.created_at,
            author_association=self.author_association,
        )


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


class _RepositoryPayload(BaseModel):
    """A repository as `repos/<owner>/<name>` gives it, with the keys `RepositoryFacts` keeps."""

    full_name: str
    html_url: str
    license: str | None = Field(default=None, validation_alias=AliasPath("license", "spdx_id"))
    archived: bool = False
    pushed_at: datetime | None = None
    stargazers_count: int = 0


class _ReleasePayload(BaseModel):
    """A release as `releases/latest` gives it."""

    tag_name: str
    published_at: datetime | None = None


_MILESTONE = TypeAdapter(_MilestonePayload)
_ISSUE = TypeAdapter(_IssuePayload)
_PULL = TypeAdapter(_PullPayload)
_LABEL = TypeAdapter(_LabelPayload)
_EVENT = TypeAdapter(_EventPayload)
_IS_PRIVATE = TypeAdapter(_IsPrivatePayload)
_REPOSITORY_PAYLOAD = TypeAdapter(_RepositoryPayload)
_RELEASE = TypeAdapter(_ReleasePayload)
_COMMENT = TypeAdapter(_CommentPayload)
_TIMELINE = TypeAdapter(_TimelinePayload)
_WORKFLOW_RUN = TypeAdapter(_WorkflowRunPayload)
_COMMITS = TypeAdapter(list[_CommitPayload])
_ANY_OBJECT = TypeAdapter(dict[str, Any])

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


def pulls_endpoint(repo: str) -> str:
    """The REST listing of the open pull requests of `repo`."""
    return f"repos/{repo}/pulls?state=open"


def labels_endpoint(repo: str) -> str:
    """The REST listing of the labels of `repo`."""
    return f"repos/{repo}/labels"


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


def issue_args(repo: str, number: Number) -> list[str]:
    return ["api", f"repos/{repo}/issues/{number}"]


def issue_edit_args(repo: str, number: Number) -> list[str]:
    """The REST write of issue `number`, its fields as JSON on stdin (`issue_edit`)."""
    return ["api", "-X", "PATCH", f"repos/{repo}/issues/{number}", "--input", "-"]


def issue_edit(*, labels: Sequence[str] | None = None, body: str | None = None) -> str:
    """The stdin of an `issue_edit_args` write: the labels that replace the issue's, and its
    whole body, each only when given."""
    fields: dict[str, Any] = {}
    if labels is not None:
        fields["labels"] = list(labels)
    if body is not None:
        fields["body"] = body
    return json.dumps(fields)


def issue_close(reason: CloseReason) -> str:
    """The stdin of an `issue_edit_args` write that closes the issue for `reason`."""
    return json.dumps({"state": GitHubState.CLOSED.value, "state_reason": reason.value})


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


def add_sub_issue_args(repo: str, parent: Number, child_id: Number) -> list[str]:
    return [
        "api",
        "-X",
        "POST",
        f"repos/{repo}/issues/{parent}/sub_issues",
        "-F",
        f"sub_issue_id={child_id}",
    ]


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


def repository_args(full_name: str) -> list[str]:
    """The `gh` arguments that read the repository `full_name`."""
    return ["api", f"repos/{full_name}"]


def latest_release_args(full_name: str) -> list[str]:
    """The `gh` arguments that read the latest release of the repository `full_name`; GitHub
    answers 404 for a repository with none."""
    return ["api", f"repos/{full_name}/releases/latest"]


def is_private_args(repo: str) -> list[str]:
    """The `gh` arguments that query whether `repo` is private."""
    return repository_query_args(repo, _IS_PRIVATE_QUERY)


def closures_args(repo: str, number: Number) -> list[str]:
    return repository_query_args(
        repo, _CLOSURES_QUERY, first=DEFAULT_GH_ISSUE_TIMELINE_LIMIT, number=number
    )


# ── Adapter ───────────────────────────────────────────────────────────────────


class GitHubRoadmapStore(RoadmapStore):
    """The roadmap on GitHub, read and written as whoever `gh` is logged in as. One store lives
    for one command or one Service round: it keeps the listing of every issue for its life."""

    def __init__(
        self,
        repo: str,
        *,
        runner: GhRunner = run_gh,
        session: ListingSession | None = None,
    ) -> None:
        self._repo = repo
        # The REST listings are read through this session, or the process's when it is None.
        self._session = session
        self._runner = runner
        # Every issue and pull request by number, read once when first needed.
        self._all: dict[int, IssueRecord] | None = None
        # The value this store last wrote to each field of each issue.
        self._written: dict[tuple[int, ItemField], str | None] = {}
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
        """The Item numbered `number`, from one read of its issue, or None when the issue holds
        no Priority, is a pull request or does not exist."""
        found = self._read_or_none(issue_args(self._repo, number), _ISSUE, f"issue #{number}")
        return None if found is None else next(iter(select_items([found.record()])), None)

    def items(self, *, milestone: int | None = None) -> list[Item]:
        """Every Item, open and closed, or only those in the milestone numbered `milestone`."""
        if milestone is None:
            return select_items(self._every_issue())
        return select_items(self._read_issues(f"milestone={milestone}&state=all"))

    def backlog(self) -> list[Item]:
        """The open Items in no milestone."""
        return select_items(self._read_issues("milestone=none&state=open"))

    def open_items(self) -> list[Item]:
        """The open Items, from the listing of open issues: one page for each 100 open issues
        and pull requests, and no read of the closed ones."""
        return select_items(self._read_issues("state=open"))

    def open_pulls(self) -> list[OpenPull]:
        """The open pull requests, one page for each 100."""
        listing = self._listing(pulls_endpoint(self._repo), _PULL, "pull requests")
        return [pull.pull() for pull in listing]

    def repository_labels(self) -> list[RepositoryLabel]:
        """The labels of the repository, one page for each 100."""
        listing = self._listing(labels_endpoint(self._repo), _LABEL, "labels")
        return [label.label() for label in listing]

    def candidates(self) -> list[Candidate]:
        """The open issues of the repository that hold no Priority."""
        return select_candidates(self._every_issue())

    def changes_since(self, since: datetime, *, except_actor: str | None = None) -> list[Change]:
        """The issue changes the issue events report at or after `since`, oldest first (#1360),
        without those `except_actor` made; an empty actor leaves out nothing."""
        cutoff = as_utc(since)
        skipped = except_actor or None
        events = self._listing(
            repository_issue_events_endpoint(self._repo),
            _EVENT,
            "issue events",
            ends=lambda event: event.created_at < cutoff,
        )
        return [
            change
            for event in reversed(events)
            if (change := event.change()) is not None
            and change.at >= cutoff
            and (skipped is None or change.actor != skipped)
        ]

    def set_field(
        self,
        item: Item,
        field: ItemField,
        value: str | None,
        *,
        marks: Mapping[Any, str | None] | None = None,
    ) -> None:
        """Replace the field's label family and record the value, with `marks`, in one `PATCH`
        of the issue, after one read of it. The value joins the job record the issue holds at
        that read, not the one `item` was read with, so two writes from one read both stay
        recorded. A field someone changed since the store read it raises before any write,
        unless the issue already holds `value` (ADR 0002)."""
        operation = "roadmap.item.set_field"
        require_value(field, value, operation)
        with _JOB_RECORD_LOCK:
            issue = self._require_issue(item.number, operation)
            now = item_of(issue.record()).field_value(field)
            read = self._written.get((item.number, field), item.field_value(field))
            require_unchanged(f"#{item.number}", field, read, now, value, operation)
            labels = relabeled(issue.label_names, field, value)
            self._edit_issue(issue, labels=labels, changes={field: value, **(marks or {})})
            self._written[(item.number, field)] = value

    def set_marks(self, item: Item, marks: Mapping[Any, str | None]) -> None:
        """Set or clear a job's marks in the Item's job record, as its issue holds it now, in
        one `PATCH` of the body after one read of the issue."""
        with _JOB_RECORD_LOCK:
            issue = self._require_issue(item.number, "roadmap.item.set_marks")
            self._edit_issue(issue, changes=marks)

    # ── Issues ──

    def issues(self) -> list[IssueRecord]:
        """Every issue, open and closed, Item or not; never pull requests."""
        return [issue for issue in self._every_issue() if not issue.pull_request]

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        """Open an issue with `title`, `body` and `labels`, returning it."""
        written = self._write(
            create_issue_args(self._repo, title, body, labels), f"open the issue {title[:64]!r}"
        )
        return self._kept(self._validate(written, _ISSUE, "issue after it was opened"))

    def add_sub_issue(self, parent: int, child: int) -> None:
        """Add issue `child` as a sub-issue of issue `parent`."""
        if self._all is None or parent not in self._all:
            self._require_issue(parent, "roadmap.add_sub_issue")
        child_id = None
        if self._all is not None and child in self._all and self._all[child].id:
            child_id = self._all[child].id
        if child_id is None:
            child_payload = self._require_issue(child, "roadmap.add_sub_issue")
            child_id = child_payload.id
        self._write(
            add_sub_issue_args(self._repo, parent, child_id),
            f"link #{child} as a sub-issue of #{parent}",
        )
        if self._all is not None:
            if parent in self._all:
                p = self._all[parent]
                self._all[parent] = p.model_copy(update={"sub_issues": p.sub_issues + 1})
            if child in self._all:
                c = self._all[child]
                self._all[child] = c.model_copy(update={"parent": parent})

    def read_issue_body(self, number: int) -> str:
        """The body of issue `number`, with no record block, raising if it is not an issue of
        this repository."""
        return self._require_issue(number, "roadmap.issue.read_body").split()[0]

    def write_issue_body(self, number: int, body: str) -> None:
        """Write `body` as the body of issue `number`, with the record block it holds, raising
        if it is not an issue of this repository."""
        with _JOB_RECORD_LOCK:
            issue = self._require_issue(number, "roadmap.issue.write_body")
            _, held = issue.split()
            block = encode_job_record(held, {}) if held else None
            self._send_edit(number, issue_edit(body=with_record(body, block)))

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

    def close(self, number: int, reason: CloseReason, *, comment: str | None = None) -> None:
        """Read issue `number`, post `comment` on it when given, then close it for `reason` in
        one `PATCH` (#1658). A pull request, a missing issue and a closed issue are refused
        before any write."""
        issue = self._require_issue(number, "roadmap.issue.close")
        if issue.state is GitHubState.CLOSED:
            raise already_closed(number, {"repo": self._repo[:256], "number": number})
        if comment is None:
            self._send_edit(number, issue_close(reason))
            return
        self.comment(number, comment)
        try:
            self._send_edit(number, issue_close(reason))
        except GitHubOperationError as exc:
            raise GitHubOperationError(
                f"{exc} The comment is on #{number}, and #{number} is still open. Close it "
                "again with no comment.",
                operation="roadmap.issue.close",
                details={"repo": self._repo[:256], "number": number},
            ) from exc

    # ── What intake reads and writes ──

    def closures(self, number: int) -> list[Closure]:
        """Every close and reopen of issue `number` from its timeline, oldest first."""
        timeline = self._read(closures_args(self._repo, number), _TIMELINE, f"#{number} timeline")
        self._require_whole(len(timeline.nodes), timeline.total_count, f"#{number} closes")
        return [node.closure() for node in timeline.nodes]

    def label_issue(self, number: int, label: str) -> None:
        """Add `label` to issue or pull request `number`; GitHub keeps its other labels."""
        self._write(label_args(self._repo, number, label), f"label #{number} {label}")
        kept = (self._all or {}).get(number)
        if kept is not None and label not in kept.labels:
            self._all = (self._all or {}) | {
                number: kept.model_copy(update={"labels": (*kept.labels, label)})
            }

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

    def repository_facts(self, full_name: str) -> RepositoryFacts | None:
        """The facts of the repository `full_name`: one read of the repository, and one of its
        latest release when it exists. None when GitHub has no such repository (#2650). A name
        that is not `owner/name` is refused before any request."""
        if not is_repository_name(full_name):
            raise GitHubOperationError(
                f"{full_name[:80]} is not a repository name.",
                operation="roadmap.read",
                details={"name": full_name[:256]},
            )
        repository = self._read_or_none(
            repository_args(full_name), _REPOSITORY_PAYLOAD, f"the repository {full_name}"
        )
        if repository is None:
            return None
        release = self._read_or_none(
            latest_release_args(full_name), _RELEASE, f"the latest release of {full_name}"
        )
        return RepositoryFacts(
            full_name=repository.full_name,
            url=repository.html_url,
            license=repository.license,
            archived=repository.archived,
            pushed_at=repository.pushed_at,
            stars=repository.stargazers_count,
            latest_release=release.tag_name if release else None,
            released_at=release.published_at if release else None,
        )

    # ── Writes ──

    def _require_issue(self, number: int, operation: str) -> _IssuePayload:
        """Issue `number` as GitHub holds it now, raising when it is a pull request or no issue
        of this repository."""
        found = self._read_or_none(issue_args(self._repo, number), _ISSUE, f"issue #{number}")
        if found is None or found.pull_request is not None:
            raise GitHubOperationError(
                f"#{number} is not an issue of {self._repo}.",
                operation=operation,
                details={"repo": self._repo[:256], "number": number},
            )
        return found

    def _edit_issue(
        self,
        issue: _IssuePayload,
        *,
        changes: Mapping[Any, str | None],
        labels: Sequence[str] | None = None,
    ) -> None:
        """One `PATCH` of `issue`: `labels` when given, and its body with the record block it
        holds, `changes` made."""
        body, held = issue.split()
        block = encode_job_record(held, changes)
        self._send_edit(issue.number, issue_edit(labels=labels, body=with_record(body, block)))

    def _send_edit(self, number: int, stdin: str) -> None:
        """Send one `PATCH` of issue `number`, keeping the issue GitHub returns."""
        written = self._write(
            issue_edit_args(self._repo, number), f"write issue #{number}", input=stdin
        )
        self._kept(self._validate(written, _ISSUE, f"issue #{number} after it was written"))

    def _kept(self, issue: _IssuePayload) -> IssueRecord:
        """The issue as a record, kept in the listing of every issue when the store holds it."""
        record = issue.record()
        if self._all is not None:
            self._all = self._all | {record.number: record}
        return record

    def _write(self, args: list[str], action: str, *, input: str | None = None) -> str:
        proc = self._run(args, input=input)
        if proc.returncode != 0:
            raise self._failure(proc, action, "roadmap.write")
        return proc.stdout or ""

    # ── Reads ──

    def _every_issue(self) -> list[IssueRecord]:
        """Every issue and pull request, read the first time the store needs them."""
        if self._all is None:
            self._all = {issue.number: issue for issue in self._read_issues("state=all")}
        return list(self._all.values())

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
        return self._runner(args, input=input, check=False, quiet=True, use_cache=False)

    def _failure(
        self, proc: subprocess.CompletedProcess[str], action: str, operation: str
    ) -> GitHubOperationError:
        """The error for a failed gh command: the class the gh classifier names from gh's
        stderr, such as `GitHubRateLimitError`, else a failure to do `action`. gh's stdout holds
        GitHub's answer, possibly partial data with item titles, and is never classified."""
        output = f"{proc.stderr or ''} {proc.stdout or ''}".strip()
        classified = classify_gh_failure(
            proc.stderr or "", exit_code=proc.returncode, operation=operation
        )
        return classified or GitHubOperationError(
            f"Could not {action} in {self._repo} (exit {proc.returncode}): {output[:256]}",
            operation=operation,
            details={"repo": self._repo[:256], "exit_code": proc.returncode},
        )


__all__ = [
    "GhRunner",
    "GitHubRoadmapStore",
    "ListingSession",
    "add_sub_issue_args",
    "advisory_args",
    "closures_args",
    "comment_args",
    "comments_endpoint",
    "commit_args",
    "create_issue_args",
    "is_private_args",
    "issue_args",
    "issue_edit",
    "issue_edit_args",
    "issues_endpoint",
    "label_args",
    "listing_path",
    "milestone_edit_args",
    "milestones_endpoint",
    "path_commits_args",
    "repository_file_args",
    "repository_issue_events_endpoint",
    "repository_query_args",
    "workflow_run_args",
]
