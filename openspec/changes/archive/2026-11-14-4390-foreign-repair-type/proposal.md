# Proposal

## Why

A repair turn of the implement step can change a file that the step did not change. `_extra_turn` builds `_Failure(foreign)` with no class, so the classifier reads the path text and the check name. The same cause becomes `lint` in one repository and `ci_infra` in another, and a retry repeats the stop (#4390).

## What Changes

- The foreign-change stop carries `FailureClass.OUTSIDE_PLAN`.
- The class no longer depends on the path text or the check name.
- The repair-turn test asserts the class.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-failure-taxonomy`: The foreign-change stop carries `outside_plan`.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_step_repair.py`

## Feasibility

- `_Failure` already holds a `klass`.
- `FailureClass.OUTSIDE_PLAN` maps to `FailureAction.WAIT`, which is the right action.
- Verification commands: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_repair.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The classifier already exists and reads an untyped stop. The change types the stop, so no model call and no new tool.
