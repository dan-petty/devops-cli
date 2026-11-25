# Proposal: #5417

## Why

The default `--timeout` of `devops pr monitor` is `300` seconds, while required checks for a code pull request routinely take more than five minutes to finish across test shards and the aggregate `Tests & Coverage` job (#5417).

## What Changes

- Define `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS = 600` in `src/devops_cli/config/defaults.py`.
- Use `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` as the default `timeout` in `monitor_pr_command` (`src/devops_cli/commands/pr.py`), `monitor_pr` (`src/devops_cli/github/pr_monitor.py`), and `plan_pr_monitor` (`src/devops_cli/github/pr_plans.py`).
- Preserve explicit `--timeout` overrides and keep dry-run plans reflecting either the 600-second default or explicit timeout.
- Regenerate generated CLI and MCP documentation and update the MCP tool listing snapshot (`pr_monitor.timeout.default = 600`).
- Add tests in `tests/commands/test_pr_dry_run.py` verifying the constant, command parameter default, default dry-run timeout, and explicit `--timeout` override.

## Capabilities

### Modified Capabilities
- `pr-monitor`: Raise the default monitor timeout to `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` (`600`).

## Impact

- `src/devops_cli/config/defaults.py`
- `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/pr_plans.py`
- `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/pr.md`, `docs/commands/gh.md`
- `tests/commands/test_pr_dry_run.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`

## Feasibility

Confirmed on `origin/main` against source:
- `src/devops_cli/commands/pr.py:868-871` hardcodes `300` as the default for `--timeout`.
- `src/devops_cli/github/pr_monitor.py:648` and `src/devops_cli/github/pr_plans.py:388` also default `timeout` to `300`.
- Updating one shared constant (`DEFAULT_PR_MONITOR_TIMEOUT_SECONDS`) in `src/devops_cli/config/defaults.py` synchronizes the CLI command, monitoring engine, dry-run planner, and generated MCP schema/docs.

## Existing Tool Considered

No open tool supplies the CLI default option value of `devops pr monitor`; the alternatives check on #5417 returned `none`. This change introduces one named constant in `defaults.py` and references it across the existing option and planner (~1k tokens, <30 min).
