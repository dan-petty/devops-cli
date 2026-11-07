"""An item that waits on the issue that blocks it: refine sets no Ready until the last blocker
closes (#1335).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.roadmap.refine.refine import (
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    REPO,
    blocked_by_issue,
    refine_round,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_closing_the_item_that_blocks_an_item_makes_it_eligible_again(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A blocked item waits while its blocker is open, and the round after the blocker closes
    refines it again with no reply and no body edit (#1758)."""
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    blocked = seed_item(store, "New", "P1-High")
    model_fake.answer(blocked_by_issue(blocker))
    refine_round(store, git_repo)

    waiting = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").close_by_hand(blocker, CloseReason.COMPLETED)
    after_close = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step) for w in waiting.waiting_items],
        [r.item.number for r in after_close.refined_items],
    ) == ([(blocked, "blocked")], [blocked])


# ── An open dependency that the proposal names blocks the item (#3500) ────────────────────


@pytest.mark.parametrize("status", ["New", CONST_ROADMAP_STATUS_READY], ids=["new", "ready"])
def test_a_complete_proposal_with_an_open_dependency_blocks_its_item_and_sets_no_ready(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, status: str
) -> None:
    """A proposal with no open question, no split and no suspected block, and one open
    dependency, gives the next step `blocked` with that number. The item stays New, or goes back
    to New from Ready, and its record holds the blocker (#3500)."""
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    number = seed_item(store, status, "P1-High")
    model_fake.answer(blocked_by_issue(blocker))

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=number)
    apply_refine(store, plan)

    item = require_item(store, number)
    assert (
        [(r.is_ready, r.next_step, r.step_details, r.blocked_by) for r in plan.refined_items],
        item.status,
        item.job_record.get(RefineRecordKey.NEXT_STEP),
        item.job_record.get(RefineRecordKey.BLOCKED_BY),
    ) == ([(False, "blocked", (f"#{blocker}",), (blocker,))], "New", "blocked", str(blocker))


def test_a_complete_proposal_whose_dependency_is_closed_reaches_ready(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The same proposal with a closed dependency gives the next step `ready` and no blocker: a
    closed issue holds nothing back (#3500)."""
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    store.as_actor("alice").close_by_hand(blocker, CloseReason.COMPLETED)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(blocked_by_issue(blocker))

    plan = refine_round(store, git_repo)

    item = require_item(store, number)
    assert (
        [(r.is_ready, r.next_step, r.blocked_by) for r in plan.refined_items],
        item.status,
        item.job_record.get(RefineRecordKey.BLOCKED_BY),
    ) == ([(True, "ready", ())], CONST_ROADMAP_STATUS_READY, None)


def test_a_blocked_item_reaches_ready_in_the_round_after_its_last_blocker_closes(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An item with two open dependencies waits on both. When the first closes, it waits on the
    second with no model call. The round after the second closes refines it again, and it reaches
    Ready (#3500)."""
    store.seed_visibility(is_private=True)
    first = seed_item(store, "In Progress", "P1-High")
    second = seed_item(store, "In Progress", "P1-High")
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY.model_copy(update={"dependencies": [first, second]}))
    refine_round(store, git_repo)
    blocked = require_item(store, number)
    calls = model_fake.call_count

    store.as_actor("alice").close_by_hand(first, CloseReason.COMPLETED)
    waiting = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").close_by_hand(second, CloseReason.COMPLETED)
    after = refine_round(store, git_repo)

    assert (
        (blocked.status, blocked.job_record.get(RefineRecordKey.BLOCKED_BY)),
        [(w.item.number, w.step, w.details) for w in waiting.waiting_items],
        model_fake.call_count - calls,
        [(r.item.number, r.next_step) for r in after.refined_items],
        require_item(store, number).status,
    ) == (
        ("New", f"{first},{second}"),
        [(number, "blocked", (f"#{second}",))],
        1,
        [(number, "ready")],
        CONST_ROADMAP_STATUS_READY,
    )
