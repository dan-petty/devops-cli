"""Refine does not set Ready an item whose title type `CONST_BRANCH_TYPES` does not list (#4508).

The stage job cannot take such an item, because its branch has no type. A round leaves the item
as it is, with no model call, until `devops roadmap retitle` or a person writes a listed type.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STATUS_NEW, CONST_ROADMAP_STATUS_READY
from devops_cli.roadmap.refine.refine import (
    NextStep,
    apply_refine,
    plan_refine,
    refine_left_out,
    select_candidates,
)
from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import READY, REPO, require_item

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")

SECURITY = "security(ssh): verify node host keys"
NO_CORRECTION = "wip(cli): finish the half-done work"
NOT_READY = (
    "Refine does not set the item Ready while its title has this type (invalid-title-type). The "
    "first round after the title change refines it."
)


def _seed(store: InMemoryRoadmapStore, title: str) -> int:
    """A New P1 backlog item that the owner opened, titled `title`."""
    return store.seed_issue(
        title,
        body="Body.",
        fields={ItemField.PRIORITY: "P1-High", ItemField.STATUS: CONST_ROADMAP_STATUS_NEW},
    )


@pytest.mark.parametrize(
    ("title", "step", "reason"),
    [
        (
            SECURITY,
            NextStep.NONE,
            "The title type `security` is not a type of the project, so the branch has no type. "
            "`devops roadmap retitle` writes `fix(security): verify node host keys`, or names "
            "that title in a comment when a person set the title.",
        ),
        (
            NO_CORRECTION,
            NextStep.PERSON,
            "The title type `wip` is not a type of the project, so the branch has no type. "
            "`devops roadmap retitle` comments on the item, and a person edits the title.",
        ),
    ],
)
def test_a_round_leaves_an_item_with_an_unlisted_title_type_new_with_no_model_call(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    title: str,
    step: NextStep,
    reason: str,
) -> None:
    number = _seed(store, title)
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert (
        plan.refined_items,
        [(w.item.number, w.step, w.details) for w in plan.waiting_items],
        model_fake.call_count,
        require_item(store, number).status,
    ) == ([], [(number, step, (f"{reason} {NOT_READY}",))], 0, CONST_ROADMAP_STATUS_NEW)


def test_the_round_after_the_title_change_refines_the_item_to_ready(
    store: InMemoryRoadmapStore, git_repo: Path, model_fake: ModelFake
) -> None:
    number = _seed(store, SECURITY)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo))
    store.set_title(number, "fix(security): verify node host keys")
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert ([r.item.number for r in plan.refined_items], model_fake.call_count) == ([number], 1)
    assert require_item(store, number).status == CONST_ROADMAP_STATUS_READY


def test_item_option_does_not_refine_an_item_with_a_type_that_has_no_correction(
    store: InMemoryRoadmapStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """A person asked for the item, but the stage job could still not take it."""
    number = _seed(store, NO_CORRECTION)
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=number)
    apply_refine(store, plan)

    assert (plan.refined_items, model_fake.call_count) == ([], 0)
    assert require_item(store, number).status == CONST_ROADMAP_STATUS_NEW


def test_an_unlisted_title_type_takes_no_place_of_the_limit(store: InMemoryRoadmapStore) -> None:
    waiting = _seed(store, NO_CORRECTION)
    taken = _seed(store, "fix(cli): finish the half-done work")

    selected, left = select_candidates(store, limit=1)

    assert ([item.number for item in selected], [w.item.number for w in left]) == (
        [taken],
        [waiting],
    )


def test_explain_gives_the_reason_of_an_unlisted_title_type(store: InMemoryRoadmapStore) -> None:
    number = _seed(store, NO_CORRECTION)

    reason = refine_left_out(store, require_item(store, number))

    assert reason is not None
    assert reason.startswith("The item waits on a person. The title type `wip`")
    assert "(invalid-title-type)" in reason
