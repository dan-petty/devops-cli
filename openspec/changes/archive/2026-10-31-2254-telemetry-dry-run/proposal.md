# Proposal

## Why
Issue #2254 addresses the dry-run rule (#412) for Grafana, Prometheus, Telemetry, and Dashboard commands. The rule states that a dry run makes no external requests and returns the planned requests that the real run makes. Currently, 18 commands make external network requests or print an echo-only preview during a dry run, and 3 commands make no external requests and need the `no-external-request` classification.

## What Changes
- Classify 1 Dashboard command with `@dry_run_class("request-plan")`:
  - `dashboard`
- Classify 7 Grafana commands with `@dry_run_class("request-plan")`:
  - `grafana alerts`
  - `grafana dashboards export`
  - `grafana dashboards import`
  - `grafana dashboards list`
  - `grafana dashboards sync`
  - `grafana datasources`
  - `grafana search`
- Classify 1 Grafana command with `@dry_run_class("no-external-request")`:
  - `grafana dashboards lint` (remove echo-only `--dry-run` option)
- Classify 5 Prometheus commands with `@dry_run_class("request-plan")`:
  - `prometheus analyze`
  - `prometheus query`
  - `prometheus query-range`
  - `prometheus rules`
  - `prometheus targets`
- Classify 5 Telemetry commands with `@dry_run_class("request-plan")`:
  - `telemetry connect`
  - `telemetry profile`
  - `telemetry semconv refresh`
  - `telemetry status`
  - `telemetry test`
- Classify 2 Telemetry commands with `@dry_run_class("no-external-request")`:
  - `telemetry logfire`
  - `telemetry open-ui`
- Add `--dry-run` option to commands where it is missing (`grafana alerts`, `grafana dashboards export`, `grafana datasources`, `grafana search`, `prometheus query-range`, `prometheus rules`, `prometheus targets`, `telemetry connect`).
- Provide request plan builders in `devops_cli.grafana.grafana_plans`, `devops_cli.prometheus.prometheus_plans`, and `devops_cli.telemetry.telemetry_plans`.
- In dry-run mode, make zero network, socket, or subprocess calls.
- Render planned requests with `render_request_plan`.
- Remove legacy echo-only previews (`render_dry_run_result`) with no backward-compatibility shim.
- Remove all 21 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test suites verifying classifications, planned requests, and zero external calls.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `command-dry-run-class`: Add requirements and scenarios specifying request-plan behavior and zero external calls for the 18 Grafana, Prometheus, Telemetry, and Dashboard commands, and normal execution for `grafana dashboards lint`, `telemetry logfire`, and `telemetry open-ui`.

## Impact
- Command interfaces: Grafana, Prometheus, Telemetry, and Dashboard CLI commands gain standard request planning in dry-run mode.
- Test suite: `tests/fixtures/dry_run_gaps.json` gap count decreases by 21. Tests verify zero external calls under dry run.
- Documentation: Command documentation reflects standard request-plan and no-external-request dry-run behavior.

## Feasibility
Confirmed against repository code and library sources:
- `dashboard` reads k8s, docker, telemetry, AI, and Valkey endpoints; in dry run it previews planned status inspections without contacting endpoints.
- Grafana commands interact with Grafana HTTP API endpoints via `httpx2`; `grafana dashboards lint` checks local JSON files only.
- Prometheus commands query Prometheus HTTP API endpoints via `httpx2`.
- `telemetry status`, `test`, `connect`, `profile`, and `semconv refresh` probe OTLP/Tempo, query Kubernetes services, or invoke weavers.
- `telemetry logfire` and `open-ui` read local in-memory bridge state or print configuration hints with no network calls.
- `PlannedRequest` and `render_request_plan` in `devops_cli.dry_run.requests` provide standard request planning.
- The 21 commands match the 21 entries in `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Existing Tool Considered
The change uses internal mechanisms `PlannedRequest`, `render_request_plan`, and `@dry_run_class` introduced in #741 and sub-issue 00 (#886). It removes legacy echo-only previews with no backward-compatibility shim.
