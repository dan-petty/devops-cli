# Proposal

## Why

A refine round of the Service plans all its items first and writes after. A stop of the Service in the plan of the last item loses the finished work of every earlier item, and the next round spends its model tokens on the same items again. A stop comes often, because each release rolls the Service (#3631).

## What Changes

- `plan_refine` in `src/devops_cli/roadmap/refine/refine.py` takes an optional `writer`. It gives the writer the count of candidates and the result of each item as soon as that item is done. Without a writer it writes nothing, as before.
- A new `RefineWriter` in the same module writes each result with the same code as `apply_refine`. `apply_refine` is now a loop over the same per-item functions, so the CLI and the Service share one write path.
- A write that fails for one item is logged and counted, and the next item still runs. Rejected GitHub credentials and the stop of the Service end the round.
- `raise_for_failed_items` also names the items whose write failed.
- `_run_refine_adapter` in `src/devops_cli/roadmap/run.py` runs the round with a `RefineWriter`.
- The round logs one line at its start and one at its end, with the counts of items taken, written and failed. The texts are fields of `RoadmapMessages`.
- `tests/roadmap/refine/test_roadmap_refine_round.py` holds the tests. One call in `tests/roadmap/refine/test_roadmap_refine_placeholder.py` feeds the writer.
- The `roadmap-refine` capability gains requirements for the per-item write and the round log, because the Service behavior changes.
- The change fits one pull request. The live run over three rollouts needs a release period and moves to #3793.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: A round writes each item when the item is done

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/refine/test_roadmap_refine_round.py`, `tests/roadmap/refine/test_roadmap_refine_placeholder.py`

## Feasibility

- The premise holds in the code. Before this change, `_run_refine_adapter` called `plan_refine`, which looped over all candidates and returned a plan, and then called `apply_refine`, which wrote every item. A stop of the Service in the plan of item 3 raised out of `plan_refine` before any write.
- The test `test_a_round_that_stops_in_item_three_keeps_items_one_and_two_and_the_next_round_takes_three` failed on the base commit: the statuses after the stop were all New. It passes with the change. `devops ci fail-to-pass` runs it.
- The issue #3502, on which the item waited, is closed. The code of the judge verdict is on main.
- The next round takes the items that remain, because the write sets an item Ready or records its hashes, and `select_candidates` reads that state. No new state is needed.

## Existing Tool Considered

Existing project code. No open tool or library covers the per-item write of a roadmap job. The change extends `apply_refine` and `plan_refine` and deletes `_record_unwritten` as a loop over a plan. The written cost is about 40k tokens to build with its tests, about 5k tokens a month to keep, and about 3k tokens for each fix, over about 2 days.

## Dependencies

None.
