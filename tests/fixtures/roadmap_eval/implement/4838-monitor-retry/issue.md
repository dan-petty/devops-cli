### Problem Description

`devops pr monitor <n> --timeout 1800` stops at the first GitHub read that fails. One read of the pull request that times out after 30 s ends the whole watch with exit 1, although 1,700 s of the watch remain. The agent must start the monitor again by hand.

In `src/devops_cli/github/pr_monitor.py`, `monitor_pr` calls `get_pr_monitoring_status` in its loop with no handling of a failed read. `fetch_pr_details` raises `GitHubOperationError` ("Failed to query PR #<n>: ...") when `gh` exits non-zero, and the error leaves the loop.

### Reproduction Steps

1. Open a pull request whose checks take more than one poll interval.
2. Run `devops pr monitor <n> --timeout 1800` while the GitHub API is slow (many sessions use one token).
3. One read of the pull request times out.

### Expected vs Actual Behavior

Expected: the monitor counts a failed read as a poll with no new data, says so, and polls again on the next interval until its own timeout. It stops early only when the reads fail for a bounded number of polls in a row, and then names the last error.

Actual: the monitor exits 1 at the first failed read.

### Environment Diagnostics

devops-cli at main (2026-11-11), devcontainer, gh through the rate limiter of `devops`.

### Logs, Traces, or Terminal Output

```
ℹ Monitoring PR #4794 for CI checks and review completion...
✗ Failed to query PR #4794: GitHub API command timed out after 30.0 seconds
```


Source: https://github.com/dan-petty/devops-cli/pull/4794

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
