# Proposal

## Why

The roadmap Service logs its round pause and GraphQL points left after each round, but Prometheus has no series for either. An alert on a paused Service or on a GraphQL budget near its floor needs Loki. #2233 adds two gauges so both values are available as Prometheus series.

## What Changes

- Add SERVICE_PAUSED_UNTIL and GITHUB_GRAPHQL_REMAINING Instrument definitions to src/devops_cli/telemetry/instruments.py
- Add emit() calls in the Service round where it already logs the pause end time and the GraphQL budget
- Add tests that capture both gauges and assert their values
- List both gauges in the metric table of docs/TELEMETRY.md
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: service-pause-gauge, graphql-remaining-gauge

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/run.py`
- Documents: `docs/TELEMETRY.md`

## Feasibility

- The issue premise is confirmed: src/devops_cli/telemetry/instruments.py defines InstrumentKind.GAUGE and emit() calls tracer.record_gauge for gauges. The archived change for #814 names devops_cli_service_paused_until_seconds and cites service_pause_until in src/devops_cli/roadmap/run.py, confirming the Service already holds the pause value.
- First checks: uv run devops ci test tests/test_telemetry_instruments.py verifies the new instruments are in INSTRUMENTS and their names follow the naming rules. uv run devops ci test tests/test_roadmap_run.py verifies the emit() calls fire with the correct values.

## Existing Tool Considered

The project's own telemetry module (src/devops_cli/telemetry/instruments.py) provides InstrumentKind.GAUGE and emit(), which the project metrics already use. No external tool is needed. The change adds two Instrument definitions and two emit() calls; it deletes no internal code.
