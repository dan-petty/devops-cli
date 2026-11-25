# Proposal

## Why

`devops pr monitor --timeout 1800` stops at the first failed read of the pull request, although 1,700 s of the watch remain. The agent must start it again by hand (#4838).

## What Changes

- `monitor_pr` counts a failed read as a poll with no new data, says so, and polls again.
- Three failed reads in a row end the watch with the last error.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-monitor`: A failed read does not end the watch.

## Impact

- Code: `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/github/test_pr_monitor_retry.py`

## Feasibility

- The monitor already loops on the clock and its own timeout.
- `GitHubOperationError` names the read failure.
- Verification commands: `uv run devops ci test tests/github/test_pr_monitor_retry.py tests/commands/test_pr.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The monitor is the repository's own. The change adds one try and one counter.
