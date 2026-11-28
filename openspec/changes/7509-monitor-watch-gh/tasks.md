# Tasks

## 1. Wait for running checks with gh pr checks --watch

Kind: behavior.

Reads: `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/rate_limiter.py`.

Changes: `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/pr_plans.py`, `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/help.py`, `tests/github/test_pr_check_verdict.py`, `tests/commands/test_pr.py`, `tests/commands/test_pr_dry_run.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [x] 1.1 Write the tests of `watch_pr_checks` (the gh arguments, the time limit, and each end: exit 0, a failed check, exit 8, a gh error, `no checks reported`, the time limit), of the monitor (one watch for a running check, exit 3 at the time limit, one interval for a head with no check, one interval before a second watch) and of the monitor plan, and watch them fail.
  - Verification: `$ uv run devops ci test tests/github/test_pr_check_verdict.py tests/commands/test_pr.py tests/commands/test_pr_dry_run.py`
- [x] 1.2 Add `watch_pr_checks`, wait with it in `monitor_pr` in place of the read of the verdict each interval while a check runs, name `CONST_GH_TIMEOUT_EXIT_CODE`, and add the watch to the monitor plan and the help.
  - Verification: `$ uv run devops ci test tests/github/test_pr_check_verdict.py tests/commands/test_pr.py tests/commands/test_pr_dry_run.py tests/github/test_pr_monitor_retry.py tests/github/test_pr_monitor_empty_checks.py tests/ai/mcp/test_mcp_tool_listing.py`

## 2. Documents

Kind: other.

Changes: `docs/commands/pr.md`, `docs/commands/gh.md`, `docs/MCP_TOOLS.md`.

- [x] 2.1 Regenerate the command reference for the new help of `devops pr monitor`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #7510: read the checks of the roadmap rows with `gh pr checks`, and delete `latest_run_of_each_check`.
- #7512: wait for and merge the template pull request of `devops repos onboard` with `gh`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
