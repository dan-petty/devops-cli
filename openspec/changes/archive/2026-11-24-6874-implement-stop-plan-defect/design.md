# Design

## Decisions

### 1. Assign FailureClass.PLAN_DEFECT to test-first stops
Set `klass=FailureClass.PLAN_DEFECT` on `_Failure` at:
- `implement_stop_no_test_file`
- `implement_stop_base_passes`
- `implement_stop_base_errors`
in `src/devops_cli/roadmap/implement/implement_step.py`.

### 2. Match test-first messages in classify_failure
Add regex patterns in `src/devops_cli/roadmap/failure.py` for:
- `MESSAGES.roadmap.implement_stop_no_test_file`
- `MESSAGES.roadmap.implement_stop_base_passes`
- `MESSAGES.roadmap.implement_stop_base_errors`
Include them in `_PLAN` so text fallback classification returns `FailureClass.PLAN_DEFECT`.

### 3. Allow repair rounds for replay failures carrying repair paths
In `_repair_ask` in `implement_step.py`, only skip repair rounds for `PLAN_DEFECT` if `failure.repair_paths is None`.
Replay failures for `BaseStatus.PASSES` and `BaseStatus.ERRORS` provide test file paths in `repair_paths`.
They must continue to get their repair round to fix test assertions before the step stops.

## Rejected alternatives

### Keep ci_infra class
Rejected. `ci_infra` represents a CI outage. It triggers a retry action that cannot fix a defective test or plan.

### Create a new failure class
Rejected. `plan_defect` already exists and correctly describes a defect in the plan or test specification.
A new class adds taxonomy complexity without extra benefit.
