"""`devops roadmap refine --item`: it refines the named item though nothing changed since its last
round (#1335).
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
    RefinementProposal,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import QUESTION, READY, REPO, require_item, seed_item

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.parametrize(
    ("answers", "status"),
    [
        ((QUESTION, READY), CONST_ROADMAP_STATUS_READY),
        ((READY, QUESTION), "New"),
    ],
    ids=["waiting-on-a-person", "ready"],
)
def test_an_item_named_with_item_is_refined_though_nothing_changed_since_its_last_round(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    answers: tuple[RefinementProposal, ...],
    status: str,
) -> None:
    """`--item` refines the open New or Ready item it names, since a person asked for it, though
    its body is unchanged and no reply came (#1758)."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(*answers)
    plan1 = plan_refine(store, repo=REPO, source=git_repo, item_number=number)
    apply_refine(store, plan1)

    again = plan_refine(store, repo=REPO, source=git_repo, item_number=number)
    apply_refine(store, again)

    assert (
        [r.item.number for r in again.refined_items],
        model_fake.call_count,
        require_item(store, number).status,
    ) == ([number], 2, status)


@pytest.mark.parametrize("status", ["Planned", "In Progress", "Blocked"])
def test_an_item_named_with_item_that_refine_never_changes_has_nothing_to_do(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, status: str
) -> None:
    """`--item` on an item In Progress or Blocked reports it with nothing to do and why,
    and calls no model (#1758)."""
    number = seed_item(store, status, "P1-High")

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=number)

    assert (
        [(w.item.number, w.step, w.details) for w in plan.waiting_items],
        model_fake.call_count,
    ) == (
        [(number, "none", (f"Status {status}: refine changes only open New and Ready items.",))],
        0,
    )


def test_an_item_named_with_item_that_is_closed_has_nothing_to_do(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """`--item` on a closed issue reports it with nothing to do and calls no model (#1758)."""
    number = seed_item(store, "New", "P1-High")
    store.as_actor("alice").close_by_hand(number, CloseReason.COMPLETED)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=number)

    assert (
        [(w.item.number, w.step, w.details) for w in plan.waiting_items],
        model_fake.call_count,
    ) == ([(number, "none", ("The issue is closed: refine changes only open items.",))], 0)
