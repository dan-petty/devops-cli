"""Tests for reading blocker state from the open listing (#6553).

A refine round, stage, and implement must decide whether recorded blockers or dependencies
are open from the open listing without calling `store.item` for each blocker.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.dependencies import open_issue_dependencies
from devops_cli.roadmap.refine.refine import (
    plan_refine,
    refine_left_out,
)
from devops_cli.roadmap.stores.store import (
    GitHubState,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    REPO,
    blocked_by_issue,
    refine_round,
    seed_item,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_refine_round_makes_no_item_reads_for_recorded_blockers(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A refine round over blocked items whose `refine.blocked_by` records blocker numbers
    decides from the open listing and makes no `store.item` read for a blocker number."""
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    blocked = seed_item(store, "New", "P1-High")
    model_fake.answer(blocked_by_issue(blocker))
    refine_round(store, git_repo)

    store.reads.clear()
    waiting = plan_refine(store, repo=REPO, source=git_repo)

    assert [(w.item.number, w.step) for w in waiting.waiting_items] == [(blocked, "blocked")]
    assert store.reads.count("item") == 0


def test_open_issue_dependencies_takes_open_numbers_and_makes_no_item_reads(
    store: InMemoryRoadmapStore,
) -> None:
    """`open_issue_dependencies` takes the open item numbers of the listing and makes no
    `store.item` read for a dependency number."""
    blocker = seed_item(store, "In Progress", "P1-High")
    item_num = seed_item(store, "New", "P1-High")
    item = store.item(item_num)
    assert item is not None
    open_items = store.open_items()
    open_numbers = {it.number for it in open_items if it.state is GitHubState.OPEN}

    store.reads.clear()
    reason = open_issue_dependencies(item, [blocker], open_numbers, open_items)

    assert reason == MESSAGES.roadmap.stage_left_dependency.format(issues=f"#{blocker}")
    assert store.reads.count("item") == 0


def test_open_issue_with_no_priority_label_is_no_blocker_and_makes_no_item_reads(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A recorded blocker number that the open listing does not hold gives no blocker,
    even when its issue is open, and makes no `store.item` read for it."""
    store.seed_visibility(is_private=True)
    non_item_issue = store.seed_issue("fix(docs): no priority", state=GitHubState.OPEN)
    blocked = seed_item(store, "New", "P1-High")
    item = store.item(blocked)
    assert item is not None
    store.set_marks(
        item,
        {RefineRecordKey.NEXT_STEP: "blocked", RefineRecordKey.BLOCKED_BY: str(non_item_issue)},
    )
    # Refresh item after setting marks
    item = store.item(blocked)
    assert item is not None

    store.reads.clear()
    reason = refine_left_out(store, item)

    assert reason is None or "blocked" not in reason
    assert store.reads.count("item") == 0
