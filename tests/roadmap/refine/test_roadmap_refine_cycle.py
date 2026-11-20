"""A dependency cycle gives a person step that names it, instead of a wait with no end (#6449).

Refine reads the declared dependencies of the open items as one graph for the round, and an item
that a dependency leads back to waits on a person, who removes one edge of the cycle, and not on
the open item that closes it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

import pytest

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.refine.refine import plan_refine, refine_left_out
from devops_cli.roadmap.stores.store import (
    CloseReason,
    Item,
    RefineRecordKey,
    install_roadmap_store,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    REPO,
    blocked_by_issue,
    refine_round,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

# The heading of the part of refine's section that holds the cause of a wait on a person.
_SUSPECTED_BLOCK = "### Suspected block"


class _ListingCountingStore(InMemoryRoadmapStore):
    """The in-memory roadmap, keeping the number of times a round reads its open items and the
    whole item listing, so a test tells whether the graph added a listing of its own."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.open_item_reads = 0
        self.whole_listing_reads = 0

    def open_items(self) -> list[Item]:
        self.open_item_reads += 1
        return super().open_items()

    def items(self, *, milestone: int | None = None) -> list[Item]:
        if milestone is None:
            self.whole_listing_reads += 1
        return super().items(milestone=milestone)


@pytest.fixture
def store() -> _ListingCountingStore:
    """The roadmap, installed as the store every command opens during the test."""
    roadmap = _ListingCountingStore(repo=REPO)
    install_roadmap_store(lambda repo, **_: roadmap)
    return roadmap


def _cycle_message(*path: int) -> str:
    """The sentence that names the cycle `path`, as refine gives it (#6449)."""
    return MESSAGES.roadmap.dependency_cycle.format(
        cycle=" → ".join(f"#{number}" for number in path)
    )


def _under_suspected_block(section: str | None) -> list[str]:
    """The lines of refine's section under its `Suspected block` heading, up to the next one."""
    assert section is not None
    return [
        line.strip()
        for line in section.split(_SUSPECTED_BLOCK, 1)[1].split("### ", 1)[0].splitlines()
        if line.strip()
    ]


def _seed_cycle(
    store: InMemoryRoadmapStore, source: Path, model_fake: ModelFake
) -> tuple[int, int]:
    """A and B where the record of A names B and the Dependencies section of B names A: the first
    round leaves A with the step `blocked` on B, and the body of B closes the cycle (#6449)."""
    store.seed_visibility(is_private=True)
    a = seed_item(store, "New", "P1-High")
    b = seed_item(store, "New", "P1-High", body=f"Body P1-High\n\n## Dependencies\n\n- #{a}\n")
    model_fake.answer(blocked_by_issue(b), READY)
    refine_round(store, source, limit=1)
    return a, b


