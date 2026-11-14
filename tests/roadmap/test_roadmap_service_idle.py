"""The Service's idle repository (#3672): no open issue and no open pull request."""

from __future__ import annotations

from devops_cli.roadmap.run import repository_is_idle
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import seed_item

pytestmark = []


def test_a_repository_with_no_open_work_is_idle(store: InMemoryRoadmapStore) -> None:
    assert repository_is_idle(store) is True


def test_a_repository_with_an_open_item_is_busy(store: InMemoryRoadmapStore) -> None:
    seed_item(store, "New", "P1-High")

    assert repository_is_idle(store) is False
