# Proposal

## Why

At the plan-defect limit, `_Planner._stop_degenerate` adds the degenerate reply to `self._refused` but does not set `self._stopped_by_checks`. `_return_plan_defects` then adds `failure.reason`, which is the same `stage_degenerate` text, so the return comment shows the same bullet twice (#4618).

## What Changes

- `_stop_degenerate` sets `self._stopped_by_checks = True`, because the job refused and kept the reply.
- A round test holds one bullet for the degenerate reply.
- The spec text needs no change: it already says the comment gives the reason unless the checks refused the last reply.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`

## Feasibility

- The stop already appends the problem to `self._refused`.
- The return comment already reads `stopped_by_checks`.
- Verification commands: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The change sets one flag. No tool and no model call.
