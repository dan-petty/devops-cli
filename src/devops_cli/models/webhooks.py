"""Typed webhook payloads: the fields the Service reads, validated after the delivery's signature."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WebhookRepository(BaseModel):
    """The repository a GitHub event is about. `private` is the visibility that GitHub gives in
    each delivery: true for a private and for an internal repository. It is None for a payload
    that does not carry it."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    full_name: str
    private: bool | None = None


class WebhookSender(BaseModel):
    """The account whose action caused a GitHub event."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    login: str


class WebhookLabel(BaseModel):
    """A label of the issue an issue event is about."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str


class WebhookComment(BaseModel):
    """The comment an `issue_comment` event is about: its body, the commenter's relation to the
    repository as GitHub gives it (`OWNER`, `MEMBER`, `COLLABORATOR`, `NONE` and others) and the
    time it was made. A refusal reads the association and a scoped update reads the body."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    body: str
    author_association: str
    created_at: datetime


class WebhookPullRequestHead(BaseModel):
    """The head commit and ref of a pull request."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    sha: str | None = None
    ref: str | None = None


class WebhookPullRequest(BaseModel):
    """A pull request that an event is about."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    number: int | None = None
    state: str | None = None
    merged: bool | None = None
    merge_commit_sha: str | None = None
    head: WebhookPullRequestHead | None = None


class WebhookIssue(BaseModel):
    """The issue an issue event is about. `labels` and `state_reason` serve the count of closed
    roadmap items (#4580). `pull_request` marks the issue of a comment that is on a pull request,
    which GitHub reports as an issue event (#4415)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    number: int | None = None
    title: str = ""
    body: str = ""
    state: str = "open"
    labels: tuple[WebhookLabel, ...] = ()
    state_reason: str | None = None
    pull_request: WebhookPullRequest | None = None
    updated_at: datetime | None = None


class WebhookCheckSuite(BaseModel):
    """The check suite a check suite event is about. Its `pull_requests` names the pull requests
    whose head the suite checked, so a delivery reads the numbers with no further request."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    pull_requests: tuple[WebhookPullRequest, ...] = ()


class WebhookRelease(BaseModel):
    """The release a release event is about: its tag, the page a person reads, the notes that link
    the closed issues and the flags that a refusal reads. A draft carries no publication time."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    tag_name: str
    html_url: str
    body: str | None = None
    draft: bool = False
    prerelease: bool = False
    published_at: datetime | None = None


class GitHubWebhookPayload(BaseModel):
    """What every GitHub event carries that the Service reads. The rest of a payload differs by
    event and is ignored. An event has no `action` when GitHub gives it none (a `ping`, a `push`),
    and no `sender` when GitHub names no account."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    action: str | None = None
    repository: WebhookRepository
    sender: WebhookSender | None = None
    issue: WebhookIssue | None = None
    pull_request: WebhookPullRequest | None = None
    check_suite: WebhookCheckSuite | None = None
    comment: WebhookComment | None = None
    release: WebhookRelease | None = None

    @property
    def delivery_numbers(self) -> tuple[int, ...]:
        """The numbers of the pull requests that a delivery names, or the number of its issue. An
        event that names no number gives an empty tuple."""
        if self.issue is not None and self.issue.number is not None:
            return (self.issue.number,)
        if self.pull_request is not None and self.pull_request.number is not None:
            return (self.pull_request.number,)
        if self.check_suite is not None:
            return tuple(
                pull.number for pull in self.check_suite.pull_requests if pull.number is not None
            )
        return ()
