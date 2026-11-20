"""The declared dependencies of the open items as one graph, and the path back to each item that a
dependency leads back to (#6449).
"""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.roadmap.refine.refine import DependencyGraph

from devops_cli.roadmap.stores.store import GitHubState, Item, JobRecord, RefineRecordKey


def _item(
    number: int,
    *,
    record: int | None = None,
    body: str = "",
    state: GitHubState = GitHubState.OPEN,
) -> Item:
    """An item that its job record names as blocked by `record`, with `body`."""
    record_block: JobRecord = {} if record is None else {RefineRecordKey.BLOCKED_BY: str(record)}
    return Item(
        number=number,
        title=f"Item {number}",
        url=f"https://example.com/{number}",
        body=body,
        state=state,
        job_record=record_block,
    )


def _depends_on(*numbers: int) -> str:
    """A body whose Dependencies section names each of `numbers`."""
    lines = "\n".join(f"- #{number}" for number in numbers)
    return f"## Dependencies\n\n{lines}\n"


def _names_cycle(graph: DependencyGraph, number: int) -> bool:
    """Whether the graph gives `number` a path that starts and ends at it and walks its edges."""
    path = graph.cycle_of(number)
    return (
        path is not None
        and path[0] == path[-1] == number
        and all(next_number in graph.edges[at] for at, next_number in pairwise(path))
    )


def test_each_item_of_a_cycle_gets_its_own_path() -> None:
    """The record of A names B and the Dependencies section of B names A: A gets the path back to
    A through B, B the path back to B through A, and the item that no dependency names gets
    none."""
    from devops_cli.roadmap.refine.refine import DependencyGraph

    a = _item(1, record=2)
    b = _item(2, body=_depends_on(1))
    lonely = _item(3)

    graph = DependencyGraph.of([a, b, lonely])

    assert (
        graph.cycle_of(1),
        graph.cycle_of(2),
        graph.cycle_of(3),
        [_names_cycle(graph, number) for number in (1, 2, 3)],
    ) == ((1, 2, 1), (2, 1, 2), None, [True, True, False])


def test_cycle_text_names_the_path_of_a_cycle() -> None:
    """A path reads as the numbers of its items, joined by an arrow."""
    from devops_cli.roadmap.refine.refine import cycle_text

    assert cycle_text((1, 2, 1)) == "#1 → #2 → #1"


def test_an_edge_to_an_issue_outside_the_sequence_is_dropped() -> None:
    """The graph is a function of the sequence it is given: a record that names #999, which the
    sequence does not hold, gives no edge and no path."""
    from devops_cli.roadmap.refine.refine import DependencyGraph

    a = _item(1, record=999)
    b = _item(2, record=999)

    graph = DependencyGraph.of([a, b])

    assert (graph.edges, graph.cycle_of(1), graph.cycle_of(2)) == ({1: (), 2: ()}, None, None)


def test_a_closed_dependency_gives_no_edge() -> None:
    """A closed issue holds nothing back, so it is no node and the open item that names it gets no
    edge and no path."""
    from devops_cli.roadmap.refine.refine import DependencyGraph

    open_item = _item(1, record=2)
    closed = _item(2, state=GitHubState.CLOSED)

    graph = DependencyGraph.of([open_item, closed])

    assert (graph.edges, graph.cycle_of(1)) == ({1: ()}, None)


def test_two_cycles_that_share_an_edge() -> None:
    """A → B → A and A → B → C → A share the edge A → B: each of A, B and C gets a path of its
    own, so the shared edge hides none of them."""
    from devops_cli.roadmap.refine.refine import DependencyGraph

    a = _item(1, record=2)
    b = _item(2, body=_depends_on(1, 3))
    c = _item(3, body=_depends_on(1))

    graph = DependencyGraph.of([a, b, c])

    assert [_names_cycle(graph, number) for number in (1, 2, 3)] == [True, True, True]


def test_the_path_of_an_item_is_a_shortest_cycle() -> None:
    """A names B and C, B names A, C names D and D names A: the path of A is the shorter cycle
    `#A → #B → #A`, and not `#A → #C → #D → #A`. Each other item gets its own shortest cycle
    (#6516)."""
    from devops_cli.roadmap.refine.refine import DependencyGraph

    graph = DependencyGraph.of(
        [
            _item(1, body=_depends_on(2, 3)),
            _item(2, body=_depends_on(1)),
            _item(3, body=_depends_on(4)),
            _item(4, body=_depends_on(1)),
        ]
    )

    assert [graph.cycle_of(number) for number in (1, 2, 3, 4)] == [
        (1, 2, 1),
        (2, 1, 2),
        (3, 4, 1, 3),
        (4, 1, 3, 4),
    ]


def test_a_self_loop_a_lead_in_and_a_closed_link_keep_their_paths() -> None:
    """An item that names itself gets the path back to itself. An item that only leads into the
    cycle of two others gets no path, and each of the two gets its own. A closed item between two
    open items breaks their chain, so neither gets a path (#6516)."""
    from devops_cli.roadmap.refine.refine import DependencyGraph

    graph = DependencyGraph.of(
        [
            _item(5, record=5),
            _item(6, record=7),
            _item(7, record=8),
            _item(8, record=7),
            _item(9, record=10),
            _item(10, record=9, state=GitHubState.CLOSED),
        ]
    )

    assert [graph.cycle_of(number) for number in (5, 6, 7, 8, 9)] == [
        (5, 5),
        None,
        (7, 8, 7),
        (8, 7, 8),
        None,
    ]


def test_a_long_ring_gives_its_item_the_whole_ring() -> None:
    """In a ring of 20,000 items, each item names the next and the last names the first: the
    path of the first item is the whole ring back to it. The search keeps one parent for each item,
    so the ring ends in one pass and copies no path at each step (#6516)."""
    from devops_cli.roadmap.refine.refine import DependencyGraph

    size = 20_000
    ring = {number: (number % size + 1,) for number in range(1, size + 1)}

    assert DependencyGraph(edges=ring).cycle_of(1) == (*range(1, size + 1), 1)
