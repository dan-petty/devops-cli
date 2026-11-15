# Tasks

## 1. Cadence interval change

Kind: behavior. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/run.py`.

- [x] 1.1 Update `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` to 239 minutes in `src/devops_cli/config/defaults.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_intervals.py`
- [x] 1.2 Update help text in `src/devops_cli/lang/en/help.py` and module docstrings in `src/devops_cli/roadmap/run.py`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py`

## 2. Test suite and snapshot updates

Kind: tests. Changes: `tests/config/test_roadmap_row_cadence_settings.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [x] 2.1 Update test assertions and cadence expectations for 239 minutes
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_row_cadence_settings.py tests/roadmap/test_roadmap_run_job_rows.py tests/roadmap/test_roadmap_alternatives.py`
- [x] 2.2 Update MCP tool listing snapshot and telemetry tests
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py tests/telemetry/test_telemetry_instruments.py`

## 3. Documentation, specs, and dashboard

Kind: docs. Changes: `docs/CLUSTER.md`, `docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/MCP_TOOLS.md`, `docs/commands/roadmap.md`, `docs/roadmap/alternatives.md`, `k8s/devops/dashboards/roadmap-service-telemetry.json`, `openspec/specs/roadmap-alternatives/spec.md`, `openspec/specs/roadmap-row-cadence/spec.md`.

- [x] 3.1 Regenerate documentation with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs`
- [x] 3.2 Update OpenSpec specifications and dashboard telemetry descriptions
  - Verification: `$ uv run devops openspec check`
