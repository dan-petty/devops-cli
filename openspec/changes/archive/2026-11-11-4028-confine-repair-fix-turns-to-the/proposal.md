# Proposal: #4028

## Why

After a push, a failed check of the pull request gets a fix turn (`ImplementRun._repair_after_push`). Since #3944, a fix turn that changes a path outside the plan stops with the class `outside_plan`. That stop comes after the turn: in pull request #3961 a failed `Plan Check` made the turn edit `src/devops_cli/roadmap/plan_check.py` and spend 217 model requests and 14.4 million tokens. A check whose cause lies outside the plan, such as `Deploy Preview`, gives a fix turn nothing to fix, so the job must not start the turn. Closes #4028.

## What Changes

- A new module, `implement_fix_scope.py`, builds the repair scope: the paths that the plan names and the change folder.
- `_repair_after_push` reads the log of the failed check first. A log that names no path of the scope stops the item as Blocked with no model request. The reason names the check and the scope.
- A log that names a path of the scope gets a fix turn, at most `repair_rounds` times, as before.
- The check of the changed paths of the turn (#3944) stays as it is, and is the guard for the turn itself.

## Capabilities

- `roadmap-implement-job` (modified): the stop of a failed check that is outside the repair scope.

## Impact

- A failed check with no path of the plan in its log stops the item at once. A person reads the reason and comments `implement: retry` after the fix.
- The job reads the log of the failed run before it starts the turn. It read it before too, so no new request is made.
- No setting, command or manifest changes.

## Feasibility

- Source: `_repair_after_push` in `src/devops_cli/roadmap/implement/implement_run.py` called `run_fix_step` for each failed check with no look at the log. `_outside_plan_failure` in `implement_step.py` (#3944) stops a fix step only after the model changed a path outside the plan, so the requests are spent first.
- Source: `failed_log` in `implement_pull.py` reads the log of the failed run, and the fake test world gives a log that names `tests/test_shout.py`, a path of the plan.
- Test run: the new test `test_a_failed_check_that_names_no_path_of_the_plan_stops_the_item_with_no_model_request` fails on `origin/main` and passes with the change.
- The issue also names the annotations of the check run. The change reads the log only. A linter, a type check and a test report the file and line in the log, with the same paths as an annotation, and the log is already read, so the change adds no request.

## Existing Tool Considered

No open tool covers it (the alternatives check of the issue found only generic filesystem servers). The change uses `unplanned_paths` and the group parser of the project, and adds about 60 lines. Cost: about 60,000 tokens to build, 10,000 tokens each month to keep it, and one day of elapsed time.
