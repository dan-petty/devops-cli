"""Refine gates Ready on the alternatives check's verdict (#2951): an item whose proposal is ready
but whose check recorded no verdict stays New and waits for the row. A repository that the check
is off for, and a Ready label that a person set, are exempt.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine.refine import (
    NextStep,
    plan_refine,
    render_refine_plan,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    REPO,
    comment_bodies,
    record_alternatives_check,
    refine_round,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


_WAIT = "Waiting for the alternatives check to run."


def _record_check(store: InMemoryRoadmapStore, number: int, verdict: str) -> None:
    """Record the check of item `number`, with a tool for the covering verdicts."""
    tool = "https://github.com/example/scanner" if verdict in {"covers", "partly"} else None
    record_alternatives_check(store, number, verdict, tool=tool)


def test_an_item_with_no_verdict_stays_new_and_waits_for_the_check(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A ready proposal with no alternatives verdict leaves the item New, with the wait comment
    and the `alternatives` next step. The next round calls no model until the check writes a
    verdict (#2951)."""
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)

    plan = refine_round(store, git_repo)
    calls = model_fake.call_count
    again = plan_refine(store, repo=REPO, source=git_repo)
    item = require_item(store, number)

    assert (
        item.status,
        plan.refined_items[0].is_ready,
        plan.refined_items[0].next_step,
        _WAIT in " ".join(comment_bodies(store, number)),
    ) == ("New", False, NextStep.ALTERNATIVES, True)
    assert (
        [(w.item.number, w.step) for w in again.waiting_items],
        again.refined_items,
        model_fake.call_count - calls,
    ) == ([(number, NextStep.ALTERNATIVES)], [], 0)
    assert "## Waiting for the alternatives check" in render_refine_plan(again)


def test_each_step_map_holds_the_alternatives_key() -> None:
    """The comment, the left line and the report heading of the wait have the key of the step
    (#2951)."""
    texts = MESSAGES.roadmap

    assert (
        "alternatives" in texts.refine_step_comments,
        "alternatives" in texts.refine_left_waits,
        "alternatives" in texts.refine_step_headings,
    ) == (True, True, True)


@pytest.mark.parametrize(
    "verdict",
    ["none", "not-applicable", "rejected", "in-use"],
    ids=["none", "not-applicable", "rejected", "in-use"],
)
def test_an_item_with_a_recorded_verdict_becomes_ready(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, verdict: str
) -> None:
    """A recorded verdict that asks no person lets a ready proposal set the item Ready (#2951)."""
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, verdict)
    model_fake.answer(READY)

    refine_round(store, git_repo)

    assert (
        require_item(store, number).status,
        require_item(store, number).job_record.get(RefineRecordKey.NEXT_STEP),
    ) == ("Ready", NextStep.READY.value)


def test_a_covering_verdict_still_asks_a_person(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A `covers` verdict is a recorded verdict, and its question stays open until a person
    answers it (#2951, #2652)."""
    number = seed_item(store, "New", "P1-High")
    _record_check(store, number, "covers")
    model_fake.answer(READY)

    plan = refine_round(store, git_repo)

    assert (
        require_item(store, number).status,
        plan.refined_items[0].next_step,
        _WAIT in " ".join(comment_bodies(store, number)),
    ) == ("New", NextStep.PERSON, False)


def test_a_repository_with_the_check_off_becomes_ready_with_no_verdict(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The gate is off for a repository that the alternatives row is off for, such as a private
    one, so a ready proposal sets the item Ready with no check (#2951)."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)

    refine_round(store, git_repo)

    assert require_item(store, number).status == "Ready"


def test_a_person_set_ready_is_not_reverted(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A Ready label that a person set stays when refine runs on an item with no verdict, and
    refine records no Status of its own (#2951, ADR 0016)."""
    number = seed_item(store, "New", "P1-High")
    person = store.as_actor("alice")
    person.set_field(require_item(store, number), ItemField.STATUS, "Ready")
    model_fake.answer(READY)

    refine_round(store, git_repo)
    item = require_item(store, number)
    comments = " ".join(comment_bodies(store, number))

    assert (item.status, item.job_record.get(ItemField.STATUS), "back to New" in comments) == (
        "Ready",
        "New",
        False,
    )
