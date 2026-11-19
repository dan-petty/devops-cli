"""The next step that refine names for each item it leaves New: the comment, the record and the
report (#1335).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config import constants
from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.owner_question import frame_hash
from devops_cli.roadmap.refine.refine import (
    RefinementProposal,
    plan_refine,
    render_refine_plan,
)
from devops_cli.roadmap.stores.store import (
    OwnerQuestionRecordKey,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    QUESTION,
    READY,
    REPO,
    SPLIT,
    blocked_by_issue,
    comment_bodies,
    refine_round,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


_OPEN_QUESTION = "Which store holds the record? (a person decides)"


def _is_about(number: int, prompt: str) -> bool:
    """Whether a proposal request is about issue `number`."""
    found: object = json.loads(prompt).get("number")
    return found == number


def _answer_each(model_fake: ModelFake, proposals: Mapping[int, RefinementProposal]) -> None:
    """Answer the proposal request about each issue with its proposal."""
    for number, proposal in proposals.items():
        model_fake.route(partial(_is_about, number), proposal)


def _seed_waiting_items(store: InMemoryRoadmapStore, model_fake: ModelFake) -> tuple[int, ...]:
    """On a private repository, an item In Progress, then three New backlog P1s whose proposals
    ask a question, need a split and wait on the first item; returned in that order."""
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    asked, split, blocked = (seed_item(store, "New", "P1-High") for _ in range(3))
    _answer_each(model_fake, {asked: QUESTION, split: SPLIT, blocked: blocked_by_issue(blocker)})
    return blocker, asked, split, blocked


def test_each_item_refine_leaves_new_waits_on_its_next_step_with_no_model_call(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An item refine leaves New gets a next step, not a skip as unchanged: its open question
    goes to a person, its split goes to a person, or the open item it depends on blocks it. The
    next round leaves each one waiting on that step and calls no model (#1758)."""
    blocker, asked, split, blocked = _seed_waiting_items(store, model_fake)

    first = refine_round(store, git_repo)
    calls = model_fake.call_count
    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(r.item.number, r.next_step, r.step_details) for r in first.refined_items],
        [(w.item.number, w.step, w.details) for w in again.waiting_items],
        again.refined_items,
        model_fake.call_count - calls,
    ) == (
        [
            (asked, "person", (_OPEN_QUESTION,)),
            (split, "split", ("The first change.", "The second change.")),
            (blocked, "blocked", (f"#{blocker}",)),
        ],
        [(asked, "person", ()), (split, "split", ()), (blocked, "blocked", (f"#{blocker}",))],
        [],
        0,
    )


def test_an_item_refine_cannot_ready_gets_one_comment_and_a_record_of_its_next_step(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Refine posts one comment that carries its marker and gives the item's next step. The
    comment names the part of refine's section that holds the question, the split or the open
    items, and the section holds them (#6196). The job record keeps the step, the split and the
    blockers (#1758). A wait on a person is one owner question with the hidden block of its hash
    (#3077)."""
    blocker, asked, split, blocked = _seed_waiting_items(store, model_fake)

    refine_round(store, git_repo)

    marker = constants.CONST_ROADMAP_REFINE_COMMENT_MARKER
    record_keys = ("refine.next_step", "refine.needs_split", "refine.blocked_by")
    comments = {number: comment_bodies(store, number) for number in (asked, split, blocked)}
    sections = {
        number: extract_section_and_outside(store.read_issue_body(number))[1] or ""
        for number in (split, blocked)
    }
    (question,) = comments[asked]
    assert (
        {number: comments[number] for number in (split, blocked)},
        ("1. The first change." in sections[split], f"#{blocker}" in sections[blocked]),
        {
            number: tuple(
                require_item(store, number).job_record.get(RefineRecordKey(key))
                for key in record_keys
            )
            for number in (asked, split, blocked)
        },
        (
            question.startswith(marker),
            question.count(_OPEN_QUESTION),
            frame_hash(question),
            require_item(store, asked).job_record.get(OwnerQuestionRecordKey.HASH),
            require_item(store, asked).job_record.get(OwnerQuestionRecordKey.TEXT),
        ),
    ) == (
        {
            split: [
                f"{marker}\nNext step: a person splits the item, or replies in a comment or "
                "edits the body to keep one item. See Fit in the section Proposed design of the "
                "body."
            ],
            blocked: [
                f"{marker}\nNext step: the open items close, or a person replies in a comment or "
                "edits the body. See Dependencies in the section Proposed design of the body."
            ],
        },
        (True, True),
        {
            asked: ("person", "false", None),
            split: ("split", "true", None),
            blocked: ("blocked", "false", str(blocker)),
        },
        (
            True,
            0,
            require_item(store, asked).job_record.get(OwnerQuestionRecordKey.HASH),
            require_item(store, asked).job_record.get(OwnerQuestionRecordKey.HASH),
            _OPEN_QUESTION,
        ),
    )


def test_the_points_of_a_next_step_hold_the_models_text_sanitized_and_one_line_for_each_point(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The model's split reaches the points of the next step, which the report shows: no raw
    HTML, every handle in a code span so no one is pinged, and each point on its own line (#1758).
    The comment holds no point: the section holds the split (#6196)."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    split_offs = ["Ask @owner <b>now</b>\n\n## Then this", "The second change."]
    model_fake.answer(SPLIT.model_copy(update={"split_offs": split_offs}))

    plan = refine_round(store, git_repo)

    assert (
        [r.step_details for r in plan.refined_items],
        ["@owner" in comment for comment in comment_bodies(store, number)],
    ) == ([("Ask `@owner` &lt;b>now&lt;/b> ## Then this", "The second change.")], [False])


def test_a_link_in_a_code_block_of_the_models_point_is_a_code_span_on_the_points_line(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A point goes on one line before it is sanitized: the line has no code block, so the
    link that a code block held goes in a code span and GitHub does not link it (#2525)."""
    store.seed_visibility(is_private=True)
    seed_item(store, "New", "P1-High")
    split_offs = ["Read this:\n\n    www.example.com", "The second change."]
    model_fake.answer(SPLIT.model_copy(update={"split_offs": split_offs}))

    plan = refine_round(store, git_repo)

    assert [r.step_details for r in plan.refined_items] == [
        ("Read this: `www.example.com`", "The second change.")
    ]


def test_the_report_groups_every_item_under_its_next_step(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, snapshot: SnapshotAssertion
) -> None:
    """The report lists each item under its next step, in the order refined to Ready, waiting on
    a person, split proposed and blocked, with its details: the round that refines three of them,
    then the round that refines the fourth and finds the three waiting (#1758)."""
    _seed_waiting_items(store, model_fake)
    seed_item(store, "New", "P1-High")
    model_fake.answer(READY)

    rounds = [refine_round(store, git_repo, limit=3), refine_round(store, git_repo, limit=3)]

    assert [render_refine_plan(plan) for plan in rounds] == snapshot
