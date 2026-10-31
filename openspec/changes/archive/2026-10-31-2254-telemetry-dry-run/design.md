# Design

## Context
See `proposal.md` for motivation.
Devops-cli enforces the owner's dry-run rule (#412) via `@dry_run_class`.
The `dashboard` command aggregates status from Kubernetes, Docker, Telemetry, AI, and Valkey. Under dry run, it must not execute these probes, but return an ordered plan of planned status queries.
The 7 Grafana commands interact with the Grafana HTTP API via `httpx2`. `grafana dashboards lint` checks local JSON files only and makes zero external requests.
The 5 Prometheus commands interact with the Prometheus HTTP API via `httpx2`.
The 5 Telemetry commands (`status`, `connect`, `test`, `profile`, `semconv refresh`) probe network endpoints, invoke subprocesses, or query cluster services. `telemetry logfire` and `open-ui` read local in-memory bridge state or print configuration links with zero external requests.

In dry-run mode, commands that make external requests must not open sockets, start child processes, or issue network requests. Instead, they must generate an ordered list of `PlannedRequest` items and render them with `render_request_plan`.

## Goals / Non-Goals

**Goals:**
- Implement plan generation functions in:
  - `devops_cli.telemetry.telemetry_plans` (for dashboard and telemetry commands)
  - `devops_cli.grafana.grafana_plans` (for grafana commands)
  - `devops_cli.prometheus.prometheus_plans` (for prometheus commands)
- Decorate `dashboard` with `@dry_run_class("request-plan")`.
- Decorate 7 Grafana commands with `@dry_run_class("request-plan")` and `grafana dashboards lint` with `@dry_run_class("no-external-request")`.
- Decorate 5 Prometheus commands with `@dry_run_class("request-plan")`.
- Decorate 5 Telemetry commands with `@dry_run_class("request-plan")` and 2 Telemetry commands (`logfire`, `open-ui`) with `@dry_run_class("no-external-request")`.
- Add `--dry-run` option where missing.
- Ensure each command respects `--dry-run` and global `devops --dry-run <cmd>`.
- In dry-run mode, make zero network, socket, or external process calls.
- Render tabular request plans with `render_request_plan`.
- Remove legacy echo-only previews (`render_dry_run_result`) with no shim.
- Remove all 21 commands from `tests/fixtures/dry_run_gaps.json`.

**Non-Goals:**
- Modifying behavior in non-dry-run mode.
- Adding backwards-compatibility shims for legacy echo-only preview output.

## Decisions

### 1. Dedicated plan modules (`telemetry_plans.py`, `grafana_plans.py`, `prometheus_plans.py`)
- **Decision**: Put plan builders in `src/devops_cli/telemetry/telemetry_plans.py`, `src/devops_cli/grafana/grafana_plans.py`, and `src/devops_cli/prometheus/prometheus_plans.py`.
- **Rationale**: Keeps CLI callback functions clean, adheres to project cyclomatic complexity limits (<=10), and avoids cyclic imports between command modules and clients.
- **Alternatives considered**:
  - *Inline plan generation directly in CLI callback bodies*: Rejected because it increases command cyclomatic complexity beyond project limits and hinders unit testing.

### 2. Request Representation
- **Decision**:
  - HTTP requests (Grafana, Prometheus, Tempo, OTLP): `PlannedRequest(method="GET"|"POST", target=url)`.
  - Subprocess commands (weaver, kubectl): `PlannedRequest(method="subcommand"|"kubectl", target=..., argv=...)`.
  - Service probes: `PlannedRequest(method="PROBE"|"OTLP", target=endpoint)`.
- **Rationale**: Standardizes request output across subsystems using established `PlannedRequest` patterns.

## Risks / Trade-offs
- [Cyclomatic complexity in command functions] → Keep dry-run handling concise and delegate plan creation to dedicated helper functions to stay within cyclomatic complexity limits (<=10).
- [Socket leakage in tests] → Use socket and HTTP client monkeypatch guards to guarantee zero external calls are made during dry runs.
