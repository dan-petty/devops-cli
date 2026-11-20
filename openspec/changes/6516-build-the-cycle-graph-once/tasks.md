# Tasks

## 1. Give a shortest cycle for the item that a caller asks for

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_dependency_graph.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_dependency_graph.py`.

- [ ] 1.1 `test_the_path_of_an_item_is_a_shortest_cycle`, `test_a_self_loop_a_lead_in_and_a_closed_link_keep_their_paths` and `test_a_long_ring_gives_its_item_the_whole_ring` in `tests/roadmap/refine/test_roadmap_dependency_graph.py`: `DependencyGraph.of` over items 1 to 4, where 1 names 2 and 3, 2 names 1, 3 names 4 and 4 names 1, gives `(1, 2, 1)` for item 1; a self-loop gives `(5, 5)`, an item that only leads into a cycle gets None, and a closed item breaks a chain; `DependencyGraph(edges=ring).cycle_of(1)` over a ring of 20,000 items gives the whole ring; the first and the third case fail on the base, which gives `(1, 3, 4, 1)` and gives no path to a graph that holds only edges
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_dependency_graph.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/refine/refine.py`, make `_path_back` a breadth-first search with a queue and one parent for each item that it reaches, in the order of the edges, and build the path from the parents when an edge leads back to the start; make `cycle_of(number)` call `_path_back(self.edges, number)`; remove the `cycles` field, `_holds_a_cycle` and the `graphlib` import
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_dependency_graph.py` passes

## 2. Build the graph once for each stage and implement selection

Kind: behavior. Reads: `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement.py`, `tests/roadmap/stage/test_roadmap_stage_registry.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement.py`, `tests/support/call_counts.py` (new), `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_dependencies.py`.
Adds: `calls_of`

- [ ] 2.1 `test_a_selection_builds_one_dependency_graph_for_its_items` and `test_a_selection_whose_dependencies_are_closed_builds_no_dependency_graph` in `tests/roadmap/stage/test_roadmap_stage_selection.py`, and `test_the_implement_selection_builds_one_dependency_graph_for_its_items` in `tests/roadmap/implement/test_roadmap_implement_selection.py`: `calls_of(DependencyGraph.of)` from `tests/support/call_counts.py` counts the builds through `sys.monitoring`; three stage items and two Staged items that depend on one open issue give one build and the open-issue reason for each item; two stage items whose dependency is closed give no build; the two one-build cases fail on the base, which builds the graph once for each item
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/implement/test_roadmap_implement_selection.py` fails on the base
- [ ] 2.2 Give `open_dependency` in `src/devops_cli/roadmap/dependencies.py` the keyword-only `graph: Callable[[], DependencyGraph]`, which it calls only after it finds an open dependency; give the stage `_Judge` and the implement `_Judge` the `cached_property` `_graph`, which returns `DependencyGraph.of(self._items)`, and pass `graph=lambda: self._graph` from `_dependency`; give `_reason` in `tests/roadmap/test_roadmap_dependencies.py` the graph of the open items
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/implement/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_dependencies.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
