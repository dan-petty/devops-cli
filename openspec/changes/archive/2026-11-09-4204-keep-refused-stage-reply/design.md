# Design

## Decisions

- **Beside the plan file, one refused file for each item.** The file `<n>.refused.json` is in the folder of `<n>.json` and uses the key of the plan input. Both files are deleted by the same step (`_Writer` staging), so there is one cleanup path. The file holds the replies of the last failed plan only: a new failed plan replaces it, so the count of files is the count of failed items, and each file has a size bound.
- **No age limit.** The plan file has none (see Feasibility), and a second rule would be a second retention rule. A file stays until the item is staged. It is small, and a person can delete it.
- **Degenerate means every text.** The check reads `why`, `existing_tool`, each line of `feasibility` and the tasks `test`, `implementation` and `documentation` of every group, with `is_placeholder`. A reply with one real text goes back once, as before, because the model can mend it. The check runs before the gates, so a degenerate reply costs no gate run.
- **A subclass for the stop.** `RoadmapStageDegenerateError` is a `RoadmapStageError`, so `failure_class_of` gives it `plan_defect` and the retry wait of 6 hours stays. The metric and the eval tell it from `failed` by the type, and `StageFailure.degenerate` carries that fact to `stage_results`. A new `FailureClass` would change the table of actions and the wait, and the issue asks for neither.
- **Log fields from the run trace.** The log line reads the last `RunTrace` of the toolbox client, taken after the item was asked (`floor`), so a trace of an earlier item is no source. A plan with no toolbox run (a kept plan, a plain client) logs `request=1 input_tokens=0 tools_offered=False`.
- **Size bound.** A reply over `CONST_ROADMAP_STAGE_REFUSED_REPLY_MAX_BYTES` (131,072) is dropped and its size stays in `reply_bytes`. A problem is masked with `mask_secrets` and cut at `CONST_ROADMAP_STAGE_REFUSED_PROBLEM_MAX_CHARS` (8,000).

## Rejected alternatives

- **Log the whole reply.** The log has no place for a reply of 100 KB, and it can hold text of the issue. The file is the record. Rejected.
- **A 7-day cleanup of the file.** The plan file has no such cleanup, so the premise of #4204 is false. A new cleanup is new code for a file that is bounded and replaced. Rejected.
- **A new failure class `degenerate`.** It would change `ACTION_BY_CLASS`, `RETRY_AFTER` and every consumer of the class, for a fact that one boolean carries. Rejected.
- **Keep the refused replies of the verify rounds too.** `_repaired` raises its own error, and the issue names the first plan run. It can follow if the data asks for it. Rejected for now.
- **Count the degenerate reply as `failed`.** The metric would hide the placeholder rate, and the eval would have no count. Rejected.
