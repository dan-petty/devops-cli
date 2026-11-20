"""The shared dependency reason of the stage and the implement jobs (#4009, #6449)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.dependencies import open_dependency
from devops_cli.roadmap.refine.refine import DependencyGraph
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ItemField,
    RefineRecordKey,
    encode_job_record,
    with_record,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

PRIORITY = "P2-Medium"


def _seed(
    store: InMemoryRoadmapStore,
    title: str,
    *,
    body: str = "",
    record: Mapping[str, Any] | None = None,
    state: GitHubState = GitHubState.OPEN,
) -> int:
    """An issue whose body holds `body` and the job record `record`."""
    block = encode_job_record({}, record) if record else None
    return store.seed_issue(
        title,
        body=with_record(body, block),
        fields={ItemField.PRIORITY: PRIORITY},
        state=state,
    )


def _reason(store: InMemoryRoadmapStore, number: int) -> str | None:
    """The reason that `open_dependency` gives for issue `number`, over the open items and their
    dependency graph."""
    item = store.item(number)
    assert item is not None
    items = store.open_items()
    return open_dependency(item, store, items, graph=lambda: DependencyGraph.of(items))


def test_the_reason_of_an_item_in_a_cycle_names_the_cycle() -> None:
    """The Dependencies section of A names the open B, and the record of B names A, so the reason
    for A names the path back to A and not only the open issue B (#6449)."""
    store = InMemoryRoadmapStore()
    first = _seed(store, "fix(roadmap): the first")
    second = _seed(
        store, "fix(roadmap): the second", record={RefineRecordKey.BLOCKED_BY: str(first)}
    )
    store.write_issue_body(first, f"### Dependencies\n#{second}\n")

    reason = _reason(store, first)

    assert reason is not None
    assert f"#{first} → #{second} → #{first}" in reason


def test_the_reason_of_an_item_whose_open_dependency_is_in_no_cycle_names_no_cycle() -> None:
    """A depends on the open B, and B depends on no open item, so the reason stays the open-issue
    reason and names no cycle (#6449)."""
    store = InMemoryRoadmapStore()
    blocker = _seed(store, "fix(roadmap): the blocker")
    waiting = _seed(store, "fix(roadmap): the waiting item", body=f"### Dependencies\n#{blocker}\n")

    reason = _reason(store, waiting)

    assert reason == MESSAGES.roadmap.stage_left_dependency.format(issues=f"#{blocker}")
    assert "→" not in reason


def test_the_reason_of_an_item_whose_body_names_no_open_issue_is_none() -> None:
    """The record of A names the open B and the body names no open issue, so the reason is None: an
    item that declares no open dependency gets no reason (#6449)."""
    store = InMemoryRoadmapStore()
    blocker = _seed(store, "fix(roadmap): the blocker")
    recorded = _seed(
        store, "fix(roadmap): the recorded item", record={RefineRecordKey.BLOCKED_BY: str(blocker)}
    )

    assert _reason(store, recorded) is None


def test_a_related_mention_gives_no_reason_and_a_depends_on_line_gives_it() -> None:
    """The Dependencies section of one item says `Related: #N`, and that of another says `Depends
    on #N`, with #N open. The related mention gives no reason, and the blocker line gives the
    reason that names #N (#6451)."""
    store = InMemoryRoadmapStore()
    blocker = _seed(store, "fix(roadmap): the open issue")
    related = _seed(
        store, "fix(roadmap): the related item", body=f"### Dependencies\n\nRelated: #{blocker}\n"
    )
    waiting = _seed(
        store,
        "fix(roadmap): the waiting item",
        body=f"### Dependencies\n\nDepends on #{blocker}\n",
    )

    assert (_reason(store, related), _reason(store, waiting)) == (
        None,
        MESSAGES.roadmap.stage_left_dependency.format(issues=f"#{blocker}"),
    )


def test_the_reason_of_a_held_item_names_the_hold_issue_and_no_link() -> None:
    """The hold line of the freeze names the open hold issue first, its parentheses name the open
    tracker, and a later line names an open related issue. The stage and the implement jobs give a
    reason that names only the hold issue, so the close of that issue lifts the hold (#6451, #6521).
    """
    store = InMemoryRoadmapStore()
    tracker = _seed(store, "refactor(roadmap): the re-architecture")
    hold = _seed(store, "chore(roadmap): hold incremental work")
    related = _seed(store, "fix(roadmap): the related item")
    held = _seed(
        store,
        "fix(roadmap): the held item",
        body=(
            f"### Dependencies\n\n- #{hold} (hold: incremental work on the stage, implement and "
            f"fix-checks jobs waits for the re-architecture of #{tracker})\n\nRelated: #{related}\n"
        ),
    )

    assert _reason(store, held) == MESSAGES.roadmap.stage_left_dependency.format(issues=f"#{hold}")


# ── An open tracker holds back no item (#6450) ───────────────────────────────────────────


def _under(store: InMemoryRoadmapStore, parent: int, *children: int) -> None:
    """Add each of `children` as a sub-issue of `parent`, so `parent` is a tracker."""
    for child in children:
        store.add_sub_issue(parent, child)


def _dependency_reason(*numbers: int) -> str:
    """The reason that names the open blockers `numbers`, in their order."""
    return MESSAGES.roadmap.stage_left_dependency.format(
        issues=", ".join(f"#{number}" for number in numbers)
    )


def test_the_parent_tracker_of_an_item_holds_nothing_back() -> None:
    """The Dependencies section of an item names its open parent tracker: the tracker closes only
    after the item, so it gives no reason (#6450)."""
    store = InMemoryRoadmapStore()
    parent = _seed(store, "feat(roadmap): the tracker")
    child = _seed(store, "fix(roadmap): the child", body=f"### Dependencies\n\n- #{parent}\n")
    _under(store, parent, child)

    assert _reason(store, child) is None


def test_a_tracker_above_the_parent_holds_nothing_back() -> None:
    """The Dependencies section of an item names the open tracker above its parent: it is an
    ancestor of the item, so it gives no reason (#6450)."""
    store = InMemoryRoadmapStore()
    top = _seed(store, "feat(roadmap): the plan")
    parent = _seed(store, "feat(roadmap): the part")
    child = _seed(store, "fix(roadmap): the child", body=f"### Dependencies\n\n- #{top}\n")
    _under(store, top, parent)
    _under(store, parent, child)

    assert _reason(store, child) is None


def test_another_tracker_is_replaced_by_its_open_sub_issues() -> None:
    """The Dependencies section of an item names another open tracker with two open sub-issues and
    one closed sub-issue: the reason names the two open sub-issues and not the tracker (#6450)."""
    store = InMemoryRoadmapStore()
    tracker = _seed(store, "feat(roadmap): another plan")
    first = _seed(store, "fix(roadmap): the first part")
    second = _seed(store, "fix(roadmap): the second part")
    done = _seed(store, "fix(roadmap): the done part", state=GitHubState.CLOSED)
    waiting = _seed(
        store, "fix(roadmap): the waiting item", body=f"### Dependencies\n\n#{tracker}\n"
    )
    _under(store, tracker, first, done, second)

    assert _reason(store, waiting) == _dependency_reason(first, second)


def test_a_tracker_with_no_open_sub_issue_holds_nothing_back() -> None:
    """The Dependencies section names an open tracker whose one sub-issue is closed, and an open
    item with the label `type/epic` and no sub-issue: neither gives a reason (#6450)."""
    store = InMemoryRoadmapStore()
    tracker = _seed(store, "feat(roadmap): the done plan")
    done = _seed(store, "fix(roadmap): the done part", state=GitHubState.CLOSED)
    epic = store.seed_issue(
        "feat(roadmap): the empty epic",
        labels=("type/epic",),
        fields={ItemField.PRIORITY: PRIORITY},
    )
    waiting = _seed(
        store,
        "fix(roadmap): the waiting item",
        body=f"### Dependencies\n\n#{tracker}, #{epic}\n",
    )
    _under(store, tracker, done)

    assert _reason(store, waiting) is None


def test_a_nested_tracker_is_replaced_by_its_open_sub_issues() -> None:
    """Another tracker holds an open tracker and an open plain item, and the inner tracker holds
    one open item. The Dependencies section names both trackers: the reason names the item of the
    inner tracker and the plain item, each once, in the order of the sub-issues (#6450)."""
    store = InMemoryRoadmapStore()
    outer = _seed(store, "feat(roadmap): the plan")
    inner = _seed(store, "feat(roadmap): the inner plan")
    deep = _seed(store, "fix(roadmap): the deep part")
    plain = _seed(store, "fix(roadmap): the plain part")
    waiting = _seed(
        store,
        "fix(roadmap): the waiting item",
        body=f"### Dependencies\n\n#{outer}, #{inner}\n",
    )
    _under(store, outer, inner, plain)
    _under(store, inner, deep)

    assert _reason(store, waiting) == _dependency_reason(deep, plain)


def test_the_item_never_waits_on_itself_among_the_sub_issues_of_another_tracker() -> None:
    """The listing holds the item as a sub-issue of a tracker, but the read of the item gave no
    parent, and the Dependencies section names that tracker and the item itself: the reason names
    the other open sub-issue only, and never the item (#6450)."""
    store = InMemoryRoadmapStore()
    tracker = _seed(store, "feat(roadmap): the plan")
    sibling = _seed(store, "fix(roadmap): the sibling")
    waiting = _seed(store, "fix(roadmap): the waiting item")
    store.write_issue_body(waiting, f"### Dependencies\n\n#{tracker}, #{waiting}\n")
    _under(store, tracker, sibling, waiting)
    read = store.item(waiting)
    assert read is not None
    items = store.open_items()

    reason = open_dependency(
        read.model_copy(update={"parent": None}),
        store,
        items,
        graph=lambda: DependencyGraph.of(items),
    )

    assert reason == _dependency_reason(sibling)


def test_an_open_hold_issue_that_is_no_tracker_still_holds_the_item() -> None:
    """The hold line names an open issue with no sub-issue and no `type/epic` label, and the item
    is a sub-issue of a tracker: the hold issue is no tracker, so it still holds the item back
    (#6450, #6521)."""
    store = InMemoryRoadmapStore()
    parent = _seed(store, "feat(roadmap): the tracker")
    plan = _seed(store, "refactor(roadmap): the re-architecture")
    part = _seed(store, "refactor(roadmap): a part of the re-architecture")
    hold = _seed(store, "chore(roadmap): hold incremental work")
    held = _seed(
        store,
        "fix(roadmap): the held item",
        body=(
            f"### Dependencies\n\n- #{hold} (hold: incremental work waits for the "
            f"re-architecture of #{plan})\n"
        ),
    )
    _under(store, parent, held)
    _under(store, plan, part)

    assert _reason(store, held) == _dependency_reason(hold)
