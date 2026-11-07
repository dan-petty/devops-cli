"""Which items a refine round takes: by milestone, by priority, by change of body and by the limit
of the round (#1335).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import httpx2
import pytest

from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.roadmap.body_hash import extract_section_and_outside, hash_text
from devops_cli.roadmap.refine.refine import (
    RefinementProposal,
    apply_refine,
    check_person_edits,
    inspect_checkout,
    plan_refine,
    select_candidates,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    CRITERION,
    CRITERION_JSON,
    FIRST,
    NO_OPEN_TOOL,
    PLACED,
    REPO,
    SECOND,
    THIRD,
    BodyReadCountingStore,
    MockLLMClient,
    comment_bodies,
    require_item,
    seed_item,
    seed_new_items,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_selection_second_milestone_backlog_priorities_and_cap(store: InMemoryRoadmapStore) -> None:
    # The second open milestone
    n1 = store.seed_issue("Next critical", milestone=SECOND, fields=PLACED)
    n2 = store.seed_issue("Next low", milestone=SECOND, fields=PLACED)
    store.set_field(require_item(store, n1), ItemField.STATUS, "New")
    store.set_field(require_item(store, n1), ItemField.PRIORITY, CONST_ROADMAP_CRITICAL_PRIORITY)
    store.set_field(require_item(store, n2), ItemField.STATUS, "New")
    store.set_field(require_item(store, n2), ItemField.PRIORITY, "P3-Low")

    # Backlog items
    b1 = store.seed_issue("Backlog critical", fields=PLACED)
    b2 = store.seed_issue("Backlog ready", fields=PLACED)
    b3 = store.seed_issue("Backlog blocked", fields=PLACED)
    store.set_field(require_item(store, b1), ItemField.STATUS, "New")
    store.set_field(require_item(store, b1), ItemField.PRIORITY, CONST_ROADMAP_CRITICAL_PRIORITY)
    store.set_field(require_item(store, b2), ItemField.STATUS, CONST_ROADMAP_STATUS_READY)
    store.set_field(require_item(store, b3), ItemField.STATUS, "Blocked")

    selected, _skipped = select_candidates(store, limit=3)
    sel_nums = [it.number for it in selected]
    assert (
        sel_nums,
        b2 not in sel_nums,
        b3 not in sel_nums,
    ) == ([n1, n2, b1], True, True)


def test_an_unchanged_item_that_waits_on_a_body_edit_is_selected_once_its_body_changes(
    store: InMemoryRoadmapStore,
) -> None:
    """An item refine could not write a design for waits on a body edit alone: selection leaves
    it out, with that next step, until a person edits the body (#1758)."""
    num = store.seed_issue("Item", body="Initial content", fields=PLACED)
    item = require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")
    outside, _ = extract_section_and_outside("Initial content")
    store.set_marks(
        item,
        {
            RefineRecordKey.BODY_HASH: hash_text(outside),
            RefineRecordKey.SECTION_HASH: None,
            RefineRecordKey.NEXT_STEP: "edit",
        },
    )

    selected_unchanged, waiting = select_candidates(store)
    store.as_actor("alice").write_issue_body(num, "Updated content by human")
    selected_changed, _ = select_candidates(store)
    assert (
        selected_unchanged,
        [(w.item.number, w.step, w.details) for w in waiting],
        [it.number for it in selected_changed],
    ) == ([], [(num, "edit", ())], [num])


def test_a_later_milestone_is_refined_once_the_second_one_is_ready(
    store: InMemoryRoadmapStore,
) -> None:
    """With the second open milestone all Ready, refine takes the third one's New items,
    highest priority first, up to its limit (#1515)."""
    store.seed_milestone(THIRD, due_on=date(2026, 11, 12))
    seed_item(store, CONST_ROADMAP_STATUS_READY, "P1-High", milestone=SECOND, refined=True)
    later = [
        seed_item(store, "New", priority, milestone=THIRD)
        for priority in ("P1-High", "P2-Medium", "P1-High", "P1-High")
    ]
    selected, _skipped = select_candidates(store)
    assert [it.number for it in selected] == [later[0], later[2], later[3]]


def test_a_critical_fix_in_the_first_milestone_goes_before_any_later_item(
    store: InMemoryRoadmapStore,
) -> None:
    """A New critical fix in the first open milestone is taken before a later milestone's item,
    even one of the same priority (#1515)."""
    planned = seed_item(store, "New", CONST_ROADMAP_CRITICAL_PRIORITY, milestone=SECOND)
    fix = seed_item(
        store, "New", CONST_ROADMAP_CRITICAL_PRIORITY, milestone=FIRST, labels=("type/bug",)
    )
    selected, _skipped = select_candidates(store)
    assert [it.number for it in selected] == [fix, planned]


def test_ready_items_refine_never_saw_are_taken_in_each_milestone_and_backlog_p0_p1(
    store: InMemoryRoadmapStore,
) -> None:
    """A Ready item refine holds no record of is taken like a New one in each open milestone and
    among the backlog's P0/P1 items; one refine already saw and a lower-priority backlog one are
    not (#1515)."""
    ready = CONST_ROADMAP_STATUS_READY
    first = seed_item(store, ready, CONST_ROADMAP_CRITICAL_PRIORITY, milestone=FIRST)
    seed_item(store, ready, "P1-High", milestone=SECOND, refined=True)
    planned = seed_item(store, ready, "P2-Medium", milestone=SECOND)
    backlog = seed_item(store, ready, "P1-High")
    seed_item(store, ready, "P3-Low")
    selected, _skipped = select_candidates(store, limit=10)
    assert [it.number for it in selected] == [first, planned, backlog]


def test_a_ready_item_refine_finds_not_ready_goes_back_to_new_and_then_waits_on_a_person(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """Refine sets a Ready item it never saw back to New when its proposal is not ready, saying so
    in the one comment that asks a person about the suspected block, and the next round leaves
    it waiting on that person (#1515, #1758)."""
    number = seed_item(store, CONST_ROADMAP_STATUS_READY, "P1-High", milestone=SECOND)
    blocked = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement="Needs the owner's decision.",
        acceptance_criteria=[CRITERION],
        suspected_block="Waiting on the owner",
    )
    llm = MockLLMClient(proposal=blocked)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo, model=llm))
    again = plan_refine(store, repo=REPO, source=git_repo, model=llm)
    sha = inspect_checkout(git_repo, REPO)[:12]
    assert (
        require_item(store, number).status,
        comment_bodies(store, number),
        again.refined_items,
        [(w.item.number, w.step) for w in again.waiting_items],
    ) == (
        "New",
        [
            f"{constants.CONST_ROADMAP_REFINE_COMMENT_MARKER}\nStatus set back to New at {sha}. "
            f"Refine cannot set this item to Ready at {sha} until a person answers the questions "
            "below. Reply in a comment or edit the body, and the next refine round looks at the "
            "item again.\n\n- Waiting on the owner"
        ],
        [],
        [(number, "person")],
    )


