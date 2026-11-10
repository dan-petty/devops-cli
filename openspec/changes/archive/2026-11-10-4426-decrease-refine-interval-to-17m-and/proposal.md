# Proposal: #4426

## Why

The roadmap refine job runs every 31 minutes and processes at most 3 items per run (#4426). When many items have status New, refining them to Ready takes too much time. Decreasing the interval to 17 minutes and increasing the batch limit to 7 items processes New tickets faster.

## What Changes

- Change `DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES` from 31 to 17 in `src/devops_cli/config/defaults.py`.
- Change `DEFAULT_ROADMAP_REFINE_LIMIT` from 3 to 7 in `src/devops_cli/config/defaults.py`.
- Update help strings and docstrings in `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/run.py`, and `src/devops_cli/roadmap/refine/refine.py`.
- Update documentation in `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, and `docs/commands/roadmap.md`.
- Update the limit registry in `tests/roadmap/test_roadmap_limit_classes.py`.
- Update hourly table thresholds in `tests/roadmap/test_roadmap_run_due_table.py`.
- Update helper function and test fixtures in `tests/support/roadmap_refine.py` and `tests/roadmap/refine/`.
- Update MCP tool listing snapshot in `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.
- The change modifies configuration defaults, documentation, and tests. It sets `skip_specs: true`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/refine/refine.py`.
- Tests: `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/support/roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_next_step.py`, `tests/roadmap/refine/test_roadmap_refine_selection.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/roadmap.md`.

## Feasibility

- The interval 17 is a prime number, following the project convention for hourly table rows.
- 17 minutes avoids alignment with 5-minute ticks and prevents job collisions.
- Running `uv run devops docs check` validates that all documentation reflects the new defaults.
- Running `uv run pytest tests/roadmap/` validates that all 444 roadmap tests pass.

## Existing Tool Considered

The existing `devops roadmap refine` job and its configuration defaults control the schedule and batch size. Changing the default constants requires no external tool. Cost: 0 tokens to build, 0 tokens to maintain, and under 15 minutes elapsed.