def test_two_items_in_a_cycle_get_a_person_step(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """Both items of the cycle get the step `person` with a detail that names the path, stay New
    with no Ready Status and record no blocker, and refine's section names the cycle under its
    Suspected block heading: a complete proposal that a cycle holds back is not Ready (#6449)."""
    a, b = _seed_cycle(store, git_repo, model_fake)

    plan = refine_round(store, git_repo)

    item_a, item_b = require_item(store, a), require_item(store, b)
    _, section_a = extract_section_and_outside(store.read_issue_body(a))
    _, section_b = extract_section_and_outside(store.read_issue_body(b))
    assert (
        [
            (r.item.number, r.is_ready, r.next_step, r.step_details, r.blocked_by)
            for r in plan.refined_items
        ],
        [item_a.status, item_b.status],
        [
            item_a.job_record.get(RefineRecordKey.BLOCKED_BY),
            item_b.job_record.get(RefineRecordKey.BLOCKED_BY),
        ],
        [_under_suspected_block(section_a), _under_suspected_block(section_b)],
    ) == (
        [
            (a, False, "person", (_cycle_message(a, b, a),), ()),
            (b, False, "person", (_cycle_message(b, a, b),), ()),
        ],
        ["New", "New"],
        [None, None],
        [["None.", _cycle_message(a, b, a)], ["None.", _cycle_message(b, a, b)]],
    )


def test_the_status_of_an_item_in_a_cycle_stays_new(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """A complete proposal in a cycle is not ready, so the round sets no Ready Status on it: the
    stage job takes no item that the cycle holds back (#6449)."""
    a, b = _seed_cycle(store, git_repo, model_fake)

    refine_round(store, git_repo)

    assert (
        require_item(store, a).status,
        require_item(store, b).status,
        [
            require_item(store, number).job_record.get(RefineRecordKey.NEXT_STEP)
            for number in (a, b)
        ],
    ) == ("New", "New", ["person", "person"])


def test_a_blocked_item_in_a_cycle_is_refined_and_gets_the_person_step(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """The record of A holds the step `blocked` on the open B, and the body of B closes the cycle:
    the round takes A and records `person` with the path (#6449)."""
    a, b = _seed_cycle(store, git_repo, model_fake)
    before = require_item(store, a)

    plan = refine_round(store, git_repo)

    item = require_item(store, a)
    assert (
        before.job_record.get(RefineRecordKey.NEXT_STEP),
        [r.item.number for r in plan.refined_items],
        item.job_record.get(RefineRecordKey.NEXT_STEP),
        item.job_record.get(RefineRecordKey.BLOCKED_BY),
    ) == ("blocked", [a, b], "person", None)


def test_explain_ends_the_wait_that_the_round_ends(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """`devops roadmap explain` reads `refine_left_out`: the blocked wait of an item in a cycle is
    over, so explain names no wait that the round does not have (#3483, #6449)."""
    a, _ = _seed_cycle(store, git_repo, model_fake)

    assert refine_left_out(store, require_item(store, a)) is None


def test_explain_reads_no_graph_for_a_blocked_wait_whose_blocker_closed(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """The record of A holds the step `blocked` on B, and B closed. `refine_left_out` ends the wait
    from the record and reads the open items once, for the frames: it builds no graph, because no
    blocker is open (#6450)."""
    store.seed_visibility(is_private=True)
    a = seed_item(store, "New", "P1-High")
    b = seed_item(store, "New", "P1-High")
    model_fake.answer(blocked_by_issue(b), READY)
    refine_round(store, git_repo, limit=1)
    store.as_actor("alice").close_by_hand(b, CloseReason.COMPLETED)
    before = store.open_item_reads

    explained = refine_left_out(store, require_item(store, a))

    assert (explained, store.open_item_reads - before) == (None, 1)


def test_an_open_dependency_outside_a_cycle_keeps_the_blocked_step(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """B names no open item, so no cycle holds A: the round leaves A with the step `blocked` on the
    open issue B, and its body names no cycle (#6449)."""
    store.seed_visibility(is_private=True)
    a = seed_item(store, "New", "P1-High")
    b = seed_item(store, "New", "P1-High")
    model_fake.answer(blocked_by_issue(b), READY)
    refine_round(store, git_repo, limit=1)

    plan = refine_round(store, git_repo)

    item = require_item(store, a)
    assert (
        [(w.item.number, w.step, w.details) for w in plan.waiting_items],
        a in [r.item.number for r in plan.refined_items],
        item.job_record.get(RefineRecordKey.NEXT_STEP),
        "dependency cycle" in store.read_issue_body(a),
    ) == ([(a, "blocked", (f"#{b}",))], False, "blocked", False)


def test_a_round_calls_open_items_once_for_the_graph(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """The round reads the open items once for the frames and the graph, and the refine of each
    item takes that graph: the round sends no listing of its own (#6449)."""
    _seed_cycle(store, git_repo, model_fake)
    before = store.open_item_reads

    plan = refine_round(store, git_repo)

    assert (
        [r.next_step for r in plan.refined_items],
        store.open_item_reads - before,
    ) == (["person", "person"], 1)


def test_a_round_with_no_candidate_reads_no_listing_for_the_graph(
    store: _ListingCountingStore, git_repo: Path
) -> None:
    """A round that takes no item reads the open items once, for the frames, and the graph adds no
    whole listing: the one whole listing is the backlog's (#6449)."""
    seed_item(store, "In Progress", "P1-High")

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        plan.refined_items,
        store.open_item_reads,
        store.whole_listing_reads,
    ) == ([], 1, 1)


def test_an_edge_to_the_parent_tracker_closes_no_cycle(
    store: _ListingCountingStore, git_repo: Path, model_fake: ModelFake
) -> None:
    """The Dependencies section of the item names its open parent tracker, and the Dependencies
    section of the tracker names the item. The parent tracker is no blocker of its sub-issue, so no
    cycle holds the item, and refine sets it Ready (#6450)."""
    store.seed_visibility(is_private=True)
    tracker = seed_item(store, "In Progress", "P1-High")
    number = seed_item(
        store, "New", "P1-High", body=f"Body P1-High\n\n## Dependencies\n\n- #{tracker}\n"
    )
    store.write_issue_body(tracker, f"Body P1-High\n\n## Dependencies\n\n- #{number}\n")
    store.add_sub_issue(tracker, number)
    model_fake.answer(blocked_by_issue(tracker))

    plan = refine_round(store, git_repo)

    assert (
        [(r.item.number, r.next_step) for r in plan.refined_items],
        require_item(store, number).status,
    ) == ([(number, "ready")], "Ready")
