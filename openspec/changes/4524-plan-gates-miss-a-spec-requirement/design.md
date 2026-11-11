# Design

## Decisions

- **The rule lives in `_delta_problems`.** `check_proposal` runs it in the stage job, in `devops roadmap plan-check` and in the replay, so one rule serves the three paths. The rule is a new function, `_length_problems`, so that the change does not touch the trace gate of `stage_change.py` that #4495 changes.
- **One constant holds the limit.** `REQUIREMENT_MAX_CHARS` sits next to `PURPOSE_MIN_CHARS`, the other OpenSpec limit of the spec delta. Its comment names `MAX_REQUIREMENT_TEXT_LENGTH` of OpenSpec. `plan_check.py` gets the rule through `check_proposal`, so it does not import the constant.
- **The rule reads ADDED and MODIFIED.** The archive merges both into the spec. The REMOVED and RENAMED sections hold no requirement text.
- **The count is in UTF-16 code units.** OpenSpec measures a JavaScript string, so a character outside the Basic Multilingual Plane counts two. The text that `plan-check` reads from a file is folded to one line; a run of spaces inside a line counts one, and OpenSpec counts each space.
- **The problem names the requirement, its length and the limit.** A delta can hold many requirements, and the planner must know which text to shorten and by how much.

## Rejected alternatives

- **Run the OpenSpec validation of the merged spec in the gate.** OpenSpec has no command that validates a change as the merged spec. The gate would have to merge the delta into a copy of the spec first, which is the work of the implement plan gate (#3429).
- **A `max_length` on the `text` field of `StageRequirement`.** The schema error would not name the requirement, and `plan-check` would report a read problem, not a gate problem.
- **State the limit in the stage prompt.** The refusal goes back to the model with the requirement name and the length, as each rule of `check_proposal` does. A prompt change needs a model run before and after; the issue asks for the gate.
