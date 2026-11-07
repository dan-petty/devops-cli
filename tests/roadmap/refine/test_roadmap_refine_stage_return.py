"""An item that the stage job returned to refine: what the model reads, and what a second return
does (#1335).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config import constants
from devops_cli.roadmap.refine.refine import (
    RefinePlan,
    plan_refine,
)
from devops_cli.roadmap.stage.stage_rejected import comment_text
from devops_cli.roadmap.stores.store import (
    IssueComment,
    ItemField,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    REPO,
    STAGE_EVIDENCE,
    STAGE_MARKER,
    refine_round,
    require_item,
    seed_item,
    stage_returns,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def _stage_returned_item(store: InMemoryRoadmapStore, model_fake: ModelFake, git_repo: Path) -> int:
    """A New item that refine set Ready and the stage job returned to New."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    refine_round(store, git_repo)
    stage_returns(store, number)
    return number


def _waits(plan: RefinePlan) -> list[tuple[int, str, tuple[str, ...]]]:
    return [(w.item.number, w.step.value, w.details) for w in plan.waiting_items]


def test_an_item_the_stage_job_returned_is_refined_again_in_the_next_round(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A stage return is the act of a job, not of a person: the next round refines the item
    again, with no reply and no body edit."""
    number = _stage_returned_item(store, model_fake, git_repo)
    calls = model_fake.call_count

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [r.item.number for r in again.refined_items],
        again.waiting_items,
        model_fake.call_count - calls,
    ) == ([number], [], 1)


def test_the_model_reads_the_evidence_of_the_stage_return_and_the_comment_has_no_marker(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    _stage_returned_item(store, model_fake, git_repo)

    plan_refine(store, repo=REPO, source=git_repo)

    request = json.loads(model_fake.calls[-1].prompt)
    assert (
        STAGE_EVIDENCE in request["stage_return"],
        STAGE_MARKER in request["stage_return"],
    ) == (
        True,
        False,
    )
    assert request["replies"] == []


def test_the_model_reads_the_reason_of_a_rejected_plan_as_the_stage_return_with_no_marker(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The stage job copies the reason of a rejected plan in a comment of its own (#3503): refine
    reads it as `stage_return` and gives the item one new look, with no reply."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    refine_round(store, git_repo)
    reason = IssueComment(
        body="The plan cannot hold: the runner has no sandbox.",
        created_at=datetime.now(UTC),
        author_login="alice",
    )
    store.comment(number, comment_text(7, reason))
    store.set_field(require_item(store, number), ItemField.STATUS, "New")
    calls = model_fake.call_count

    again = plan_refine(store, repo=REPO, source=git_repo)

    request = json.loads(model_fake.calls[-1].prompt)
    assert model_fake.call_count - calls == 1
    assert [r.item.number for r in again.refined_items] == [number]
    assert "The plan cannot hold: the runner has no sandbox." in request["stage_return"]
    assert "#7" in request["stage_return"]
    assert STAGE_MARKER not in request["stage_return"]
    assert constants.CONST_ROADMAP_STAGE_REJECTED_MARKER not in request["stage_return"]
    assert request["replies"] == []


def test_an_item_with_no_stage_return_has_no_stage_evidence_in_the_request(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    seed_item(store, "New", "P1-High")
    model_fake.answer(READY)

    plan_refine(store, repo=REPO, source=git_repo)

    assert json.loads(model_fake.calls[-1].prompt)["stage_return"] is None


def test_a_second_stage_return_on_the_same_body_waits_on_a_person_with_the_reason(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The first return gives one new look. A second return on the same body gives none: the
    item waits on a person, and says why."""
    number = _stage_returned_item(store, model_fake, git_repo)
    refine_round(store, git_repo)
    stage_returns(store, number)
    calls = model_fake.call_count

    waiting = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        _waits(waiting),
        waiting.refined_items,
        model_fake.call_count - calls,
    ) == (
        [
            (
                number,
                "person",
                (
                    "The stage job returned the item to New twice on the same body. A reply or a "
                    "body edit makes refine look at it again.",
                ),
            )
        ],
        [],
        0,
    )


def test_a_body_edit_after_a_stage_return_gives_a_new_look_and_resets_the_second_return(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    number = _stage_returned_item(store, model_fake, git_repo)
    refine_round(store, git_repo)
    recorded = require_item(store, number).job_record
    assert recorded[RefineRecordKey.RETURNED_BODY_HASH] == recorded[RefineRecordKey.BODY_HASH]
    stage_returns(store, number)
    store.as_actor("alice").edit_body_by_hand(number, "A new body.")

    refine_round(store, git_repo)

    assert RefineRecordKey.RETURNED_BODY_HASH not in require_item(store, number).job_record or (
        require_item(store, number).job_record[RefineRecordKey.RETURNED_BODY_HASH] is None
    )


def test_an_item_a_person_sets_back_after_a_stage_return_that_refine_answered_waits_for_a_reason(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The stage return is older than refine's last comment, so it is no cause of the wait: the
    item that a person set back waits for the reason of that person."""
    number = _stage_returned_item(store, model_fake, git_repo)
    refine_round(store, git_repo)
    person = store.as_actor("alice")
    person.set_field(require_item(person, number), ItemField.STATUS, "New")
    calls = model_fake.call_count

    waiting = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        _waits(waiting),
        model_fake.call_count - calls,
    ) == (
        [
            (
                number,
                "person",
                (
                    "A person set the item back to New after refine set it to Ready. A reply "
                    "that tells why makes refine look at it again.",
                ),
            )
        ],
        0,
    )
