# Tasks

## 1. Add the dependency graph and the cycle path of an item

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/support/roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_alert.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_dependency_graph.py` (new).
Adds: `DependencyGraph`, `cycle_text`, `_path_back`

- [ ] 1.1 `test_each_item_of_a_cycle_gets_its_own_path` in `tests/roadmap/refine/test_roadmap_dependency_graph.py`: `DependencyGraph.of` over the items of a store where the record of A names B and the Dependencies section of B names A gives the path `#A → #B → #A` for A and `#B → #A → #B` for B, and gives no path for an item that no cycle holds; a second case builds the graph over a store that counts each read and shows that the count stays zero; the cases fail on the base because `DependencyGraph` does not exist
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_dependency_graph.py` fails on the base
- [ ] 1.2 Add `DependencyGraph`, `cycle_text` and `_path_back` to `src/devops_cli/roadmap/refine/refine.py` beside `body_dependencies`: a frozen dataclass that holds the edges of the open items and the cycle of each item; `DependencyGraph.of(items)` builds the edges from `recorded_blockers(item)`, `body_dependencies(item.body)` and `title_dependencies(item.body, items).numbers`, keeps only the numbers of open items, and gates the graph with one `TopologicalSorter(edges).prepare()` inside a `try` that catches `CycleError`; `cycle_of(number)` gives the path that `_path_back` walks from the item back to it, or no path; `cycle_text(path)` renders `#A → #B → #A`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_dependency_graph.py` passes

## 2. Name the cycle in the shared dependency reason

Kind: behavior. Reads: `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_refine.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dependencies.py` (new).
Adds: `dependency_cycle`

- [ ] 2.1 `test_the_reason_of_an_item_in_a_cycle_names_the_cycle` in `tests/roadmap/test_roadmap_dependencies.py`: `open_dependency` for item A of a store where the record of A names B and the Dependencies section of B names A returns a reason that names `#A → #B → #A`, and the reason of an item whose open dependency is in no cycle stays `MESSAGES.roadmap.stage_left_dependency`; the case fails on the base because `open_dependency` names the open issue only
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dependencies.py` fails on the base
- [ ] 2.2 Add `dependency_cycle` to `src/devops_cli/lang/en/messages.py` beside `stage_left_dependency`, with the path of the cycle and the sentence that a person removes one edge. In `src/devops_cli/roadmap/dependencies.py`, import `DependencyGraph` and `cycle_text` beside `body_dependencies`, and give `open_dependency` the cycle reason before the open-issue reason: build `DependencyGraph.of(items)` from the item sequence that the caller already holds, and return the `dependency_cycle` message with `cycle_text(cycle)` when `cycle_of(item.number)` gives a path
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dependencies.py` passes

## 3. Prove the stage reason names the cycle

Kind: other. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/dependencies.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_selection.py`.

- [ ] 3.1 Add `test_a_dependency_cycle_names_the_cycle_in_the_reason` to `tests/roadmap/stage/test_roadmap_stage_selection.py` beside the case that asserts `stage_left_dependency`: the stage plan leaves item A out with a reason that names `#A → #B → #A`, where the record of A names B and the Dependencies section of B names A, and an item whose open dependency is in no cycle keeps the open-issue reason that `open_dependency` gives
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py` passes

## 4. Prove the implement reason names the cycle

Kind: other. Reads: `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/dependencies.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_selection.py`.

- [ ] 4.1 Add `test_a_dependency_cycle_names_the_cycle_in_the_reason` to `tests/roadmap/implement/test_roadmap_implement_selection.py` beside the case that asserts `stage_left_dependency`: the reason that `_reasons` gives for item A names `#A → #B → #A` and not only `#B`, where the record of A names B and the Dependencies section of B names A
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py` passes

## 5. Give a dependency cycle a person step in refine

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_proposal.py`, `tests/roadmap/refine/test_roadmap_refine_blocked.py`, `tests/support/roadmap_refine.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_cycle.py` (new), `tests/roadmap/refine/test_roadmap_refine_proposal.py`.

