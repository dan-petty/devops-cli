"""A stop of the Service after each write of a refine result, and a round that finds the same
next step again, leave no second comment (ADR 0021, #4793).

The roadmap is the in-memory store, the model edge is the fake, and git runs on the git fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.refine.refine import RefinementProposal
from tests.support.roadmap_refine import QUESTION, READY, refine_round, require_item, seed_item
from tests.support.write_stops import stop_after_each_write

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")


def _asks(question: str) -> RefinementProposal:
    """The answer of `QUESTION` with another question for a person."""
    (asked,) = QUESTION.key_questions
    return QUESTION.model_copy(
        update={"key_questions": [asked.model_copy(update={"question": question})]}
    )


@pytest.mark.parametrize("answer", [READY, QUESTION], ids=["ready", "question"])
def test_a_stop_after_each_write_of_a_result_leaves_no_second_comment(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    answer: RefinementProposal,
) -> None:
    """A result writes the issue, then the comment. After a stop of the Service after either
    write, the next round leaves no comment that one whole round does not leave."""
    store.seed_visibility(is_private=True)
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
    round still holds it, so the store refuses the repeat. A new question posts."""
    store.seed_visibility(is_private=True)
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
