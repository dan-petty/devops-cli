# Proposal

## Why

The implement selection reads the plan gates from the local tree but not the CI checks of the plan pull request. A plan pull request that fails `Plan Check` or is still running stays unready, and the Service starts a runner Job for it. The Job then spends compute and model tokens on a broken or rejected plan (#3976).

## What Changes

- `_pull_reason` reads the check runs at the head of `stage.pr` through `read_check_runs`.
- A failed, cancelled, pending or unread check leaves the item out with the check's name or the unread reason.
- A settled set of checks with no failure selects the item.
- `plan_implement` takes a `check_reader` so the tests run offline.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/selection`: The selection reads the plan checks.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_selection.py`

## Feasibility

- `read_check_runs` already returns a `CheckVerdictSummary` with a bucket for each check and an unread reason.
- `PullStatus` already carries `head_sha`.
- Verification commands: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py tests/roadmap/implement/test_roadmap_implement_job.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The repository already reads check runs for the job and the plan check. The change calls that reader from the selection, and adds no library.
