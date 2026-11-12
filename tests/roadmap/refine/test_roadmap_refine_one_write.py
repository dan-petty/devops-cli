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
from devops_cli.roadmap.refine.refine import (
    NextStep,
    RefinementProposal,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import RefineRecordKey
from tests.support.roadmap_refine import (
    QUESTION,
    READY,
    REPO,
    refine_round,
    require_item,
    seed_item,
)
from tests.support.service_stop import stop_error
from tests.support.write_stops import stop_after_each_write

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


@pytest.mark.parametrize("answer", [READY, QUESTION], ids=["ready", "question"])
def test_a_stop_after_each_write_of_a_result_leaves_no_second_comment(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    answer: RefinementProposal,
) -> None:
    """A result writes the issue, then the comment. After a stop of the Service after either
    write, the next round leaves no comment that one whole round does not leave (ADR 0021,
    #4793)."""
    _private(store)
    seed_item(store, "New", "P1-High")
    model_fake.answer(answer)

    replay = stop_after_each_write(store, lambda copied: refine_round(copied, git_repo))

    assert (replay.whole[-1], [run.at for run in replay.runs], replay.extra_comments()) == (
        "comment",
        [1, 2],
        [],
    )


def test_a_round_that_asks_the_same_question_again_posts_no_second_comment(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A person edits the body, and the model asks the same question: the comment of the first
    round still holds it, so the store refuses the repeat (#4793). A new question posts."""
    _private(store)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION)
    refine_round(store, git_repo)
    person = store.as_actor("alice")
    person.write_issue_body(number, f"{require_item(store, number).body}\n\nThe store is Valkey.")
    refine_round(store, git_repo)
    once = len(store.comments_on(number))
    model_fake.answer(_asks("Which key holds the record?"))
    person.write_issue_body(number, f"{require_item(store, number).body}\n\nOne key per item.")

    refine_round(store, git_repo)

    assert (model_fake.call_count, once, len(store.comments_on(number))) == (3, 1, 2)


def _asks(question: str) -> RefinementProposal:
    """The answer of `QUESTION` with another question for a person."""
    (asked,) = QUESTION.key_questions
    return QUESTION.model_copy(
        update={"key_questions": [asked.model_copy(update={"question": question})]}
    )
