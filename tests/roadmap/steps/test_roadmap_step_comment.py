"""Tests for the shared marked-comment writer (#5025).

Acceptance criteria:
- An upsert edits the comment; a second run posts nothing; a repeat is refused.
- The writer reads marked comments before writing (read precedes write).
- A structural test fails when a module other than steps/comment.py calls comment_on_issue or comment_on_pull.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.stores.store import IssueComment
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

if TYPE_CHECKING:
    pass


class FakeCommentTarget:
    """A target for testing read-before-write, upserts, and repeat refusals."""

    def __init__(self, comments: list[IssueComment] | None = None) -> None:
        self.comments: list[IssueComment] = list(comments or [])
        self.recorded_calls: list[str] = []

    def list_comments(self) -> list[IssueComment]:
        self.recorded_calls.append("list")
        return list(self.comments)

    def create_comment(self, body: str) -> int:
        self.recorded_calls.append("create")
        comment_id = len(self.comments) + 1
        self.comments.append(
            IssueComment(
                id=comment_id,
                body=body,
                created_at=datetime.now(UTC),
                author_login="devops-cli[bot]",
            )
        )
        return comment_id

    def update_comment(self, comment_id: int, body: str) -> None:
        self.recorded_calls.append("update")
        for i, c in enumerate(self.comments):
            if c.id == comment_id:
                self.comments[i] = IssueComment(
                    id=comment_id,
                    body=body,
                    created_at=c.created_at,
                    author_login=c.author_login,
                )
                return


def test_upsert_edits_existing_comment() -> None:
    """When a target already holds a comment with the marker and key, edit that comment and add no
    second comment."""
    marker = "<!-- roadmap-test-marker -->"
    key = "run-101"
    old_body = f"{marker}\n{key}\n\nOld content"
    new_body = f"{marker}\n{key}\n\nNew updated content"

    target = FakeCommentTarget(
        comments=[
            IssueComment(
                id=42,
                body=old_body,
                created_at=datetime.now(UTC),
                author_login="devops-cli[bot]",
            )
        ]
    )

    posted = post(target, marker, key, new_body)

    assert posted is True
    assert len(target.comments) == 1
    assert target.comments[0].id == 42
    assert target.comments[0].body == new_body
    assert target.recorded_calls == ["list", "update"]


def test_read_precedes_write() -> None:
    """The target records a comment list before the create or update call."""
    marker = "<!-- roadmap-test-marker -->"
    key = "run-102"
    body = f"{marker}\n{key}\n\nFirst run"

    target = FakeCommentTarget()

    posted = post(target, marker, key, body)

    assert posted is True
    assert target.recorded_calls == ["list", "create"]


def test_second_run_posts_nothing() -> None:
    """When the same marker, key, and body already exist on the target, make no comment write."""
    marker = "<!-- roadmap-test-marker -->"
    key = "run-103"
    body = f"{marker}\n{key}\n\nExact content"

    target = FakeCommentTarget(
        comments=[
            IssueComment(
                id=7,
                body=body,
                created_at=datetime.now(UTC),
                author_login="devops-cli[bot]",
            )
        ]
    )

    posted = post(target, marker, key, body)

    assert posted is False
    assert len(target.comments) == 1
    # Only list was called, no create and no update
    assert target.recorded_calls == ["list"]


def test_repeat_is_refused_by_store_guard() -> None:
    """When the store guard refuses a repeated marked comment, post makes no comment write."""
    store = InMemoryRoadmapStore(repo="example/repo")
    issue_num = store.seed_issue("test issue")
    marker = CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER
    key = "run-104"
    body = f"{marker}\n{key}\n\nExact content"

    # Seed an existing comment directly in the store
    store.seed_comment(issue_num, body)

    target = Target(repo="example/repo", number=issue_num, store=store)

    # Calling post with a new key but identical fingerprint/recent text triggers store repeat refusal
    posted = post(target, marker, "run-other", body)

    assert posted is False
    assert len(store.comments_on(issue_num)) == 1


class _SimpleComment:
    def __init__(self, body: str) -> None:
        self.body = body


def test_target_with_client_coverage() -> None:
    """Test Target methods when using client."""
    from unittest.mock import MagicMock

    from devops_cli.exceptions.git import GitHubNotFoundError
    from devops_cli.github.client import IssueComment as ClientIssueComment

    client = MagicMock()
    client.list_issue_comments.return_value = [ClientIssueComment(id=1, body="existing")]
    client.comment_on_pull.return_value = 2

    target = Target("owner/repo", 10, client=client)

    # list_comments and cache check
    assert len(target.list_comments()) == 1
    assert len(target.list_comments()) == 1
    assert client.list_issue_comments.call_count == 1

    # create_comment
    assert target.create_comment("new comment") == 2
    assert len(target.list_comments()) == 2

    # update_comment
    target.update_comment(1, "updated")
    client.update_issue_comment.assert_called_once_with("owner/repo", 1, "updated")
    assert target.list_comments()[0].body == "updated"

    # update_comment with None id does nothing on client
    target.update_comment(None, "no-op")

    # 404 on list_comments
    client404 = MagicMock()
    client404.list_issue_comments.side_effect = GitHubNotFoundError("not found")
    target404 = Target("owner/repo", 10, client=client404)
    assert target404.list_comments() == []


def test_target_with_store_coverage() -> None:
    """Test Target methods when using store."""
    store = InMemoryRoadmapStore(repo="owner/repo")
    num = store.seed_issue("test issue")
    target = Target("owner/repo", num, store=store)

    assert target.list_comments() == []
    assert target.create_comment("first comment") is True
    assert len(target.list_comments()) == 1


def test_an_upsert_through_the_store_edits_the_marked_comment_by_its_id() -> None:
    """The store path edits the one comment that holds the marker and the key, by its id, with
    `RoadmapStore.edit_comment`, and the edit moves the time of its last edit (#6197). The comment
    of a person before it stays as it is."""
    times = iter(datetime(2026, 11, 17, hour, tzinfo=UTC) for hour in range(9, 24))
    store = InMemoryRoadmapStore(repo="owner/repo", clock=lambda: next(times))
    num = store.seed_issue("test issue")
    marker = CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER
    store.seed_comment(num, "A note of a person.", author_login="alice")
    store.comment(num, f"{marker}\nrun-1\n\nOld state")

    posted = post(
        Target("owner/repo", num, store=store), marker, "run-1", f"{marker}\nrun-1\n\nNew state"
    )

    note, state = store.comments_on(num)
    assert (
        posted,
        note.body,
        state.body,
        state.updated_at is not None and state.updated_at > state.created_at,
        store.writes[-1],
    ) == (True, "A note of a person.", f"{marker}\nrun-1\n\nNew state", True, "edit_comment")


def test_with_body_plain_object() -> None:
    """_with_body supports objects with body attribute but without model_copy."""
    from devops_cli.roadmap.steps.comment import _with_body

    obj = _SimpleComment("initial")
    updated = _with_body(obj, "new")
    assert updated.body == "new"
