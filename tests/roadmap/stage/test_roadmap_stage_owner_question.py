"""The owner question that the stage job asks (#3077).

A stage step whose task group is still over the budget after the split needs an owner decision, so
it posts one owner-question frame: the question whether to split the group or raise its budget
once, two options with their results, a recommendation, the evidence and the hidden block with the
question hash. The record of the item holds the hash and the question, so the inbox lists the open
question and a trusted reply resumes the item. The stage step asks one question and ends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_COMMENT_MARKER
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.owner_question import frame_hash
from devops_cli.roadmap.stage.stage import StageApplied, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_change import StageSplit
from devops_cli.roadmap.stores.store import Item, OwnerQuestionRecordKey, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    StageRepo,
    apply_stage,
    heavy_group,
    seed_stageable,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store", "openspec_fake")


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A Ready P1 bug that the default filter names."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


def _stage(store: InMemoryRoadmapStore, repo: StageRepo) -> StageApplied:
    """One round of `devops roadmap stage --confirm` whose only task group stays over the budget
    after the model split it once."""
    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        step_tokens=6000,
    )
    return apply_stage(store, plan, source=repo.clone)


def _comments(store: InMemoryRoadmapStore) -> list[str]:
    return [comment.body for comment in store.comments_on(1)]


def _item(store: InMemoryRoadmapStore) -> Item:
    item = store.item(1)
    assert item is not None
    return item


def test_a_group_still_over_the_budget_posts_the_owner_question_frame(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    """The stop on the budget is one owner-question frame: the question once, the two options with
    their results, the recommendation, the evidence with the item link, and the hidden block whose
    hash the record keeps with the question text."""
    heavy = heavy_group(stage_repo)
    model_fake.answer(make_stage_proposal(groups=[heavy]), StageSplit(groups=[heavy]))

    applied = _stage(store, stage_repo)

    (comment,) = _comments(store)
    item = _item(store)
    record = item.job_record
    question = record.get(OwnerQuestionRecordKey.TEXT) or ""
    options = MESSAGES.roadmap.stage_owner_question_options
    assert applied.stopped == (1,)
    assert comment.startswith(f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n")
    assert frame_hash(comment) is not None
    assert record.get(OwnerQuestionRecordKey.HASH) == frame_hash(comment)
    assert (question in comment, comment.count(question)) == (True, 1)
    assert 2 <= len(options) <= 3
    assert [text in comment and result in comment for text, result in options.items()] == [
        True,
        True,
    ]
    assert MESSAGES.roadmap.stage_owner_question_recommendation in comment
    assert item.url in comment
    assert '"Keep the last comment"' in comment
    assert record.get(OwnerQuestionRecordKey.ANSWER) is None
    assert StageRecordKey.BRANCH not in record
    assert (record[StageRecordKey.NEEDS_SPLIT] or "").startswith("Keep the last comment (")
