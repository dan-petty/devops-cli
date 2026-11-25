"""The open issue that an item's Dependencies section names (#4009).

The stage job and the implement job read the same declaration: a blocker `#N` in the Dependencies
section of the body (#2654, #6451), or a quoted title of another item (#4803). A dependency that is still open
holds both jobs back, and the message is the same in both. An item that a dependency leads back to
gets the reason of its cycle, so the jobs name the cycle and not only the next open issue (#6449).
Each job builds the dependency graph at most once for each selection and gives it to each item
(#6516).

One rule decides which open dependency is a blocker, for refine, stage, implement and the
dependency graph (`open_blockers`, #6450). No job closes a tracker: it closes after its
sub-issues. So the parent tracker of an item, and each tracker above it, is no blocker of the
item, and an item waits on the open sub-issues of another tracker, not on the tracker.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Iterator, Sequence

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine.refine import (
    DependencyGraph,
    body_dependencies,
    cycle_text,
    title_dependencies,
)
from devops_cli.roadmap.stores.store import GitHubState, Item, ItemTree, RoadmapStore


def open_blockers(
    item: Item,
    numbers: Iterable[int],
    found: Callable[[int], Item | None],
    tree: ItemTree,
) -> tuple[int, ...]:
    """The open issues among the dependencies `numbers` of `item` that hold it back, in the order
    of `numbers` and then of the sub-issues, each once (#6450). `found` reads one dependency, and
    `tree` holds the sub-issue links of the read.

    The item itself and each of its ancestors, its parent tracker and each tracker above it, is no
    blocker. An open tracker gives its open sub-issues in its place, a sub-issue that is a tracker
    gives its own, and none is the item or an ancestor of it: a tracker with no open sub-issue
    holds nothing back. A closed issue and a number that `found` does not know hold nothing back.
    Any other open dependency is a blocker.
    """
    blockers: dict[int, None] = {}
    expanded: set[int] = set()
    for number in dict.fromkeys(numbers):
        if number in (item.number, item.parent):
            continue
        dependency = found(number)
        if dependency is None or dependency.state is not GitHubState.OPEN:
            continue
        if not dependency.is_tracker:
            blockers[number] = None
            continue
        ancestors = tree.ancestors(item)
        if number in ancestors:
            continue
        skipped = {item.number, *ancestors}
        blockers.update(dict.fromkeys(_open_work(number, tree, skipped, expanded)))
    return tuple(blockers)


def _open_work(
    tracker: int, tree: ItemTree, skipped: set[int], expanded: set[int]
) -> Iterator[int]:
    """The open sub-issues that deliver `tracker`, lowest number first, each sub-issue that is a
    tracker replaced by its own. `skipped` holds the item and its ancestors, and `expanded` the
    trackers already read, so a tracker is read once."""
    if tracker in expanded:
        return
    expanded.add(tracker)
    for sub_issue in tree.open_sub_issues(tracker):
        if sub_issue.number in skipped:
            continue
        if sub_issue.is_tracker:
            yield from _open_work(sub_issue.number, tree, skipped, expanded)
        else:
            yield sub_issue.number


def open_issue_dependencies(
    item: Item,
    numbers: Iterable[int],
    open_numbers: Collection[int],
    items: Sequence[Item],
) -> str | None:
    """The reason that the open blockers among the dependencies `numbers` of `item` give
    (`open_blockers`, #6450), or None when no dependency holds the item back. `open_numbers` is the
    set of open item numbers, and `items` is the read whose sub-issue links the rule follows."""
    tree = ItemTree.of(items)
    blockers = open_blockers(
        item,
        numbers,
        lambda n: tree.item(n) if n in open_numbers else None,
        tree,
    )
    if not blockers:
        return None
    return MESSAGES.roadmap.stage_left_dependency.format(
        issues=", ".join(f"#{number}" for number in blockers)
    )


def open_dependency(
    item: Item,
    store: RoadmapStore,
    items: Sequence[Item],
    *,
    graph: Callable[[], DependencyGraph],
) -> str | None:
    """The reason that the open issue named by the Dependencies section of `item` gives, or None
    when every dependency is closed or the body names none. An item that a dependency leads back to
    gets the reason of its cycle (#6449). `graph` returns the dependency graph of the selection,
    and the call reads it only when a dependency is open, so a caller that builds the graph on its
    first call builds it at most once for each selection and builds none when no item has an open
    dependency (#6516)."""
    open_numbers = {it.number for it in items if it.state is GitHubState.OPEN}
    open_reason = open_issue_dependencies(
        item,
        [
            *body_dependencies(item.body),
            *title_dependencies(item.body, items).numbers,
        ],
        open_numbers,
        items,
    )
    if open_reason is None:
        return None
    cycle = graph().cycle_of(item.number)
    if cycle is None:
        return open_reason
    return MESSAGES.roadmap.dependency_cycle.format(cycle=cycle_text(cycle))
