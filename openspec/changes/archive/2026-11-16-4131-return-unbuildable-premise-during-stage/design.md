# Design: #4131

## Architecture Overview
`apply_return(store, plan)` in `src/devops_cli/roadmap/return_item.py` is the canonical implementation of returning a roadmap item to New with an evidence comment.
Previously, stage return functions (`_return_premise`, `_return_blocked`, `_return_plan_defects`, `_reject_plan`, and `_return_for_split`) called `store.comment(...)` and `write_status(...)` directly because `ReturnPlan` did not accept record marks.
By adding `marks` to `ReturnPlan` and `plan_return`, all return writers in `stage.py` and `stage_job.py` can call `apply_return(store, plan_return(store, item.number, comment, repo, marks=marks))`.

## Key Decisions
1. **Extend `ReturnPlan` and `plan_return` with `marks`**:
   - `ReturnPlan.marks: Mapping[Any, str | int | None] | None = None`
   - `plan_return(..., *, marks: Mapping[Any, str | int | None] | None = None)`
   - `apply_return` calls `write_status(store, item, _RETURNED, marks=plan.marks)`.
2. **Unified Return Writers**:
   - `_return_premise`: calls `apply_return` with `marks={RefineRecordKey.NEXT_STEP: NextStep.EDIT.value}`.
   - `_return_blocked`: calls `apply_return` with `marks={RefineRecordKey.BLOCKED_BY: ..., RefineRecordKey.NEXT_STEP: ...}`.
   - `_return_plan_defects`: calls `apply_return` with failure marks and cleared plan defect counts.
   - `_reject_plan`: when not `staged`, calls `apply_return` with cleared plan keys and `REJECTED` mark.
   - `_return_for_split`: calls `apply_return` with split marks.
3. **Repository Context in `StageWriter`**:
   - `StageWriter` retains `self._repo` from `begin(plan, selected)` or initializes with `repo`.

## Testing Strategy
- Unit tests verifying `apply_return` passes `marks` into `write_status`.
- Unit tests verifying that `_return_premise`, `_return_blocked`, and `_return_plan_defects` execute through `apply_return`.
- Ensure all existing stage tests continue to pass.
