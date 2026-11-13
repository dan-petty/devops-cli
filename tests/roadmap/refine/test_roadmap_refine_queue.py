"""The queue of the refine row: the items that the selection orders, before the rules of each item
and the limit, counted from the listings that the selection reads (#5470)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.refine.refine import plan_refine
from tests.support.roadmap_refine import REPO, MockLLMClient, seed_new_items

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_the_plan_counts_every_item_that_the_selection_orders(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """Three New items and a limit of 1: the round refines one item, and its queue is 3."""
    seed_new_items(store)

    plan = plan_refine(store, repo=REPO, source=git_repo, model=MockLLMClient(), limit=1)

    assert (len(plan.refined_items), plan.queue) == (1, 3)


def test_a_plan_with_no_item_to_take_has_an_empty_queue(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A roadmap with no New item gives a queue of 0, which ends a backlog."""
    plan = plan_refine(store, repo=REPO, source=git_repo, model=MockLLMClient())

    assert (plan.refined_items, plan.queue) == ([], 0)
