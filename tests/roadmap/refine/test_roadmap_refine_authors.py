"""The author of an item: refine leaves an item from an outside account for a person and takes the
items of the owner, a member or a collaborator (#1335).
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
    select_candidates,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import READY, REPO, require_item

pytestmark = pytest.mark.usefixtures("keyring_store")


# ── Text from an account without write access (#2478) ─────────────────────────────


def _seed_authored(store: InMemoryRoadmapStore, association: str | None, priority: str) -> int:
    """A New backlog item with `priority`, whose author GitHub gives as `association`."""
    return store.seed_issue(
        f"{association} {priority}",
        body=f"Body {priority}",
        fields={ItemField.PRIORITY: priority, ItemField.STATUS: "New"},
        author_association=association,
    )


def _outside_author(association: str, number: int) -> str:
    """The detail line of an item that an account that the jobs do not trust opened."""
    return (
        f"The author is unknown, and its association with the repository is {association}. A "
        "refine round refines only the items that these accounts opened: the owner, a member, "
        "a collaborator, the Service App's bot and github-actions[bot]. A person refines this "
        f"item with --item {number}."
    )


@pytest.mark.parametrize(
    ("association", "shown"),
    [
        ("NONE", "NONE"),
        ("CONTRIBUTOR", "CONTRIBUTOR"),
        ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR"),
        (None, "unknown"),
    ],
)
def test_a_round_leaves_an_item_from_an_outside_account_waiting_on_a_person_and_item_refines_it(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    association: str | None,
    shown: str,
) -> None:
    """A round refines no item that an account without write access opened, since its text
    could steer the work that agents take: the item waits on a person, takes no place under
    `--limit`, and the round calls no model for it. `--item` refines it, since a person asked
    for it (#2478)."""
    store.seed_visibility(is_private=True)
    outside = _seed_authored(store, association, "P2-Medium")
    owners = _seed_authored(store, "OWNER", "P3-Low")
    model_fake.answer(READY)

    round_plan = plan_refine(store, repo=REPO, source=git_repo, limit=1)
    calls_in_round = model_fake.call_count
    asked = plan_refine(store, repo=REPO, source=git_repo, item_number=outside)
    apply_refine(store, asked)

    assert (
        [r.item.number for r in round_plan.refined_items],
        [(w.item.number, w.step, w.details) for w in round_plan.waiting_items],
        calls_in_round,
        [r.item.number for r in asked.refined_items],
        require_item(store, outside).status,
    ) == (
        [owners],
        [(outside, "person", (_outside_author(shown, outside),))],
        1,
        [outside],
        CONST_ROADMAP_STATUS_READY,
    )


@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_a_round_takes_an_item_that_the_owner_a_member_or_a_collaborator_opened(
    store: InMemoryRoadmapStore, association: str
) -> None:
    """An account with write access opened the item, so a round takes it (#2478)."""
    number = _seed_authored(store, association, "P2-Medium")

    selected, waiting = select_candidates(store)

    assert ([item.number for item in selected], waiting) == ([number], [])
