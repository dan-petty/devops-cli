# Proposal: #3968

## Why

The Service opens a draft plan pull request for each staged item, and the default branch moves after that. A moved module or a new task rule makes an older plan invalid, and GitHub re-runs no check without a push. The draft stays open until a person finds the drift at review or implement time. The Service detects it now, labels the pull request, and comments each problem, with no model call.

## What Changes

- `src/devops_cli/roadmap/stage/plan_drift.py` adds the row: it lists the open pull requests, keeps the plans of the default branch, fetches each head, reads the change folder, and runs `folder_problems` against the default branch tree.
- `src/devops_cli/roadmap/run.py` registers `plan_drift` in `STATUS_LANE_ROWS` before `stage_ready`, with `needs_clone=True` and a first run; `src/devops_cli/config/defaults.py` sets `DEFAULT_ROADMAP_PLAN_DRIFT_INTERVAL_MINUTES` to 37.
- A failing plan gets the label `plan/needs-fix` and one marked comment, which a later round updates in place; a passing plan loses the label.
- `stage_ready` already refuses a green draft that holds the label, so readiness waits.
- Tests cover the comment, the label changes, the delivery exclusion, and a path that the default branch moved.

## Capabilities

- `roadmap-plan-drift`

## Impact

The status lane reads each open plan every 37 minutes: one fetch and one set of gates per plan, with no model call. The row only writes a label and one comment.

## Feasibility

Checked on `origin/main` 34551501c, 2026-11-14. `store.open_pulls()` lists the open pulls, `plan_check.read_pull`, `is_plan` and `folder_problems` hold the plan rules, and `stage_ready` already refuses the label. `plan_drift` runs in the status lane with a clone. `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_drift.py tests/roadmap/test_roadmap_run_due_table.py` passes.

## Existing Tool Considered

No open tool detects plan drift, labels the pull request and comments each problem. The change reuses the plan-check gates and the Service rows; it builds the row only, about 25,000 tokens to build and keep, and 3 hours.
