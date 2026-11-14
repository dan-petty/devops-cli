# Proposal

## Why

The `plan-check` job runs its command while the required `Semantic PR title` check is still in progress, so the command reports `semantic-pr-title` as a problem. The job condition uses `always()`, which starts the job at once even with `needs: semantic-title` (#3975).

## What Changes

- The `plan-check` job uses `!cancelled()` in place of `always()`, so it waits for `semantic-title` and still runs after that job fails.
- `plan_check` polls the title check for up to 120 seconds at 5-second intervals. A check that passes in that time is no problem. A check that is still pending at the limit gives a note and no problem.
- A failed title check still gives a problem.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: The command waits for a pending title check, and a pending check at the limit is a note.

## Impact

- Code: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`
- Workflow: `.github/workflows/pr-title.yml`
- Tests: `tests/roadmap/test_roadmap_plan_check.py`, `tests/invariants/test_workflow_contracts.py`

## Feasibility

- The job already declares `needs: semantic-title`; the condition is the only change.
- `plan_check` already receives a `check_reader` callable, so a poll needs no new client.
- Verification commands: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py tests/invariants/test_workflow_contracts.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

`lewagon/wait-on-check-action` waits on a check, but it runs no command that reports the plan problems, and it adds a third-party action to the job. The command's own bounded poll reuses the `check_reader` that exists, and `!cancelled()` is the GitHub Actions status function for the condition.