def test_an_item_refine_would_skip_for_a_person_edit_takes_no_place(
    store: InMemoryRoadmapStore,
) -> None:
    """A New backlog P1 whose section's hash differs from the record, as an item holding a section
    from before #1470 has once refine adds its own, waits on a body edit at selection, and the
    New item behind it gets the round's one place (#1515, #1758)."""
    stuck = seed_item(store, "New", "P1-High")
    store.write_issue_body(
        stuck,
        f"Body\n\n{CONST_ROADMAP_REFINE_START_MARKER}\n## Proposed design\nOld.\n[end-marker]\n\n"
        f"{CONST_ROADMAP_REFINE_START_MARKER}\n## Proposed design\nNew.\n"
        f"{CONST_ROADMAP_REFINE_END_MARKER}",
    )
    store.set_marks(
        require_item(store, stuck),
        {
            RefineRecordKey.BODY_HASH: "body",
            RefineRecordKey.SECTION_HASH: hash_text("## Proposed design\nNew."),
        },
    )
    fresh = seed_item(store, "New", "P1-High")
    selected, waiting = select_candidates(store, limit=1)
    assert (
        [it.number for it in selected],
        [(w.item.number, w.step, w.details) for w in waiting],
    ) == (
        [fresh],
        [(stuck, "edit", ("the section's hash differs from the one refine last recorded",))],
    )


