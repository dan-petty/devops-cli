"""What ends the wait of an item that refine left New: a reply of a person, a set-back to New and a
split to hand on (#1335).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.refine.refine import (
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    QUESTION,
    READY,
    REPO,
    SPLIT,
    comment_bodies,
    refine_round,
    replies_sent,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_persons_reply_makes_an_item_that_waits_on_them_eligible_and_reaches_the_model(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A comment after refine's own makes the item eligible again, though its body is unchanged,
    and the model reads the reply; the first round, with no comment, sent none (#1758)."""
    store.seed_visibility(is_private=True)
    asked = seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION, READY)
    refine_round(store, git_repo)
    first_replies = replies_sent(model_fake)

    store.as_actor("alice").comment(asked, "The job record holds it.")
    again = refine_round(store, git_repo)

    assert (
        first_replies,
        [r.item.number for r in again.refined_items],
        replies_sent(model_fake),
        require_item(store, asked).status,
    ) == ([], [asked], ["The job record holds it."], CONST_ROADMAP_STATUS_READY)


def test_the_alternatives_jobs_block_and_comment_do_not_end_a_wait_of_refine(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The alternatives check (#2650) writes a block to the body and posts a comment. Neither is
    a person's edit or reply, so an item that waits on a person still waits and the model is not
    called again; the person's own reply after them still ends the wait."""
    store.seed_visibility(is_private=True)
    asked = seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION)
    refine_round(store, git_repo)
    calls = model_fake.call_count

    block = (
        f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nVerdict: none.\n"
        f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
    )
    store.write_issue_body(asked, f"{store.read_issue_body(asked)}\n\n{block}")
    store.comment(asked, f"{CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER}\nVerdict: none.")
    after_job = plan_refine(store, repo=REPO, source=git_repo)
    job_calls = model_fake.call_count - calls
    store.as_actor("alice").comment(asked, "The job record holds it.")
    after_reply = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step) for w in after_job.waiting_items],
        after_job.refined_items,
        job_calls,
        [r.item.number for r in after_reply.refined_items],
    ) == ([(asked, "person")], [], 0, [asked])


def test_an_unchanged_item_whose_record_needs_a_split_but_holds_no_step_gets_its_split_handed_on(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An unchanged item whose record holds `refine.needs_split` and no next step is refined
    again, not skipped, and its split goes to a person in a comment (#1758)."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    section = "## Proposed design\nNeeds splitting into 2 items."
    start, end = CONST_ROADMAP_REFINE_START_MARKER, CONST_ROADMAP_REFINE_END_MARKER
    store.write_issue_body(number, f"Body P1-High\n\n{start}\n{section}\n{end}")
    store.set_marks(
        require_item(store, number),
        {
            RefineRecordKey.BODY_HASH: hash_text("Body P1-High"),
            RefineRecordKey.SECTION_HASH: hash_text(section),
            RefineRecordKey.NEEDS_SPLIT: "true",
        },
    )
    model_fake.answer(SPLIT)

    plan = refine_round(store, git_repo)

    assert (
        [(r.item.number, r.next_step) for r in plan.refined_items],
        [comment.splitlines()[-2:] for comment in comment_bodies(store, number)],
    ) == ([(number, "split")], [["1. The first change.", "2. The second change."]])


def test_an_item_a_person_sets_back_to_new_waits_for_their_reason_and_is_refined_after_it(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An item refine set Ready and a person set back to New waits on that person; their
    comment, as `devops roadmap return` posts, makes refine look again with it (#1758)."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY, QUESTION)
    refine_round(store, git_repo)
    person = store.as_actor("alice")

    person.set_field(require_item(person, number), ItemField.STATUS, "New")
    waiting = plan_refine(store, repo=REPO, source=git_repo)
    person.comment(number, "It needs a new store.")
    returned = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step, w.details) for w in waiting.waiting_items],
        [r.item.number for r in returned.refined_items],
        replies_sent(model_fake),
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
        [number],
        ["It needs a new store."],
    )
