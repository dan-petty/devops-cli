# Proposal: #6515

## Why
Refine decides whether a refined item is in a dependency cycle from the `DependencyGraph` built at the start of the round, using the item's old record and body rather than the dependencies of its new proposal. When a person replies to remove the last cycle edge and the model outputs no dependency, refine still records a `person` cycle wait on that round and consumes the reply. Conversely, refine ends a blocked wait on a cycle edge only under `NextStep.BLOCKED`, leaving an item stuck in a `NextStep.PERSON` cycle wait after another item edits its body to break the cycle. `docs/roadmap/refine.md` also omits the cycle step from the list of next steps and states that any open dependency makes an item wait.

## What Changes
- Decouple the cycle check during item refinement (`refine_one_item` and round graph updates in `src/devops_cli/roadmap/refine/refine.py`) from the item's stale pre-round edges by computing its cycle from its new validated proposal's open blockers against the rest of the round's graph.
- End a `NextStep.PERSON` wait whose recorded dependency cycle in `### Suspected block` no longer exists in the current `DependencyGraph` of open items.
- Update `docs/roadmap/refine.md` to list the dependency cycle step and state that only an open dependency outside a cycle makes an item wait.
- Advance `CONST_ROADMAP_REFINE_RULES_SINCE` in `src/devops_cli/config/constants.py` so items stranded in a stale cycle wait under earlier rules receive one new look.
- Add failing-first regression tests in `tests/roadmap/refine/test_roadmap_refine_cycle.py` covering reply edge removal, stale cycle wait clearance, and the guide text.

## Capabilities
- `roadmap-refine/waits`: Cycle step calculation from new proposal dependencies, stale cycle wait clearance on `NextStep.PERSON`, and refine guide documentation.

## Impact
- `src/devops_cli/roadmap/refine/refine.py`: `DependencyGraph.with_edges`, recorded cycle detection and graph edge check in `_still_waiting`, proposal-edge cycle check in `refine_one_item`.
- `src/devops_cli/config/constants.py`: Bump `CONST_ROADMAP_REFINE_RULES_SINCE` timestamp.
- `docs/roadmap/refine.md`: Update next-step list, cycle wait rule, and rule version documentation.
- `tests/roadmap/refine/test_roadmap_refine_cycle.py`: Update cycle helper answers and add regression tests for `-k reply_removes_edge`, `-k stale_cycle_wait_ends`, and `-k guide`.

## Feasibility
Confirmed against `src/devops_cli/roadmap/refine/refine.py` (`_still_waiting` only checks `cycle_of` under `NextStep.BLOCKED`; `refine_one_item` calls `held.cycle_of(item.number)` instead of substituting `blockers`), `src/devops_cli/config/constants.py` (`CONST_ROADMAP_REFINE_RULES_SINCE`), and `docs/roadmap/refine.md` (lines 11-22 and 33).

## Existing Tool Considered
The alternatives check in `#6515` gives the verdict `none` (`depcycle`, `pydeps`, and `DepMapper` analyze Python module imports, not GitHub issue dependency graphs). Extending the existing cycle helper in `src/devops_cli/roadmap/refine/refine.py` takes ~150 lines / 2 hours with zero new dependencies.
