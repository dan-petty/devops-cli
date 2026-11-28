# Proposal

## Why

`devops pr monitor` and `devops pr wait` read the pull request, its checks, its review threads, its changed files and its reviews again each interval while a check runs (`src/devops_cli/github/pr_monitor.py`, `monitor_pr`). `gh pr checks --watch` already waits until no check is pending (#7509, a part of #7499).

## What Changes

- While the verdict holds a running check, the monitor waits with `gh pr checks <n> --repo <repo> --watch --interval <interval>` in a process whose time limit is the time left. It reads the pull request again at once when gh ends, and judges every blocker as before.
- A watch past the timeout gives the timeout result, exit 3.
- The monitor waits `interval` itself only when the head reports no check yet, when a check still runs after a watch, and while a Copilot review is active or the settle time has not passed. gh has no watch of reviews.
- `run_gh` names its timeout exit code `CONST_GH_TIMEOUT_EXIT_CODE` (124).
- The dry-run plan of `pr monitor` lists the watch. The help of `--interval` and of the command say how the monitor waits.
- The monitor keeps the settle time of the Copilot review, the map of exit codes, and the three failed reads of #4838. The help and the dry run change, so the change carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-monitor`: the monitor waits for running checks with `gh pr checks --watch`.

## Impact

- Code: `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/pr_plans.py`, `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/github/test_pr_check_verdict.py`, `tests/commands/test_pr.py`, `tests/commands/test_pr_dry_run.py`, the snapshot of `tests/ai/mcp/test_mcp_tool_listing.py`.
- Documents: the generated command reference.

The change fits one pull request. #7510 and #7512 do the rest of #7499.

## Feasibility

- gh v2.106.0 is in the devcontainer (`/usr/local/bin/gh`, build info `github.com/cli/cli/v2 v2.106.0`).
- `pkg/cmd/pr/checks/checks.go` at v2.106.0: `--watch` reads the checks, prints them, sleeps `--interval` seconds (default 10) and reads again while one is pending. It ends with exit 0 when none is pending and none failed, and 1 when one failed. Exit 8 (pending) cannot follow a watch, because the loop ends only when no check is pending or, with `--fail-fast`, at a failure. A head with no check returns `no checks reported on the '<branch>' branch` before the loop, so gh exits 1 at once. `--watch` refuses `--json`, and `--fail-fast` and `--interval` need `--watch`. gh has no time limit of its own.
- `pkg/iostreams/iostreams.go`: with no terminal, gh prints no screen codes. It prints one line `Refreshing checks status every <n> seconds` and the table on each read (`pkg/cmd/pr/checks/output.go`).
- `run_gh` stops a command at its `timeout` and answers exit 124 (`_execute_gh_single_attempt`).

## Existing Tool Considered

GitHub CLI (https://github.com/cli/cli), MIT, v2.106.0: `gh pr checks --watch --interval`. It waits for the checks; it holds no project policy and no watch of reviews, so the monitor keeps its Copilot settle time, its exit-code map and its read-failure rule. The deleted internal code is the read of the checks and of the whole verdict each interval while a check runs.