- [ ] 5.1 `test_two_items_in_a_cycle_get_a_person_step`, `test_the_status_of_an_item_in_a_cycle_stays_new`, `test_a_blocked_item_in_a_cycle_is_refined_and_gets_the_person_step` and `test_explain_ends_the_wait_that_the_round_ends` in `tests/roadmap/refine/test_roadmap_refine_cycle.py`, which cover the requirement `A dependency cycle gives a person step that names it` with the scenario `Two items in a cycle` and the requirement `A cycle keeps an item out of Ready and ends its wait` with the scenarios `The Status of an item in a cycle stays New`, `The recorded wait of a blocked item in a cycle ends` and `Explain ends the wait that the round ends`, and `test_an_open_dependency_outside_a_cycle_keeps_the_blocked_step` for the requirement `An open dependency outside a cycle blocks the item` and its scenarios `A complete proposal with one open dependency`, `A Ready item with an open dependency` and `A closed dependency`: one refine round over items A and B, where the record of A names B and the Dependencies section of B names A and each proposal is complete, gives both the step `person` with a detail that names `#A → #B → #A` or `#B → #A → #B`, leaves both items New with no Ready label, records no blocker for either, and writes the cycle under the Suspected block heading of each section; a second case starts from a record that holds the step `blocked` and shows that the round refines the item and records `person`; a third case gives the same record to `refine_left_out` and shows that it returns None, so `devops roadmap explain` takes the item; the last case gives A the step `blocked` with `#B` when B names no open item, and the record of A keeps that step and names no cycle; the cases fail on the base, where a complete proposal takes `ready` and a recorded `blocked` item is left waiting
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_cycle.py` fails on the base
- [ ] 5.2 In `src/devops_cli/roadmap/refine/refine.py`, add the required keyword `cycle` to `check_ready` and return False when it is set, so a proposal in a cycle is never Ready and the Status stays New; update each case of `tests/roadmap/refine/test_roadmap_refine_proposal.py` with `cycle=False` and add one case with a cycle that is not ready. Give `_Selection` the field `graph` and pass it to `_still_waiting`; give `_still_waiting` the keyword `graph` that defaults to None, and in its `BLOCKED` branch build `DependencyGraph.of(store.items())` when the caller gives none and return None when `cycle_of(item.number)` gives a path, so `refine_left_out` for `devops roadmap explain` and `select_candidates` end the same wait that a round ends. Build the graph once in `_select_round`, before the `_Selection` is made, from the milestone items and the backlog items that the round already read, and give it to the selection; `_select_single_candidate` needs none. In `refine_one_item`, bind `items = store.items()` once at the `title_dependencies` call, take `cycle = DependencyGraph.of(items).cycle_of(item.number)` from it, pass `cycle=bool(cycle)` to `check_ready` and `cycle=cycle` to `next_step_of`, and give `render_proposal_section` the keyword `cycle` so the Suspected block part holds `cycle_text(cycle)` instead of `None.` when a cycle exists; in `next_step_of`, after the alternatives branch and before the ready branch, return `NextStep.PERSON` with the one detail of the `dependency_cycle` message and no blockers
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_cycle.py` passes

## Criteria

- Group 5: Test first: a store with items A and B, where the record of A names B and the Dependencies section of B names A. Refine gives each item a person step that names the cycle `A → B → A`. The test fails on the base.
- Group 3: A test: the stage and implement reason for an item in a cycle names the cycle, not only "depends on the open issue".
- Group 5: A test: an item whose dependency is open but not in a cycle keeps the step `blocked`.
- Group 5: The graph is read once for each round from the listing that the round already holds. The round sends no extra GitHub request.
- Pending person: Live proof: after the release, the next refine round gives #4691 or #4692 a person step that names its cycle., Only a person can read the live refine round after a release, and this run reads no GitHub state.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
