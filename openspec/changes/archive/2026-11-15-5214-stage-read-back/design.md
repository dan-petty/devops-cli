# Design

## Decisions

- **Gate read vs ReadBackError**:
  - A `PlanReadError` is a formatting or parsing error of the model's text. It is returned to the model via gate returns (`READ_GATE`), giving the model an opportunity to fix the syntax.
  - A fact mismatch from `read_back_problems` indicates that valid syntax produced facts that do not match `file_facts(proposal)`. This indicates a writer or reader defect rather than a model failure. Therefore, `_settle` raises `RoadmapPlanReadBackError` immediately with no model return.
- **Pure comparison function**:
  - `plan_read.read_back_problems(files, proposal)` compares only groups, unchanged references, and criteria.
  - Specs are excluded from comparison because `_restored` restores base scenarios not present in the initial proposal.
  - Error messages name only the group number and differing field name, with no plan text.
- **Failure classification**:
  - `RoadmapPlanReadBackError` inherits from `RoadmapStageError`.
  - It is mapped in `CLASS_BY_EXCEPTION` to `FailureClass.PLAN_UNREADABLE` before `RoadmapStageError` so that `isinstance` selects `plan_unreadable`.
  - Action is `wait`, wait duration is 6 hours (`RETRY_AFTER`).
  - `_record_failures` counts `plan_unreadable` alongside `plan_defect` on the same body hash.
- **Fix-plan integration**:
  - When `revise_plan` calls `_settle`, an unreadable plan raises `RoadmapPlanReadBackError`, mapped to `StageFailure` with class `plan_unreadable`.
  - In `_decide`, a failure with no gated plan gives `FixPlanResult.FAILED` (0 pushes). With a gated plan, it gives `FixPlanResult.REGATED` (pushes gated plan).

## Rejected alternatives

- **Check only first redirect or plain word match**:
  - A plain pattern misses complex syntax or process mark combinations. Running `read_change` directly ensures parity with the actual reader.
- **Return fact mismatches to the model**:
  - A fact mismatch is a bug in the code that serializes or deserializes the plan, not a defect in model reasoning. Prompting the model cannot resolve code bugs.
