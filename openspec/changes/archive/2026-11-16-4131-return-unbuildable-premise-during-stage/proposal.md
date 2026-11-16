# Proposal: #4131

## Why
When `devops roadmap stage` plans an issue whose premise cannot be built as written, the stage job creates a compensating proposal or writes returns directly to the store rather than calling `apply_return`.
Per Rule 2 of AGENTS.md and the owner decision on #4131, every return writer in the stage subsystem must call `apply_return` with evidence and record marks. Closes #4131.

## What Changes
- Extend `ReturnPlan` and `plan_return` in `src/devops_cli/roadmap/return_item.py` to accept optional `marks: Mapping[Any, str | int | None] | None`.
- Update `apply_return` in `src/devops_cli/roadmap/return_item.py` to write `marks=plan.marks` when updating status.
- Update `_return_premise`, `_return_blocked`, `_return_plan_defects`, and `_reject_plan` in `src/devops_cli/roadmap/stage/stage.py` to call `apply_return(store, plan_return(...))`.
- Update `_return_for_split` in `src/devops_cli/roadmap/stage/stage_job.py` to call `apply_return(store, plan_return(...))`.
- Remove redundant direct status writes in stage return writers.

## Capabilities
- Stage return writers uniformly call `apply_return`.
- `apply_return` supports record marks preservation across all returns.

## Impact
- All roadmap returns route through one canonical function (`apply_return`).
- Returns correctly post comments and update status to `status/new` with associated metadata marks.

## Feasibility
- Verified in code: `apply_return` in `src/devops_cli/roadmap/return_item.py` calls `store.comment` and `write_status`. Adding `marks` to `ReturnPlan` and passing them to `write_status` fulfills all stage return needs.

## Existing Tool Considered
- None found. Internal roadmap pipeline control flow. Written cost: 40,000 tokens and 2 days elapsed.
