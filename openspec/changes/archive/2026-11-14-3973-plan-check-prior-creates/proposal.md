# Proposal

## Why

`_size_problems` in `src/devops_cli/roadmap/plan_check.py` reports `group-no-files` for a group that changes a file that an earlier group of the same plan creates. The file is not in the tree yet, so `measure_groups` counts no packed file, and the group's own `creates` does not repeat the path. A valid plan is refused (#3973).

## What Changes

- `_size_problems` accumulates the paths that each group creates, in order. A changed path that an earlier group creates counts as present.
- A test holds a later group that changes the file of an earlier group.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: A group that changes a file that an earlier group of the same plan creates is not reported.

## Impact

- Code: `src/devops_cli/roadmap/plan_check.py`
- Tests: `tests/roadmap/test_roadmap_plan_check.py`

## Feasibility

- `_size_problems` already walks the groups in order and holds each group's `changes` and `creates`.
- Verification commands: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py tests/roadmap/stage/test_roadmap_stage_plan_check.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

No outside tool applies. The fix adds one set to an existing loop.
