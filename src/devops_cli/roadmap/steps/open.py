"""The roadmap step `open`: open, update or recover the pull request (#5020).

Consolidates draft pull request creation across stage, implement, and recovery sweeps:
- Checks every attribute with the rules that CI runs before it writes the pull request (#5974): a
  diff of runtime code gets a type that ships a release (`release_title`), a scope that
  `.github/labels.yml` declares, a summary that the check `Semantic PR title` accepts, and a body
  that closes only the delivered issue, or `Plans #N` for a plan (`pull_form`).
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

import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubUnauthenticatedError,
)
from devops_cli.exceptions.roadmap import RoadmapOpenRefusedError
from devops_cli.git.branch_form import issue_of_branch
from devops_cli.github.client import missing_pull_reviewers
from devops_cli.github.release_title import (
    ADDED_STATUS,
    RELEASE_CONFIG_PATH,
    hidden_types,
    shipping_title,
)
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.pull_form import (
    open_body_problems,
    title_problems,
    title_with_declared_scope,
)
from devops_cli.roadmap.pull_labels import (
    add_pull_labels,
    declared_labels,
    read_title_labels,
    remove_pull_labels,
    stale_labels,
)
from devops_cli.roadmap.status_sync import StatusFacts, write_status
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    RoadmapStore,
    StageRecordKey,
)
from devops_cli.roadmap.title_labels import declared_label_names, title_labels

if TYPE_CHECKING:
    from devops_cli.github.client import OpenPullRequest, PullRequestFile
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
    title: str = ""

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
        if self.title:
            data["title"] = self.title
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
    reviewers: Sequence[str] = ()
    # The files of the diff of the head, when the caller read them: the step then reads no diff.
    changed: Sequence[PullRequestFile] | None = None


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


def _declared(request: OpenRequest) -> tuple[str, ...] | None:
    """The label names that `.github/labels.yml` declares on the base branch, or None when the
    repository has no such file: then no scope is checked against it. Another failed read raises."""
    try:
        if request.store is not None:
            return declared_labels(request.store, ref=request.base)
        text = get_github_session().client.get_file_at(
            request.repo, CONST_ROADMAP_LABELS_PATH, request.base
        )
    except GitHubFileNotFoundError:
        return None
    if text is None:
        return None
    try:
        return declared_label_names(text)
    except (yaml.YAMLError, ValidationError) as exc:
        raise RoadmapOpenRefusedError(
            MESSAGES.roadmap.open_file_unreadable.format(
                path=CONST_ROADMAP_LABELS_PATH, error=str(exc)[:200]
            )
        ) from exc


def _release_config(request: OpenRequest) -> dict[str, Any]:
    """The release-please config on the base branch, or an empty config when the repository has
    none: a repository with no release-please hides no type. Another failed read raises."""
    try:
        if request.store is not None:
            text: str | None = request.store.repository_file(RELEASE_CONFIG_PATH, ref=request.base)
        else:
            text = get_github_session().client.get_file_at(
                request.repo, RELEASE_CONFIG_PATH, request.base
            )
    except GitHubFileNotFoundError:
        return {}
    if text is None:
        return {}
    try:
        config = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RoadmapOpenRefusedError(
            MESSAGES.roadmap.open_file_unreadable.format(path=RELEASE_CONFIG_PATH, error=exc.msg)
        ) from exc
    return config if isinstance(config, dict) else {}


def _shipping_title(request: OpenRequest, title: str, config: dict[str, Any]) -> str:
    """`title` with a type that ships a release when the diff of the head changes runtime code
    under a hidden type (#5974). The diff is read only for a hidden type, and only when the
    request holds no files of it."""
    if commit_type(title) not in hidden_types(config):
        return title
    files = request.changed
    if files is None:
        client = get_github_session().client
        files = client.get_compare_files(request.repo, request.base, request.head).files
    paths = [changed.filename for changed in files]
    added = [changed.filename for changed in files if changed.status == ADDED_STATUS]
    shipped = shipping_title(title, paths, added, config)
    if shipped != title:
        logger.info(MESSAGES.roadmap.open_title_retyped, request.head, title, shipped)
    return shipped


def checked_request(request: OpenRequest, declared: tuple[str, ...] | None) -> OpenRequest:
    """`request` with the title and the body that the rules of CI accept (#5974). The step fixes
    what a rule can decide: a title on one line, a type that ships a release for a diff of runtime
    code, and no scope that `declared` lacks. Any other problem of the title or the body raises
    `RoadmapOpenRefusedError` that names every problem, and the step writes nothing."""
    title = title_with_declared_scope(request.title, declared)
    title = _shipping_title(request, title, _release_config(request))
    issue = request.item or issue_of_branch(request.head)
    problems = [
        *title_problems(title, declared),
        *open_body_problems(request.body, issue=issue, plan=request.kind == "plan"),
    ]
    if problems:
        raise RoadmapOpenRefusedError(
            MESSAGES.roadmap.open_attributes_refused.format(
                title=title, problems=" ".join(problems)
            )
        )
    return replace(request, title=title)


def _upsert_marked_comment(repo: str, pull_number: int, comment_body: str) -> bool:
    """Upsert one marked comment on pull request `pull_number` (#5020, #5025)."""
    marker = ""
    for line in comment_body.splitlines():
        if line.startswith("<!--") and line.endswith("-->"):
            marker = line.strip()
            break
    target = Target(repo, pull_number)
    return post(target, marker, None, comment_body)


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


def _resolve_desired_labels(request: OpenRequest, declared: tuple[str, ...] | None) -> set[str]:
    """The labels of the request and the labels that its checked title gives (#5974): the type
    label follows the type that the step wrote. A store-less request gets the labels it names."""
    desired_labels: set[str] = set(request.labels)
    if request.store and declared is not None:
        desired_labels.update(title_labels(request.title, declared).labels)
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
        title=request.title,
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

    reviewers = missing_pull_reviewers(
        request.reviewers, author=created.author, existing=created.requested_reviewers
    )
    if reviewers:
        client.request_pull_reviewers(request.repo, created.number, reviewers)

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
        title=request.title,
    )


def open_or_update(request: OpenRequest) -> OpenResult:
    """Open a new draft pull request or update an existing one (#5020).

    Returns `OpenResult` with the pull request number and status (`created`, `updated`, or `unchanged`).
    """
    _check_refusals(request)

    if request.dry_run:
        return OpenResult(number=0, status=OpenStatus.CREATED)

    declared = _declared(request)
    request = checked_request(request, declared)
    client = get_github_session().client
    existing = (
        client.find_open_pull(request.repo, head=request.head, base=request.base)
        if request.lookup_existing
        else None
    )
    target_issue = request.item or issue_of_branch(request.head)
    desired_labels = _resolve_desired_labels(request, declared)

    if existing is not None:
        return _handle_existing_pull(request, existing, desired_labels, target_issue)

    return _handle_new_pull(request, desired_labels, target_issue)
