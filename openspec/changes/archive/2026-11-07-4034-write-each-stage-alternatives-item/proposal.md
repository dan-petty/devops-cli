# Proposal

## Why

The stage row and the alternatives row of the Service plan every selected item first and write the results after. A stop of the Service, or a kill of the worker when the drain time ends, loses every finished plan of the round. A stage plan can use up to 1.5 million input tokens, so the next round pays for the same work again. #3631 removed this fault for the refine row only (#4034).

Two more faults come from the same order:

- `_plan_each` in `src/devops_cli/roadmap/stage/stage.py` does not catch `ServiceStoppingError`. The error leaves the loop and every finished plan is lost.
- `apply_alternatives` in `src/devops_cli/roadmap/alternatives.py` has no handler for `GitHubRateLimitError`. The round goes on to plan every item although every later write fails.

## What Changes

- The stage row plans one item, writes its result at once, and then plans the next item. The removals and the rejections of the items that the round does not select are written before the first plan call, because they need no model. A rejection of a selected item is written after its plan and before its publish. The moved paths are read for one item, just before its publish.
- A stop of the Service or rejected GitHub credentials end the round. The failures of the finished items are recorded first. Any other error is the failure of one item, and the round goes on.
- The alternatives row writes the body block, the record and the comment of check N before check N+1 starts. A write that fails with a rate limit ends the round and keeps the checks that are written.
- `plan_stage` and `plan_alternatives` take an optional writer, as `plan_refine` takes a `RefineWriter`. With no writer they write nothing, so `--plan` makes no GitHub write. `devops roadmap stage --confirm`, `devops roadmap alternatives --confirm` and the two rows use the same writers.
- The stage writer and the alternatives writer are two adapter classes, one in each module. The stage and alternatives specs gain requirements because the Service behavior changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A round writes each item when the item is done
- `roadmap-alternatives`: A round writes each check when the check is done

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_item_writes.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`

## Feasibility

- I read the code at origin/main. `plan_stage` calls `_plan_each` over all selected targets. `_plan_each` catches `AICredentialsError` (and re-raises it), `AIClientError`, `RoadmapStageError` and `ToolExecutionError` only, so `ServiceStoppingError` leaves the loop. `apply_stage` runs five phases after all plans and calls `_moved_by_item` once for the plan. `_run_stage_adapter` in `src/devops_cli/roadmap/run.py` is `plan_stage` and then `apply_stage`.
- `plan_alternatives` loops `_check_one` over all items, and `apply_alternatives` writes after the loop. It has no handler for `GitHubRateLimitError`. `_run_alternatives_adapter` is `plan_alternatives` and then `apply_alternatives`.
- The pattern exists and is merged: `RefineWriter` in `src/devops_cli/roadmap/refine/refine.py` with `begin`, `settle`, `end` and `raise_for_failures`, and `plan_refine(writer=None)` (#3631). `RefineWriter` is tied to `RefinedItem`, `RefineFailure` and `_apply_result`, so it does not fit stage or alternatives. Each row needs its own adapter.
- The new tests ran against origin/main. The kill test, the stop test and the order test of the stage row fail there, because item 1 has no draft pull request until `apply_stage` runs, and because the first plan call comes before the first removal. The kill test and the rate-limit test of the alternatives row fail there, because check 1 is not written when check 3 is killed, and because the round asks the model about all five items after the write failed. `devops ci fail-to-pass --base origin/main` runs them.
- Three tests are guards that pass on origin/main: the plan-only test of each row, and the test of the rejection of a selected item. They keep the old behavior (a plan makes no write, and the rejection comes between the plan and the publish) while the order changes.
- No merged change and no open pull request does this work, and no ADR or newer issue replaces it.

## Existing Tool Considered

Existing project code. No open library covers the write order of two roadmap rows. The nearest code is `RefineWriter` (#3631). The change follows its pattern with two adapter classes, and it deletes the five-phase `apply_stage` as a batch over a whole plan and the batch loop of `apply_alternatives`. The written cost is about 80k tokens and 3.5 hours to build with the tests, about 3k tokens a quarter to keep, and about 20k tokens and 1 hour for each fault.

## Dependencies

None.
