# Design

## The step knows the cause, so the step passes the class

A stop of the implement job used to carry a string. The classifier then read words in that string. The step knows the exact cause when it makes the stop, so the step passes a class, and the classifier is the fallback for a stop whose cause has no class of its own (a failed command, a hook, a provider error).

- `_Failure` (the exit checks of a step) and `_Run` (a turn of the agent) get a `failure_class`. `_attempt` copies the class to the new field `StepOutcome.failure_class`.
- `_stopped_by` copies it to `_StopError.failure_class`, with the check and the log that `_fix` has.
- `Run.stop` uses `_StopError.failure_class` when it is set. Else it classifies the evidence of the stop, which now includes the log of the check.
- The tier decision `_moves_tier` reads `_Run.failure_class`. The class is set once in `_run_turn`, so the decision and the stop comment use the same class. Before, `_moves_tier` classified `run.reason` a second time.

## The new classes and their default actions

| Class | Site | Default action | Why |
| :--- | :--- | :--- | :--- |
| `no_change_in_fix` | a fix step ends with no changed file | `wait` | The cause is unknown: the check may fail for a reason outside the code. A person reads the failed check, which the stop now names. #3460 owns recovery from a no-op group. |
| `not_ticked` | a task of the group is not ticked after the extra turn | `amend` | The plan cannot be run as written, as for `plan_defect` before. |
| `tests_lost` | the agent removed a test that existed | `retry` | A new run can keep the test. The class was `ci_infra`, whose action is `retry`. |
| `head_moved` | the agent moved HEAD | `retry` | The same reason. |
| `output_cap` | a reply reached the output cap | `raise_limit` | The cap is a limit of the run. |

A step with no changed file in a **group** step stays `plan_defect`: the plan asked for a change that the code does not need, and the amend path of #3057 reads that class. Only the fix step gets `no_change_in_fix`.

## The classifier reads the failure, not the claim

`FailureEvidence` loses the field `agent`. The last message of the agent is a claim that no check verified, so no rule reads it. `_PREMISE` reads the text of the failure only. `_PLAN` loses `changed no file` and `task of the group is not ticked`, as both stops are typed now. A new field `log` holds the log of the check that failed. The rules for the checks of the item read the text, then the log.

Rejected: keep `agent` and weight it below the text. The 05:14Z stop of #2116 shows that any read of the claim can give `premise_false` for a fix step that failed for another reason. A rule that never reads the claim cannot make that error.

## The check and its log

`_StopError` gets `check_log`. `_fix(check, log)` and the scoped-check stop pass the name of the check and the log. `Run.stop` masks the log, keeps its last `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters, shows it in the comment, and writes both to the record keys `implement.check` and `implement.check_log`. A retry clears both keys with the stop. The table shows the check name as the last failing command, as it did for a failed check of the pull request.

Rejected: put the log in the reason. The reason is the text of the failure, and the classifier reads it. A separate field keeps the log out of the cause rules (a test name with `timeout` in it would give the class `timeout`).

## The order of the comment

The comment starts with the failed check: the check that the stop names (a fix step and the scoped checks name one), else the last command of the step that did not exit 0. The log of the check follows when the stop has one. Then come the class lines, the table, the reason, the last message labeled as a claim that no check verified, and the diff. The class lines stay before the reason, as `roadmap-implement-job` requires. The old order started with the class and showed the claim with no label.

## The report reads the item again

`_report` reads the log of the Job, then reads the item again, then decides. A stop that the runner wrote while the log was read has the Status Blocked and a recorded class, so `_settles_as_stop` is false and the recorded class stands.

## The metric labels

`FailureClass` values are the label values. A test reads each file of `k8s/` that names the metric and holds that every `class` matcher in it names a class of the taxonomy. No panel or alert reads the metric today, so the test passes with no match and fails when a later panel uses a wrong value.
