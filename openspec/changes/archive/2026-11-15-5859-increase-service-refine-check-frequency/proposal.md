# Proposal: #5859

## Why

The roadmap service refine check runs every 17 minutes. Increasing the refine frequency by about three times lets the service advance candidates from New to Ready status more quickly and reduces backlog processing latency.

## What Changes

- Change `DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES` in `src/devops_cli/config/defaults.py` from 17 to 7 minutes (prime per invariant #2965).
- Update help text in `src/devops_cli/lang/en/help.py` and docstrings in `src/devops_cli/roadmap/run.py`.
- Update test cases in `tests/roadmap/test_roadmap_intervals.py`, `tests/config/test_roadmap_row_cadence_settings.py`, `tests/roadmap/test_roadmap_run_due_table.py`, and the MCP tool listing snapshot.
- Update the OpenSpec specification for `roadmap-row-cadence`.
- Regenerate documentation (`docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/roadmap.md`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-row-cadence`: The default cadence interval for `roadmap.refine.interval_minutes` is 7 minutes.

## Impact

- Runtime code: `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/run.py`.
- Documentation: `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/roadmap.md`.
- Tests: `tests/roadmap/test_roadmap_intervals.py`, `tests/config/test_roadmap_row_cadence_settings.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

## Feasibility

- The setting is defined in `src/devops_cli/config/defaults.py` and loaded across the cadence settings loader and row scheduler.
- Invariant #2965 requires interval values to be prime numbers not divisible by 5. 7 is prime and satisfies this invariant.
- All unit and invariant test suites pass with the 7-minute value.

## Existing Tool Considered

Built-in roadmap refine runner and cadence configuration. Cost to implement: about 3k tokens and 0.5 hours.
