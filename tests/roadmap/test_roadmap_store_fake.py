"""The read faults and the read record of the in-memory roadmap (#3746)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore


def test_a_failed_visibility_read_raises_the_error_until_it_is_cleared() -> None:
    """`fail_read` makes each read of the visibility raise, whatever the error, and
    `None` makes the roadmap answer again."""
    roadmap = InMemoryRoadmapStore(is_private=True)
    roadmap.fail_read("repository_is_private", GitHubRateLimitError("GraphQL budget exhausted"))
    with pytest.raises(GitHubRateLimitError, match="budget exhausted"):
        roadmap.repository_is_private()

    roadmap.fail_read("repository_is_private", GitHubOperationError("transient", operation="read"))
    with pytest.raises(GitHubOperationError, match="transient"):
        roadmap.repository_is_private()

    roadmap.fail_read("repository_is_private", None)
    assert roadmap.repository_is_private() is True


def test_a_failed_read_of_the_changes_raises_the_error() -> None:
    roadmap = InMemoryRoadmapStore()
    roadmap.fail_read("changes_since", RuntimeError("the events read timed out"))

    with pytest.raises(RuntimeError, match="events read timed out"):
        roadmap.changes_since(datetime(2026, 11, 1, tzinfo=UTC))


def test_a_read_the_fake_cannot_fail_is_refused() -> None:
    with pytest.raises(ValueError, match="no read that the fake can fail"):
        InMemoryRoadmapStore().fail_read("items", RuntimeError("x"))


def test_the_roadmap_names_each_read_of_an_item_and_of_a_path() -> None:
    """`reads` keeps the Item reads and the path reads in the order a caller made them."""
    roadmap = InMemoryRoadmapStore()
    roadmap.seed_commit("src/app.py", at=datetime(2026, 11, 1, tzinfo=UTC))

    roadmap.item(1)
    roadmap.path_changed_at("src/app.py")
    roadmap.item(2)

    assert roadmap.reads == ["item", "path_changed_at", "item"]
