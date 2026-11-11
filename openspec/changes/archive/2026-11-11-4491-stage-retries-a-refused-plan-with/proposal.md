# Proposal: #4491

## Why

The stage job takes a Ready item again each time the `RETRY_AFTER` wait of its failure class passes, and no limit stops it. A plan that the deterministic gates refuse two times ends with `RoadmapStageError` and the class `plan_defect`, which waits 6 hours. `priority_order` puts the same high-priority items first, so each 3-item round takes them again. Closes #4491.

In 48 hours (2026-11-08T23:45Z to 2026-11-10T23:45Z) the stage row failed 47 full rounds with 141 item failures, 81 of them `RoadmapStageError` on 44 items. 27 items failed more than 2 times, and the error rows took 71,951 s of the one model lane. Refine, intake and alternatives waited behind them.

## What Changes

- The stage job counts the `plan_defect` failures of an item on the same body. The new job record keys are `stage.plan_defects`, the count, and `stage.plan_defects_body`, the hash of the body without the block of the alternatives job. A body edit starts a new count. A failure of another class keeps the count and its own `RETRY_AFTER` wait.
- The failure that reaches `CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT` (3) returns the item to New in the same round. The job posts one comment that lists the problems of the refused replies of the last plan in sequence, and then the reason of the failure unless the checks refused the last reply. Then it sets New with the failure marks and clears the count. A log line `stage item returned after refused plans` names the item and the count.
- A staged item clears the count.
- `StageFailure` keeps the problems of the refused replies of its plan, masked and cut as the refused-reply file keeps them.
- New messages `stage_returned_plan_defects` and `stage_returned_plan_defects_log`. The comment is observable, so the change has a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refused plans count on their body; The limit of refused plans returns the item to New; A staged item clears the count of refused plans (all added)

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`, `tests/roadmap/test_roadmap_limit_classes.py` (the class `kept` of the new limit)
- Documents: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`
- The row breaker of `src/devops_cli/roadmap/run.py` and the gates do not change. #4463 and #4467 cover the gate false positives.
- The change fits one pull request.

## Feasibility

The line numbers are those of `main` before this change.

- `RETRY_AFTER` sets `plan_defect` to 6 hours (`src/devops_cli/roadmap/failure.py:161-169`). `_Judge._failed_lately` reads only `stage.failed_at` and `stage.failed_class` (`src/devops_cli/roadmap/stage/stage.py:615`). `_record_failures` writes only those four keys (`stage.py:2670`), and `StageRecordKey` has no count (`src/devops_cli/roadmap/stores/store.py:217`). No code counts the attempts.
- A stage return already has a refine path (#3483). `_stage_return` finds the stage comment after refine's last comment, refine gives its text to the model as `stage_return` (`src/devops_cli/roadmap/refine/refine.py:2350`), and `_returned_twice` makes refine wait for a reply or a body edit after a second return on the same body (`refine.py:1876`). The return at the limit uses this path and adds no refine code.
- The stage planner keeps the problem of each refused reply in `_Planner._refused` and writes them to `<n>.refused.json` (`stage.py:1245`). The failure takes the same list from the planner, so a run with no plan files has the problems too.
- The stage planner does not read the issue comments (`src/devops_cli/roadmap/stage/stage_request.py`), so a comment is no input of a plan while the item is Ready. After the return, refine reads the replies.
- The failures of the 48-hour window (Loki query of #4491) replayed through the rule, with a body that did not change: a limit of 3 returns 10 items. 5 of the 6 plans that staged in the window came after 2 refused plans, and 1 came after 3. In the 7 days from 2026-11-04, 4 of 39 staged plans came after 3 or more refused plans; at the limit, refine looks at such an item once more and the count starts again.
- 8 releases in the same 48 hours changed a gate file of `STAGE_EVAL_TRIGGER_PATHS` or a stage prompt, about one each 6 hours. With the gate version in the key of the count, no item reaches a limit of 3 in the window; with the prompt version, 2 items do. The count therefore keys on the body only.

## Existing Tool Considered

No open tool covers a limit of attempts inside the stage job: the count lives in the job record of the item, as `refine.tries` and `CONST_ROADMAP_REFINE_MAX_TRIES` do for refine (#3632). The change reuses the stage return path of refine (#3483), the body hash of `roadmap/body_hash.py`, `safe_text` and `mask_secrets`. It deletes no internal code. Cost: about 40k tokens to build, 5k tokens a year to keep and fix, about 3 hours elapsed.
