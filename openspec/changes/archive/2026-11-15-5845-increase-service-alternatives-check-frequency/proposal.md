# Proposal: #5845

## Why

The roadmap service alternatives check runs every 719 minutes (about twelve hours). A full pass of open items takes about four days. Increasing the check frequency by three times lets the service complete a pass of open items in about one and a half days.

## What Changes

- Change `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` in `src/devops_cli/config/defaults.py` from 719 to 239 minutes (about four hours, prime per invariant #2965).
- Update help text, docstrings, and documentation references (`docs/CLUSTER.md`, `docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/MCP_TOOLS.md`, `docs/roadmap/alternatives.md`).
- Update Grafana dashboard panel descriptions and telemetry test expectations.
- Update test cases in `tests/roadmap/test_roadmap_intervals.py`, `tests/config/test_roadmap_row_cadence_settings.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_alternatives.py`, and the MCP tool listing snapshot.
- Update the OpenSpec specifications for `roadmap-alternatives` and `roadmap-row-cadence`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: The alternatives row runs six times a day on a 239-minute interval.
- `roadmap-row-cadence`: The default cadence interval for `roadmap.alternatives.interval_minutes` is 239 minutes.

## Impact

- Runtime code: `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/run.py`.
- Documentation: `docs/CLUSTER.md`, `docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/MCP_TOOLS.md`, `docs/roadmap/alternatives.md`.
- Dashboards: `k8s/devops/dashboards/roadmap-service-telemetry.json`.
- Tests: `tests/roadmap/test_roadmap_intervals.py`, `tests/config/test_roadmap_row_cadence_settings.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`, `tests/telemetry/test_telemetry_instruments.py`.

## Feasibility

- The setting is defined in `src/devops_cli/config/defaults.py` and referenced across the cadence settings loader and row scheduler.
- Invariant #2965 requires interval values to be prime numbers not divisible by 5. 239 is prime and satisfies this invariant.
- All unit and invariant test suites pass with the 239-minute value.

## Existing Tool Considered

Built-in roadmap alternatives runner and cadence configuration. Cost to implement: about 3k tokens and 0.5 hours.
