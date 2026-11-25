# Tasks

## 1. Behavior

Kind: behavior. Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/pr_plans.py`, `tests/commands/test_pr_dry_run.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/pr_plans.py`, `tests/commands/test_pr_dry_run.py`.

- [x] 1.1 Write failing tests in `tests/commands/test_pr_dry_run.py` asserting `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS == 600`, inspecting `monitor_pr_command`'s default `timeout`, verifying default `--dry-run` plans wait up to `600s`, and verifying explicit `--timeout 42` uses `42s`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py`
- [x] 1.2 Define `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS = 600` in `src/devops_cli/config/defaults.py` and wire it as default `timeout` in `monitor_pr_command`, `monitor_pr`, and `plan_pr_monitor`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py tests/commands/test_pr.py`

## 2. Documents and MCP snapshot

Kind: other. Reads: `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/pr.md`, `docs/commands/gh.md`, `tests/ai/mcp/test_mcp_tool_listing.py`. Changes: `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/pr.md`, `docs/commands/gh.md`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [x] 2.1 Regenerate docs with `uv run devops docs generate`, update the `pr_monitor` MCP tool listing snapshot, and run docs/MCP/OpenSpec checks
  - Verification: `$ uv run devops ci docs && uv run devops openspec check`
