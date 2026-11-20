"""The open issue that an item's Dependencies section names (#4009).

The stage job and the implement job read the same declaration: a `#N` in the Dependencies section
of the body (#2654), or a quoted title of another item (#4803). A dependency that is still open
holds both jobs back, and the message is the same in both. An item that a dependency leads back to
gets the reason of its cycle, so the jobs name the cycle and not only the next open issue (#6449).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.refine.refine import (
    DependencyGraph,
    body_dependencies,
    cycle_text,
    title_dependencies,
)
from devops_cli.roadmap.stores.store import GitHubState, Item, RoadmapStore


def open_issue_dependencies(numbers: Iterable[int], store: RoadmapStore) -> str | None:
    """The reason that the open issues of `numbers` give, or None when every dependency is closed
    or the list names none."""
    open_issues = [
        f"#{number}"
        for number in dict.fromkeys(numbers)
        if (found := store.item(number)) is not None and found.state is GitHubState.OPEN
    ]
    if not open_issues:
        return None
    return MESSAGES.roadmap.stage_left_dependency.format(issues=", ".join(open_issues))


def open_dependency(item: Item, store: RoadmapStore, items: Sequence[Item]) -> str | None:
    """The reason that the open issue named by the Dependencies section of `item` gives, or None
    when every dependency is closed or the body names none. An item that a dependency leads back to
    gets the reason of its cycle (#6449)."""
    open_reason = open_issue_dependencies(
        [
            *body_dependencies(item.body),
            *title_dependencies(item.body, items).numbers,
        ],
        store,
    )
    if open_reason is None:
        return None
    cycle = DependencyGraph.of(items).cycle_of(item.number)
    if cycle is None:
        return open_reason
    return MESSAGES.roadmap.dependency_cycle.format(cycle=cycle_text(cycle))
