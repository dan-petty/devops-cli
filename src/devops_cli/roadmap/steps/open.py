"""The roadmap step `open`: open, update or recover the pull request (#5020).

Consolidates draft pull request creation across stage, implement, and recovery sweeps:
- Looks up open pull request for the head and base branches first.
- If it exists, updates only the fields that differ (title, body, labels).
- If none exists, creates a draft pull request.
- If GitHub refuses the text, retries once with form-checked text (#3599).
- For a delivery pull request, sets Status to In Progress through `write_status`.
- Records `<kind>.pr` in the item record.
- Upserts marked comment if provided.
- Refuses second open pull request for an issue, and refuses heads with `[skip ci]`.
- Sweep recovery recovers an un-opened PR when head matches `checked_sha` in at most 3 requests.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from devops_cli.exceptions.git import GitHubOperationError, GitHubUnauthenticatedError
from devops_cli.exceptions.roadmap import RoadmapOpenRefusedError
from devops_cli.git.branch_form import issue_of_branch
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.pull_labels import (
    add_pull_labels,
    read_title_labels,
    remove_pull_labels,
    stale_labels,
)
from devops_cli.roadmap.status_sync import StatusFacts, write_status
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    RoadmapStore,
    StageRecordKey,
)

if TYPE_CHECKING:
    from devops_cli.github.client import OpenPullRequest
    from devops_cli.roadmap.stores.store import Item

logger = logging.getLogger(__name__)


class OpenStatus(StrEnum):
    """The result status of the open step on a pull request (#5020)."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class OpenResult:
    """The outcome of opening or updating a pull request."""

    number: int
    status: OpenStatus
    html_url: str = ""
    labels: tuple[str, ...] = ()

    def __iter__(self) -> Iterator[int | OpenStatus]:
        yield self.number
        yield self.status

    def to_json(self) -> str:
        """The JSON result line of the open step."""
        import json

        data = {
            "job": "open",
            "number": self.number,
            "status": self.status.value,
        }
        if self.html_url:
            data["html_url"] = self.html_url
        if self.labels:
            data["labels"] = list(self.labels)
        return json.dumps(data)


@dataclass(frozen=True)
class OpenRequest:
    """The request parameters for the open step."""

    repo: str
    head: str
    base: str
    title: str
    body: str
    kind: str = "delivery"
    item: int | None = None
    store: RoadmapStore | None = None
    dry_run: bool = False
    comment_body: str | None = None
    labels: Sequence[str] = ()
    producer_sha: str | None = None
    head_commit_message: str | None = None
    lookup_existing: bool = True
    retry_refused: bool = True


def is_recovery_due(
    item: Item,
    *,
    branch_head_sha: str | None = None,
    store: RoadmapStore | None = None,
) -> bool:
    """Whether the open step is due to recover a pull request for `item` (#5020).

    Due when the branch head equals `checked_sha` in the record and no open PR exists.
    """
    checked = item.job_record.get(ImplementRecordKey.CHECKED_SHA) or item.job_record.get(
        StageRecordKey.SHA
    )
    if not checked or (branch_head_sha and checked != branch_head_sha):
        return False
    if store is not None:
        open_pr = next(
            (p for p in store.open_pulls() if issue_of_branch(p.head_ref) == item.number),
            None,
        )
        if open_pr is not None:
            return False
    return True


def recover_open(request: OpenRequest) -> OpenResult:
    """Recover and open a pull request that a killed unit did not open (#5020)."""
    return open_or_update(request)


def _check_refusals(request: OpenRequest) -> None:
    """Check whether the request should be refused due to marker or second PR."""
    if request.head_commit_message and "[skip ci]" in request.head_commit_message:
        raise RoadmapOpenRefusedError("Commit message contains [skip ci].")

    target_issue = request.item or issue_of_branch(request.head)
    if target_issue and request.store:
        for pull in request.store.open_pulls():
            pull_issue = issue_of_branch(pull.head_ref)
            if pull_issue == target_issue and pull.head_ref != request.head:
                raise RoadmapOpenRefusedError(
                    f"Issue #{target_issue} already has an open pull request #{pull.number} on branch '{pull.head_ref}'."
                )


def _form_checked_text(title: str, body: str) -> tuple[str, str]:
    """Sanitize and format title and body according to pull form rules."""
    clean_title = " ".join(title.strip().splitlines())
    clean_body = body.strip()
    return clean_title, clean_body


def _upsert_marked_comment(repo: str, pull_number: int, comment_body: str) -> bool:
    """Upsert one marked comment on pull request `pull_number` (#5020)."""
    client = get_github_session().client
    marker = None
    for line in comment_body.splitlines():
        if line.startswith("<!--") and line.endswith("-->"):
            marker = line.strip()
            break
    if not marker:
        client.comment_on_pull(repo, pull_number, comment_body)
        return True

    existing_comments = client.list_issue_comments(repo, pull_number)
    for c in existing_comments:
        if marker in c.body:
            if c.body != comment_body:
                client.update_issue_comment(repo, c.id, comment_body)
                return True
            return False

    client.comment_on_pull(repo, pull_number, comment_body)
    return True


def _record_pr_marks(
    store: RoadmapStore | None, item_num: int | None, kind: str, pr_num: int
) -> None:
    """Record `<kind>.pr` in the item record."""
    if not store or not item_num:
        return
    item = store.item(item_num)
    if not item:
        return
    key = StageRecordKey.PR if kind == "plan" else ImplementRecordKey.PR
    store.set_marks(item, {key: str(pr_num)})


def _sync_status(store: RoadmapStore | None, item_num: int | None, kind: str) -> None:
    """Set In Progress through write_status for delivery pull requests."""
    if kind != "delivery" or not store or not item_num:
        return
    item = store.item(item_num)
    if not item:
        return
    write_status(store, item, StatusFacts(pull_open=True))


def _resolve_desired_labels(request: OpenRequest) -> set[str]:
    """Resolve desired labels including title labels from the store."""
    desired_labels: set[str] = set(request.labels)
    if request.store:
        try:
            read_labels = read_title_labels(request.store, request.title, ref=request.base)
            desired_labels.update(read_labels.labels)
        except (GitHubOperationError, GitHubUnauthenticatedError, KeyError, ValueError) as exc:
            logger.debug("Could not read title labels for %s: %s", request.title, exc)
    return desired_labels


def _update_existing_labels(
    request: OpenRequest, existing: OpenPullRequest, title_diff: bool
) -> bool:
    """Update labels of an existing pull request if needed, returning True if labels changed."""
    if not request.store:
        return False
    existing_labels_set = set(existing.labels)
    to_add = set()
    to_remove = set()
    try:
        old_title_labels = read_title_labels(request.store, existing.title, ref=request.base)
        new_title_labels = read_title_labels(request.store, request.title, ref=request.base)
        desired_title_set = set(new_title_labels.labels) | set(request.labels)
        to_add = desired_title_set - existing_labels_set
        if title_diff:
            to_remove = set(stale_labels(existing.labels, old_title_labels, new_title_labels))
    except (GitHubOperationError, GitHubUnauthenticatedError, KeyError, ValueError) as exc:
        logger.debug("Could not resolve label differences for PR #%s: %s", existing.number, exc)

    labels_changed = False
    if to_add:
        add_pull_labels(request.store, existing.number, tuple(to_add))
        labels_changed = True
    if to_remove:
        remove_pull_labels(request.store, existing.number, tuple(to_remove))
        labels_changed = True
    return labels_changed


def _handle_existing_pull(
    request: OpenRequest,
    existing: OpenPullRequest,
    desired_labels: set[str],
    target_issue: int | None,
) -> OpenResult:
    """Update an existing pull request and record marks."""
    client = get_github_session().client
    title_diff = existing.title != request.title
    body_diff = existing.body != request.body

    if title_diff or body_diff:
        client.update_pull(
            request.repo,
            existing.number,
            title=request.title if title_diff else None,
            body=request.body if body_diff else None,
        )

    labels_changed = _update_existing_labels(request, existing, title_diff)

    comment_changed = False
    if request.comment_body:
        comment_changed = _upsert_marked_comment(
            request.repo, existing.number, request.comment_body
        )

    _record_pr_marks(request.store, target_issue, request.kind, existing.number)
    _sync_status(request.store, target_issue, request.kind)

    status = (
        OpenStatus.UPDATED
        if (title_diff or body_diff or labels_changed or comment_changed)
        else OpenStatus.UNCHANGED
    )
    return OpenResult(
        number=existing.number,
        status=status,
        html_url=existing.html_url,
        labels=tuple(desired_labels | set(existing.labels)),
    )


def _handle_new_pull(
    request: OpenRequest, desired_labels: set[str], target_issue: int | None
) -> OpenResult:
    """Create a new draft pull request, label it, and record marks."""
    client = get_github_session().client
    try:
        created = client.create_draft_pull(
            request.repo,
            title=request.title,
            body=request.body,
            head=request.head,
            base=request.base,
        )
    except GitHubOperationError:
        if not request.retry_refused:
            raise
        # Retry once with form-checked text (#3599)
        clean_title, clean_body = _form_checked_text(request.title, request.body)
        created = client.create_draft_pull(
            request.repo,
            title=clean_title,
            body=clean_body,
            head=request.head,
            base=request.base,
        )

    if request.store and desired_labels:
        try:
            add_pull_labels(request.store, created.number, tuple(desired_labels))
        except (GitHubOperationError, GitHubUnauthenticatedError) as exc:
            logger.warning("Could not apply labels to PR #%s: %s", created.number, exc)

    if request.comment_body:
        _upsert_marked_comment(request.repo, created.number, request.comment_body)

    _record_pr_marks(request.store, target_issue, request.kind, created.number)
    _sync_status(request.store, target_issue, request.kind)

    return OpenResult(
        number=created.number,
        status=OpenStatus.CREATED,
        html_url=created.html_url,
        labels=tuple(desired_labels),
    )


def open_or_update(request: OpenRequest) -> OpenResult:
    """Open a new draft pull request or update an existing one (#5020).

    Returns `OpenResult` with the pull request number and status (`created`, `updated`, or `unchanged`).
    """
    _check_refusals(request)

    if request.dry_run:
        return OpenResult(number=0, status=OpenStatus.CREATED)

    client = get_github_session().client
    existing = (
        client.find_open_pull(request.repo, head=request.head, base=request.base)
        if request.lookup_existing
        else None
    )
    target_issue = request.item or issue_of_branch(request.head)
    desired_labels = _resolve_desired_labels(request)

    if existing is not None:
        return _handle_existing_pull(request, existing, desired_labels, target_issue)

    return _handle_new_pull(request, desired_labels, target_issue)
