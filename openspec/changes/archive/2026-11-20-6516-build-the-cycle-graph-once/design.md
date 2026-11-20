# Design

## Decisions

- **One lazy graph for each judge.** The stage `_Judge` and the implement `_Judge` each hold `_graph`, a `functools.cached_property` that returns `DependencyGraph.of(self._items)`. A judge lives for one selection, so the graph is built at most once for each selection, and only when the first judged item has an open dependency. The judge already holds `_items`, every item open and closed, as a `cached_property` (#4803), so the graph reads no new listing.
- **The caller gives the graph as a function.** `open_dependency(item, store, items, *, graph)` takes `graph: Callable[[], DependencyGraph]` and calls it only after it finds an open dependency. A function keeps the build lazy: a parameter of type `DependencyGraph` makes the caller build the graph before it knows that an item needs it. The judges give `lambda: self._graph`.
- **A shortest cycle from one breadth-first search.** `_path_back(edges, start)` walks the edges from `start` in the order of the edges with a queue, and keeps one parent for each item that it reaches. The first edge back to `start` closes a shortest cycle, because the search reaches each item at its least distance first. The path is built once, from the parents, at the end. The search is O(V + E) for one item, and copies no path at each step.
- **The search runs for the item that a caller asks for.** `cycle_of(number)` calls `_path_back` for that item. The graph no longer computes a path for each open item when it holds a cycle, so the `cycles` field, `_holds_a_cycle` and the `graphlib` gate go. The callers ask for the items that they judge: about 27 to 130 items for a stage selection, and not each of the 798 open items.
- **The results that stay.** A self-loop gives `#A → #A`, two items that name each other give `#A → #B → #A`, an item that only leads into a cycle gets no path, and a closed item between two open items breaks their chain. The tests hold each of these.
- **Refine and explain.** Refine already builds one graph for each round and gives it to the selection and to each item, so it stays as it is. `devops roadmap explain` runs three selections (refine, stage and implement), and each builds at most one graph.
- **The count in tests.** A test counts the calls of `DependencyGraph.of` with `sys.monitoring` (PEP 669) in `tests/support/call_counts.py`, so it replaces no function of `devops_cli` (docs/TESTING.md, Doubles). `tests/roadmap/stage/test_roadmap_stage_registry.py` uses the same interface to count the calls of `ast.parse`.

## Rejected alternatives

- **A graph library.** `graphlib` names only one cycle (`CycleError.args[1]`), and not a shortest cycle through a given item. The lock file has no networkx, rustworkx or igraph, and a new dependency for one search over about 800 nodes costs more than the 15 lines of the search.
- **An eager graph for each selection.** The judge builds the graph when the selection starts. A selection with no open dependency then spends 3.3 s on a graph that it does not read.
- **A cache on `DependencyGraph.of`.** A module cache keyed on the sequence of items needs a key over 800 bodies, and it keeps the graph of each selection alive after the selection ends.
- **A `DependencyGraph` parameter for `open_dependency`.** The caller then builds the graph before it knows that an item has an open dependency, which is the eager build above.
- **A path for each open item in `DependencyGraph.of`.** A breadth-first search for each of n items is O(n × (V + E)): a ring of 20,000 items is 4 × 10^8 steps. The callers read the path of the items that they judge only.
- **Floyd-Warshall.** It computes all shortest paths in O(V^3) time and O(V^2) memory, which a ring of 20,000 items cannot afford.
- **One graph for the three selections of explain.** It adds a graph parameter to `refine_left_out`, `read_stage_selection` and `plan_implement` to save at most two builds of one command. Each selection builds at most once.