def test_person_edits_guards(store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Item", body="Body text", fields=PLACED)
    item = require_item(store, num)

    # 1. Section exists but no recorded hash
    body_with_untracked_section = (
        f"Body\n{CONST_ROADMAP_REFINE_START_MARKER}\nSection\n{CONST_ROADMAP_REFINE_END_MARKER}"
    )
    store.write_issue_body(num, body_with_untracked_section)
    err1 = check_person_edits(item, body_with_untracked_section)
    assert err1 == "the body holds a section refine has no record of"

    # 2. Section hash differs from recorded
    store.set_marks(item, {RefineRecordKey.SECTION_HASH: "different-hash"})
    item = require_item(store, num)
    err2 = check_person_edits(item, body_with_untracked_section)
    assert err2 == "the section's hash differs from the one refine last recorded"


def test_an_item_a_person_edited_waits_on_a_body_edit_with_no_model_call(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """`--item` refines an item whose section refine has no record of to the edit step, with an
    empty proposal and no call to the model (#1849 made the proposal's existing-tool answer a
    required key)."""
    body = f"Body\n{CONST_ROADMAP_REFINE_START_MARKER}\nSection\n{CONST_ROADMAP_REFINE_END_MARKER}"
    num = store.seed_issue("Item", body=body, fields=PLACED)
    llm = MockLLMClient()

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=num, model=llm)
    refined = plan.refined_items[0]
    assert (
        refined.next_step.value,
        refined.skip_reason,
        refined.proposal.existing_tool,
        llm.calls,
    ) == ("edit", "the body holds a section refine has no record of", "", [])


# ── The hourly round: no Ready count stops it, and no model call when nothing changed ──

# A proposal refine leaves New: it does not fit one pull request.
_SPLIT_PROPOSAL = json.dumps(
    {
        "existing_tool": NO_OPEN_TOOL,
        "problem_statement": "Two changes in one item.",
        "acceptance_criteria": [CRITERION_JSON],
        "fits_one_pr": False,
        "split_offs": ["The first change.", "The second change."],
    }
)


def test_a_backlog_full_of_ready_items_stops_refine_from_no_new_item_up_to_the_limit(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Twelve Ready items in the backlog do not stop a round. It asks the model about the New
    item of an open milestone first, then about the backlog's New items by priority, and stops
    at `--limit` alone. The board shows the Ready count to the person who plans (#2004)."""
    store.seed_visibility(is_private=True)
    for _ in range(12):
        seed_item(store, CONST_ROADMAP_STATUS_READY, "P2-Medium", refined=True)
    planned = seed_item(store, "New", "P3-Low", milestone=FIRST)
    backlog = [
        seed_item(store, "New", priority)
        for priority in ("P3-Low", "P2-Medium", "P1-High", "P3-Low")
    ]
    model_fake.answer(_SPLIT_PROPOSAL)

    plan_refine(store, repo=REPO, source=git_repo, limit=4)

    assert [json.loads(call.prompt)["number"] for call in model_fake.calls] == [
        planned,
        backlog[2],
        backlog[1],
        backlog[0],
    ]


def test_a_round_after_refine_left_items_new_leaves_them_waiting_reading_no_body_or_model(
    git_repo: Path,
    store: BodyReadCountingStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Items a real round refined and left New with a split proposed still wait on that split in
    the next round, which reads no issue body, selects nothing and sends the gateway no request,
    with a Ready item that has a recorded section among them (#1515, #1539, #1758)."""
    numbers = seed_new_items(store)
    seed_item(store, CONST_ROADMAP_STATUS_READY, "P2-Medium", milestone=SECOND, refined=True)
    sent = scripted_gateway({}, default=_SPLIT_PROPOSAL)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo))
    first_round = len(sent)
    store.body_reads.clear()
    again = plan_refine(store, repo=REPO, source=git_repo)
    assert (
        first_round,
        len(sent),
        store.body_reads,
        again.refined_items,
        [(w.item.number, w.step) for w in again.waiting_items],
        [require_item(store, number).status for number in numbers],
    ) == (3, 3, [], [], [(number, "split") for number in numbers], ["New"] * 3)


def test_editing_one_settled_items_body_selects_only_it_with_one_body_read_and_one_model_call(
    git_repo: Path,
    store: BodyReadCountingStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """A person's edit outside the refine section unsettles that item alone; the planning round
    that follows reads its body once, sends one request, and writes nothing (#1539)."""
    first, second, third = seed_new_items(store)
    sent = scripted_gateway({}, default=_SPLIT_PROPOSAL)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo))
    store.as_actor("alice").write_issue_body(
        second, store.read_issue_body(second) + "\n\nAnd one more requirement."
    )
    store.body_reads.clear()
    writes_before, requests_before = store.job_writes(), len(sent)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [refined.item.number for refined in again.refined_items],
        [(w.item.number, w.step) for w in again.waiting_items],
        store.body_reads,
        len(sent) - requests_before,
        store.job_writes() == writes_before,
    ) == ([second], [(first, "split"), (third, "split")], [second], 1, True)
