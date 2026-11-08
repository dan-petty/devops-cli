# Design

## Decisions

- **One table, read by `isinstance`.** The order of the tuple is the order of the match, most specific first. `RoadmapItemChangedError` comes before `GitHubOperationError`, `StructuredOutputValidationError` before `AIClientError`, and `DevOpsCLIError` is last, so every `DevOpsCLIError` has a class. A test holds that the last entry is `DevOpsCLIError` and that no entry comes after a type that it is a subclass of.
- **`head_moved` for `RoadmapItemChangedError`.** The error means that the item changed while the job worked, and the next round reads it again. No person must act, so `head_moved` (default action `retry`) is right and `plan_defect` is not.
- **`StageFailure` gets two required keyword-only fields.** A default would hide a site that forgets to set the class. The two sites that build a failure in the job set both fields, and the five tests that build one by hand pass them.
- **The two keys go in the existing write.** `_record_failures` already calls `set_marks` once for each failure. The two keys join that call, so the request count does not change.
- **`StepName` has two members.** The stage records `plan` and `apply`. Other issues add members when they use them.

## Rejected alternatives

- **A default class on `StageFailure`.** `ci_infra` as a default would label a plan error that a site forgot to classify. Rejected: it hides a missed site.
- **Classify the exception name with `classify_failure`.** The classifier reads error text with regular expressions. An exception type is exact, and the text rules would depend on the wording of a message. Rejected: `isinstance` is exact and needs no pattern.
- **A new `FailureClass` for the stage.** The class list already holds `provider`, `parser`, `plan_defect`, `ci_infra` and `head_moved`. Rejected: no class is missing (see Feasibility in the proposal).
- **A `RETRY_AFTER` table now.** Nothing reads it before #4060. Rejected: code with no consumer.
