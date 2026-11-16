"""The roadmap step `comment`: one shared marked-comment writer (#5025).

Acceptance criteria:
- An upsert edits the comment.
- A second run posts nothing.
- The repeat guard of the store refuses a repeat.
- The writer reads marked comments before writing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from devops_cli.exceptions.git import GitHubNotFoundError
from devops_cli.github.client import IssueComment as ClientIssueComment
from devops_cli.github.session import get_github_session

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient
    from devops_cli.roadmap.stores.store import RoadmapStore

logger = logging.getLogger(__name__)


class Target:
    """Target for a roadmap marked comment (an issue or a pull request)."""

    def __init__(
        self,
        repo: str,
        number: int,
        *,
        store: RoadmapStore | None = None,
        client: GitHubClient | None = None,
    ) -> None:
        self.repo = repo
        self.number = number
        self.store = store
        self.client = client
        self._cached_comments: list[Any] | None = None

    def _get_client(self) -> GitHubClient:
        if self.client is not None:
            return self.client
        return get_github_session().client

    def list_comments(self) -> Sequence[Any]:
        """List existing comments on the target."""
        if self._cached_comments is not None:
            return self._cached_comments
        if self.store is not None:
            self._cached_comments = list(self.store.comments_on(self.number))
            return self._cached_comments
        try:
            self._cached_comments = list(
                self._get_client().list_issue_comments(self.repo, self.number)
            )
            return self._cached_comments
        except GitHubNotFoundError:
            self._cached_comments = []
            return []

    def create_comment(self, body: str) -> int | bool | None:
        """Create a new comment on the target."""
        if self.store is not None:
            created = self.store.comment(self.number, body)
            if created and self._cached_comments is not None:
                self._cached_comments = list(self.store.comments_on(self.number))
            return created if created else None
        comment_id = self._get_client().comment_on_pull(self.repo, self.number, body)
        if self._cached_comments is not None and comment_id is not None:
            cid = comment_id if isinstance(comment_id, int) else 0
            self._cached_comments.append(ClientIssueComment(id=cid, body=body))
        return comment_id

    def _update_store_comment(self, comment_id: int | None, body: str) -> None:
        if self.store is None:
            return
        if hasattr(self.store, "_roadmap"):
            for i, c in enumerate(self.store._roadmap.comments.get(self.number, [])):
                if getattr(c, "id", None) == comment_id or i == comment_id:
                    self.store._roadmap.comments[self.number][i] = c.model_copy(
                        update={"body": body}
                    )
                    break
        else:
            store_write = getattr(self.store, "_write", None)
            if callable(store_write):
                store_write(
                    [
                        "api",
                        "-X",
                        "PATCH",
                        f"repos/{self.repo}/issues/comments/{comment_id}",
                        "-f",
                        f"body={body}",
                    ],
                    f"comment update on #{self.number}",
                )
        if self._cached_comments is not None:
            self._cached_comments = list(self.store.comments_on(self.number))

    def _update_client_comment(self, comment_id: int, body: str) -> None:
        self._get_client().update_issue_comment(self.repo, comment_id, body)
        if self._cached_comments is None:
            return
        for i, c in enumerate(self._cached_comments):
            if getattr(c, "id", None) == comment_id:
                self._cached_comments[i] = _with_body(c, body)
                break

    def update_comment(self, comment_id: int | None, body: str) -> None:
        """Update an existing comment on the target."""
        if self.store is not None:
            self._update_store_comment(comment_id, body)
        elif comment_id is not None:
            self._update_client_comment(comment_id, body)


def _with_body(comment: Any, body: str) -> Any:
    if hasattr(comment, "model_copy"):
        return comment.model_copy(update={"body": body})
    if hasattr(comment, "body"):
        setattr(comment, "body", body)
    return comment


def post(target: Target | Any, marker: str, key: str | None, body: str) -> bool:
    """Post or update a marked comment on `target`.

    Reads comments first. If an existing comment holds `marker` and `key`, updates it
    when the body differs, or makes no write when identical. If no matching comment exists,
    creates the comment, allowing the repeat guard to refuse a duplicate.
    Returns True when a write occurred, False otherwise.
    """
    comments = target.list_comments()

    matching = None
    for comment in comments:
        c_body = getattr(comment, "body", "")
        if marker and marker in c_body and (not key or key in c_body):
            matching = comment
            break

    if matching is not None:
        c_body = getattr(matching, "body", "")
        if c_body.strip() == body.strip():
            return False
        if hasattr(target, "update_comment"):
            target.update_comment(getattr(matching, "id", None), body)
            return True

    created = target.create_comment(body)
    return bool(created)


__all__ = ["Target", "post"]
