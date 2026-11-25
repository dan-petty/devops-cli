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

import re
from collections.abc import Callable, Collection, Iterable, Iterator, Sequence
from dataclasses import dataclass

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import text_of_a_person
from devops_cli.roadmap.markdown import commonmark_parser
from devops_cli.roadmap.refine.refine import (
    DependencyGraph,
    body_dependencies,
    cycle_text,
    title_dependencies,
)
from devops_cli.roadmap.stores.store import GitHubState, Item, ItemTree, RoadmapStore

_ISSUE_REF_RE = re.compile(r"(?<![A-Za-z0-9_/])#([1-9]\d*)\b")


@dataclass(frozen=True)
class TrackerEntry:
    """One open sub-issue or open related issue of a tracker, with its open blocker numbers."""

    number: int
    title: str
    status: str | None = None
    blockers: tuple[int, ...] = ()


@dataclass(frozen=True)
class TrackerWork:
    """Open deliverable sub-issues and open related issues referenced by a tracker."""

    sub_issues: tuple[TrackerEntry, ...] = ()
    related: tuple[TrackerEntry, ...] = ()


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


def _tracker_entry(
    candidate: Item,
    open_items: Sequence[Item],
    open_by_number: dict[int, Item],
    tree: ItemTree,
) -> TrackerEntry:
    """Build a `TrackerEntry` with declared open blockers for `candidate`."""
    deps = [
        *body_dependencies(candidate.body),
        *title_dependencies(candidate.body, open_items).numbers,
    ]
    blockers = open_blockers(candidate, deps, open_by_number.get, tree)
    return TrackerEntry(
        number=candidate.number,
        title=candidate.title,
        status=candidate.status,
        blockers=blockers,
    )


def _sub_issue_numbers(item: Item, tree: ItemTree, skipped: set[int]) -> tuple[int, ...]:
    """Direct open sub-issues of `item`, expanding non-empty child trackers to their open leaves."""
    expanded: set[int] = set()
    numbers: list[int] = []
    for child in tree.open_sub_issues(item.number):
        if not child.is_tracker:
            numbers.append(child.number)
            continue
        leaves = list(_open_work(child.number, tree, skipped, expanded))
        numbers.extend(leaves or [child.number])
    return tuple(dict.fromkeys(numbers))


def _related_numbers(body: str) -> tuple[int, ...]:
    """Issue `#N` references found in plain inline prose written by a person."""
    found: list[int] = []
    for token in commonmark_parser().parse(text_of_a_person(body)):
        if token.type != "inline":
            continue
        for child in token.children or ():
            if child.type == "text":
                found.extend(int(match.group(1)) for match in _ISSUE_REF_RE.finditer(child.content))
    return tuple(dict.fromkeys(found))


def tracker_work(item: Item, open_items: Sequence[Item]) -> TrackerWork:
    """Return open deliverable sub-issues and open related issues referenced by tracker `item`."""
    open_by_number = {each.number: each for each in open_items if each.state is GitHubState.OPEN}
    tree = ItemTree.of(list(open_by_number.values()))
    ancestors = tree.ancestors(item)
    skipped = {item.number, *ancestors}
    sub_entries = tuple(
        _tracker_entry(open_by_number[number], open_items, open_by_number, tree)
        for number in _sub_issue_numbers(item, tree, skipped)
        if number in open_by_number
    )
    excluded = {item.number, *ancestors, *(entry.number for entry in sub_entries)}
    related_entries = tuple(
        _tracker_entry(open_by_number[number], open_items, open_by_number, tree)
        for number in _related_numbers(item.body)
        if number not in excluded and number in open_by_number
    )
    return TrackerWork(sub_issues=sub_entries, related=related_entries)
