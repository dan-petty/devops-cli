# Proposal: #6516

## Why

Since #6449, `open_dependency` builds the dependency graph of all open items each time that it finds an open dependency (#6516). The stage judge and the implement judge call it once for each item that they judge, so a selection builds the full graph again for each item that depends on an open issue. One build over 798 open items takes 3.3 s, and one `devops roadmap explain 4814` built the graph 28 times, 93.7 s of 321 s. The path search `_path_back` is a last-in-first-out search that copies the path at each step: it does not give the shortest cycle, and a ring of 20,000 items did not end in 3 minutes.

## What Changes

- `open_dependency` in `src/devops_cli/roadmap/dependencies.py` takes the graph from its caller as the keyword-only `graph`: a function that returns the graph of the selection. It calls the function only when a dependency of the item is open.
- The stage judge (`src/devops_cli/roadmap/stage/stage.py`) and the implement judge (`src/devops_cli/roadmap/implement/implement.py`) each hold the graph of their items as a `cached_property`. The first judged item with an open dependency builds it, and each later item reads the same graph. A selection with no open dependency builds no graph.
- `DependencyGraph.cycle_of` in `src/devops_cli/roadmap/refine/refine.py` searches for the one item that the caller asks for. `_path_back` becomes a breadth-first search with one parent for each item that it reaches. It gives a shortest cycle through the item, in the order of the edges, and it builds the path only at the end.
- The change removes the `cycles` field of `DependencyGraph`, `_holds_a_cycle` and the import of `graphlib`: the graph computed a path for each open item when it held a cycle, and the callers read only the path of the item that they judge.
- Refine keeps its one graph for each round (`plan_refine`). `devops roadmap explain` runs the refine, the stage and the implement selections, so it builds at most one graph for each of them.
- The named cycle is output that a person reads, so the change modifies the capability `roadmap-dependency-cycle`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-dependency-cycle`: The dependency graph names a cycle for each item, The shared dependency reason names a dependency cycle, Stage and implement build one graph for each selection

## Impact

- Code: `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement.py`
- Tests: `tests/roadmap/refine/test_roadmap_dependency_graph.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_dependencies.py`, `tests/support/call_counts.py` (new)
- A stage round of the Service builds one graph and not one for each judged item with an open dependency.

## Feasibility

- `git show origin/main:src/devops_cli/roadmap/dependencies.py` at d27abc8b1 shows `cycle = DependencyGraph.of(items).cycle_of(item.number)` at line 49 of `open_dependency`, after the open-issue reason.
- `git grep` at d27abc8b1 shows the two per-item callers: `src/devops_cli/roadmap/stage/stage.py:774` and `src/devops_cli/roadmap/implement/implement.py:382` both return `open_dependency(item, self._store, self._items)`. Refine builds the graph once in `plan_refine` (`src/devops_cli/roadmap/refine/refine.py:3854`) and gives it to the selection and to each item.
- The issue measured on 2026-11-20: one build over the 798 open items takes 3.3 s, and one `devops roadmap explain 4814` called `DependencyGraph.of` 28 times, 93.7 s of 321 s.
- A scratch timing at d27abc8b1 of `DependencyGraph.of` over rings of items whose job record names the next item gives 0.39 s for 300 items, 0.96 s for 500 items and 4.93 s for 1,000 items: the graph computed the path of each item with a path copy at each step. A chain of 5,000 items with no cycle takes 4.73 s, which is the parse of the bodies.
- `graphlib` raises `CycleError("nodes are in a cycle", cycle)` with one cycle that it found first, and not a shortest cycle through a given item.
- `grep` of `uv.lock` finds no graph library: networkx, rustworkx and igraph are absent.

## Existing Tool Considered

`graphlib` of the Python standard library names only one cycle of the graph, and not a shortest cycle through the item that a caller asks for. The lock file holds no graph library (networkx, rustworkx and igraph are absent), and a new dependency for one search of a graph of about 800 nodes costs more than the search. The change keeps the search in `_path_back`: a breadth-first search of about 15 lines, about 2,000 tokens to write and keep, and less than one hour. The change deletes the internal `_holds_a_cycle`, the `cycles` field of `DependencyGraph` and the eager path of each open item.

## Dependencies

None.
