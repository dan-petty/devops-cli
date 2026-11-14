"""The owner question that refine asks (#3077).

A refine step that needs an owner decision posts one owner-question frame: the first open question
once, two options with their results, a recommendation, the evidence and the hidden block with the
question hash. The other open questions wait for a later round, so one run asks one question. When
an older open item already holds the frame of the same question, the item gets a link comment to it
instead of a second frame, and both records hold the same hash.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config import constants
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.owner_question import frame_hash
from devops_cli.roadmap.refine.refine import QuestionAnswer
from devops_cli.roadmap.stores.store import OwnerQuestionRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    comment_bodies,
    refine_round,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


FIRST_QUESTION = "Which store holds the record?"
SECOND_QUESTION = "Should the job keep the old name?"
FIRST_OPEN = f"{FIRST_QUESTION} (a person decides)"
MARKER = constants.CONST_ROADMAP_REFINE_COMMENT_MARKER


def _two_questions() -> object:
    """A proposal that leaves two questions to a person: the first is the one that a round asks."""
    return READY.model_copy(
        update={
            "key_questions": [
                QuestionAnswer(question=FIRST_QUESTION, answer="A person picks it.", kind="person"),
                QuestionAnswer(
                    question=SECOND_QUESTION, answer="A person picks it.", kind="person"
                ),
            ]
        }
    )


def _open_item(store: InMemoryRoadmapStore) -> int:
    """A New backlog P1 on a private repository."""
    store.seed_visibility(is_private=True)
    return seed_item(store, "New", "P1-High")


def test_a_refine_step_posts_one_frame_for_the_first_question_of_the_run(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The comment of a wait on a person is one owner-question frame: the first open question once,
    the two options with their results, the recommendation, the evidence link and the hidden block
    with the hash that the record keeps. The second question waits for a later round."""
    number = _open_item(store)
    model_fake.answer(_two_questions())

    refine_round(store, git_repo)

    (comment,) = comment_bodies(store, number)
    record = require_item(store, number).job_record
    options = MESSAGES.roadmap.refine_owner_question_options
    assert (
        comment.startswith(MARKER),
        comment.count(FIRST_QUESTION),
        SECOND_QUESTION in comment,
        len(options),
        [text in comment and result in comment for text, result in options.items()],
        MESSAGES.roadmap.refine_owner_question_recommendation in comment,
        require_item(store, number).url in comment,
        frame_hash(comment),
        record.get(OwnerQuestionRecordKey.HASH),
        record.get(OwnerQuestionRecordKey.TEXT),
        record.get(OwnerQuestionRecordKey.ANSWER),
    ) == (
        True,
        1,
        False,
        2,
        [True, True],
        True,
        True,
        record.get(OwnerQuestionRecordKey.HASH),
        frame_hash(comment),
        FIRST_OPEN,
        None,
    )


def test_a_second_item_that_asks_the_same_question_links_the_frame_of_the_older_item(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Two items that ask one question post one frame: the older item holds it, the second item
    gets a link to it, and both records hold its hash."""
    store.seed_visibility(is_private=True)
    older = seed_item(store, "New", "P1-High")
    newer = seed_item(store, "New", "P1-High")
    model_fake.answer(_two_questions())

    refine_round(store, git_repo, limit=2)

    (frame,) = comment_bodies(store, older)
    (link,) = comment_bodies(store, newer)
    question_hash = require_item(store, older).job_record.get(OwnerQuestionRecordKey.HASH)
    assert (
        frame_hash(frame),
        frame_hash(link),
        question_hash,
        require_item(store, newer).job_record.get(OwnerQuestionRecordKey.HASH),
        link.startswith(MARKER),
        f"on #{older}:" in link,
        require_item(store, older).url in link,
    ) == (question_hash, None, question_hash, question_hash, True, True, True)
