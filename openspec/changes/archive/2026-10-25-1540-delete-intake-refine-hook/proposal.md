# Proposal

## Why

Issue #1540. Intake calls a refine hook directly when it places a P0 item. The Service runs intake without a repository checkout, so the hook fails every time. The cross-job rule in `devops roadmap run` already makes refine due in the same round. The direct hook in intake is redundant and causes errors.

## What Changes

- Delete `_maybe_refine_intake`, `_should_refine_on_intake`, and the intake wrapper `refine_item`.
- Delete the `refine` parameter from `apply_intake`.
- Delete `refine.refine_item` and `RefineOutcome` from `src/devops_cli/roadmap/refine.py`.
- Update `_places_critical_or_p0` in `src/devops_cli/roadmap/run.py` to check Priority P0 only and skip cards in `IntakeApplied.finished`.
- Remove `CONST_ROADMAP_CRITICAL_FIX_LABELS` from `src/devops_cli/roadmap/run.py`.
- Delete obsolete hook tests in `tests/test_roadmap_refine.py`.
- Update existing tests in `tests/test_roadmap_refine.py` to call `plan_refine` and `apply_refine`.
- Add test coverage in `tests/test_roadmap_run.py` for the three cross-job trigger cases.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/intake.py`
- `src/devops_cli/roadmap/refine.py`
- `src/devops_cli/roadmap/run.py`
- `tests/test_roadmap_run.py`
- `tests/test_roadmap_refine.py`
- `tests/test_roadmap_intake.py`

## Feasibility

- Tested offline against the in-memory roadmap store.
- `src/devops_cli/roadmap/intake.py` contains the hook.
- `src/devops_cli/roadmap/refine.py` contains `refine_item`.
- `src/devops_cli/roadmap/run.py` contains the cross-job check.

## Existing Tool Considered

The existing `devops roadmap run` cross-job orchestration covers the refinement trigger. No new tool is necessary. Deleting the redundant hook removes dead code and prevents runtime errors.
