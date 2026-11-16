"""Refine leaves out an item that is a tracker: it has sub-issues or the epic label (#3703)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.lang.en.messages import MESSAGES
from devops_cli.roadmap.refine.refine import (
    NextStep,
    apply_refine,
    plan_refine,
    refine_left_out,
)
from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    PLACED,
    READY,
    REPO,
    comment_bodies,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_round_leaves_out_an_item_with_sub_issues_and_an_item_with_the_epic_label(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
) -> None:
    store.seed_visibility(is_private=True)
    tracker_sub = store.seed_issue(
        "Tracker with sub-issues",
        body="Initial body",
        sub_issues=2,
        fields=PLACED,
    )
    store.set_field(require_item(store, tracker_sub), ItemField.STATUS, "New")
    store.set_field(require_item(store, tracker_sub), ItemField.PRIORITY, "P1-High")

    tracker_epic = seed_item(
        store,
        "New",
        "P1-High",
        labels=(CONST_ROADMAP_EPIC_LABEL,),
        body="Epic body",
    )

    plain = seed_item(store, "New", "P2-Medium", body="Plain body")

    record_sub_before = dict(require_item(store, tracker_sub).job_record)
    record_epic_before = dict(require_item(store, tracker_epic).job_record)

    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert model_fake.call_count == 1
    assert [json.loads(c.prompt)["number"] for c in model_fake.calls] == [plain]

    waiting_map = {w.item.number: (w.step, w.details) for w in plan.waiting_items}
    expected_msg = MESSAGES.roadmap.refine_left_tracker
    assert waiting_map[tracker_sub] == (NextStep.NONE, (expected_msg,))
    assert waiting_map[tracker_epic] == (NextStep.NONE, (expected_msg,))

    assert comment_bodies(store, tracker_sub) == []
    assert comment_bodies(store, tracker_epic) == []
    assert require_item(store, tracker_sub).body == "Initial body"
    assert require_item(store, tracker_epic).body == "Epic body"
    assert require_item(store, tracker_sub).job_record == record_sub_before
    assert require_item(store, tracker_epic).job_record == record_epic_before

    assert require_item(store, plain).status == CONST_ROADMAP_STATUS_READY
    assert len(comment_bodies(store, plain)) == 1


def test_a_named_tracker_is_left_out(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
) -> None:
    store.seed_visibility(is_private=True)
    tracker = store.seed_issue(
        "Named tracker",
        body="Named body",
        sub_issues=1,
        fields=PLACED,
    )
    store.set_field(require_item(store, tracker), ItemField.STATUS, "New")
    store.set_field(require_item(store, tracker), ItemField.PRIORITY, "P1-High")

    record_before = dict(require_item(store, tracker).job_record)

    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=tracker)
    apply_refine(store, plan)

    assert model_fake.call_count == 0
    assert plan.refined_items == []
    assert [(w.item.number, w.step, w.details) for w in plan.waiting_items] == [
        (tracker, NextStep.NONE, (MESSAGES.roadmap.refine_left_tracker,))
    ]
    assert comment_bodies(store, tracker) == []
    assert require_item(store, tracker).body == "Named body"
    assert require_item(store, tracker).job_record == record_before


def test_a_tracker_of_an_untrusted_author_gets_no_notice_comment(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
) -> None:
    store.seed_visibility(is_private=True)
    untrusted_tracker = store.seed_issue(
        "Untrusted tracker",
        body="Untrusted body",
        sub_issues=2,
        fields=PLACED,
        author_association="NONE",
    )
    store.set_field(require_item(store, untrusted_tracker), ItemField.STATUS, "New")
    store.set_field(require_item(store, untrusted_tracker), ItemField.PRIORITY, "P1-High")

    record_before = dict(require_item(store, untrusted_tracker).job_record)

    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert model_fake.call_count == 0
    assert comment_bodies(store, untrusted_tracker) == []
    assert require_item(store, untrusted_tracker).job_record == record_before


def test_refine_left_out_gives_the_tracker_text(
    store: InMemoryRoadmapStore,
) -> None:
    sub_num = store.seed_issue(
        "Sub tracker",
        sub_issues=2,
        fields=PLACED,
    )
    store.set_field(require_item(store, sub_num), ItemField.STATUS, "New")
    store.set_field(require_item(store, sub_num), ItemField.PRIORITY, "P1-High")

    epic_num = seed_item(
        store,
        "New",
        "P1-High",
        labels=(CONST_ROADMAP_EPIC_LABEL,),
    )

    plain_num = seed_item(store, "New", "P2-Medium")

    expected = MESSAGES.roadmap.refine_left_tracker
    assert refine_left_out(store, require_item(store, sub_num)) == expected
    assert refine_left_out(store, require_item(store, epic_num)) == expected
    assert refine_left_out(store, require_item(store, plain_num)) is None


def test_a_plain_item_is_still_refined(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
) -> None:
    store.seed_visibility(is_private=True)
    plain = seed_item(store, "New", "P2-Medium", body="Plain item body")

    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert model_fake.call_count == 1
    assert [refined.item.number for refined in plan.refined_items] == [plain]
    assert require_item(store, plain).status == CONST_ROADMAP_STATUS_READY
    assert len(comment_bodies(store, plain)) == 1
