"""Refine writes the result of one item with one request (#4049).

The body, the marks and the Status of one result go in one `PATCH`. A stop of the Service after
that write leaves the new body, the new marks and the new Status together, so the next round does
not read the new body as a person's edit and does not refine the item again.

The roadmap is the in-memory store, the model edge is the fake, and git runs on the git fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions import RoadmapRunError
from devops_cli.roadmap.refine.refine import NextStep, apply_refine, plan_refine
from devops_cli.roadmap.stores.store import RefineRecordKey
from tests.support.roadmap_refine import (
    QUESTION,
    READY,
    REPO,
    require_item,
    seed_item,
)
from tests.support.service_stop import stop_error

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

_DESIGN = "The item needs a design."
"""The problem statement of `READY`, which the refined section of the body holds."""


def _private(store: InMemoryRoadmapStore) -> None:
    store.seed_visibility(is_private=True)


def test_a_stop_after_first_write_leaves_the_body_the_marks_and_the_status_together(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The only write of the result is one request. A stop right after it leaves the new body,
    the new marks and the new Status together. The next round makes no model call, and the item
    is neither a wait for a body edit nor a return to New (#4049)."""
    _private(store)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    plan = plan_refine(store, repo=REPO, source=git_repo)
    asked = model_fake.call_count
    store.fail_write(at=2, error=stop_error())

    with pytest.raises(RoadmapRunError) as stopped:
        apply_refine(store, plan)
    item = require_item(store, number)
    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        stopped.value.error_code,
        item.status,
        _DESIGN in item.body,
        RefineRecordKey.BODY_HASH in item.job_record,
        item.job_record.get(RefineRecordKey.NEXT_STEP),
        again.refined_items,
        [waiting.step for waiting in again.waiting_items if waiting.step is NextStep.EDIT],
        model_fake.call_count - asked,
    ) == ("SERVICE_STOPPING", "Ready", True, True, NextStep.READY.value, [], [], 0)


def test_the_result_of_a_ready_item_is_one_write_that_holds_the_body_and_the_status(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An item that refine sets Ready costs one write of its issue and one comment. The write
    carries the body, the Status and the marks (#4049)."""
    _private(store)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    plan = plan_refine(store, repo=REPO, source=git_repo)
    before = len(store.writes)

    apply_refine(store, plan)
    item = require_item(store, number)

    assert (store.writes[before:], item.status, _DESIGN in item.body) == (
        ["set_field", "comment"],
        "Ready",
        True,
    )


def test_an_item_with_no_status_change_is_written_with_one_request_that_holds_the_body_and_marks(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An item that keeps its Status New, with a question for a person, costs one write of its
    issue and one comment. The write carries the new body and the marks (#4049)."""
    _private(store)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION)
    plan = plan_refine(store, repo=REPO, source=git_repo)
    before = len(store.writes)

    apply_refine(store, plan)
    item = require_item(store, number)

    assert (
        store.writes[before:],
        item.status,
        _DESIGN in item.body,
        item.job_record.get(RefineRecordKey.NEXT_STEP),
    ) == (["set_marks", "comment"], "New", True, NextStep.PERSON.value)


def test_a_ready_item_that_goes_back_to_new_is_written_with_one_request_for_body_and_status(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A Ready item that refine finds not ready goes back to New with one write of its issue: the
    body, the Status and the marks together (#1515, #4049)."""
    _private(store)
    number = seed_item(store, "Ready", "P1-High")
    model_fake.answer(QUESTION)
    plan = plan_refine(store, repo=REPO, source=git_repo)
    before = len(store.writes)

    apply_refine(store, plan)
    item = require_item(store, number)

    assert (store.writes[before:], item.status, _DESIGN in item.body) == (
        ["set_field", "comment"],
        "New",
        True,
    )
