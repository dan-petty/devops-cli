# Proposal

## Why

The `plan-check` job of `.github/workflows/pr-title.yml` starts from the plan title in the event payload. The implement job then edits the live title and body to the delivery form, and the running job reads the delivery form and fails (#3829, run 42259947563).

## What Changes

- The `plan-check` job declares a concurrency group keyed to the pull request number with `cancel-in-progress: true`. The edit event cancels the run that read the plan form, and the later run skips the job through its event-title condition.
- A workflow contract test holds the group and the cancellation.
- The command keeps one live title source and no content test.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Workflow: `.github/workflows/pr-title.yml`
- Tests: `tests/invariants/test_workflow_contracts.py`

## Feasibility

- GitHub Actions gives `concurrency` and `cancel-in-progress` at the job level.
- The job condition already reads the event title, so the later event skips the job.
- Verification commands: `uv run devops ci test tests/invariants/test_workflow_contracts.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

GitHub Actions `concurrency` covers the race, and the workflow keeps no second title source. No command change and no new dependency.
