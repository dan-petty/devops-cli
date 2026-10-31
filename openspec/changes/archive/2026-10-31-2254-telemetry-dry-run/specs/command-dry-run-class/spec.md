# command-dry-run-class Specification

## ADDED Requirements

### Requirement: dashboard-request-plans
The `dashboard` command SHALL carry the `request-plan` dry-run class. Under dry run, the command makes zero external requests and returns an ordered plan of planned status inspection queries across Kubernetes, Docker, Telemetry, AI, and Valkey.

#### Scenario: Dry run on dashboard
- **WHEN** user executes `devops dashboard --dry-run`
- **THEN** no external requests are made and the planned status queries are printed

### Requirement: grafana-request-plans
Seven commands in `grafana` SHALL carry the `request-plan` dry-run class:
`grafana alerts`, `grafana dashboards export`, `grafana dashboards import`, `grafana dashboards list`, `grafana dashboards sync`, `grafana datasources`, and `grafana search`.
Under dry run, each command makes zero HTTP or network requests and outputs its planned requests.

#### Scenario: Dry run on grafana alerts
- **WHEN** user executes `devops grafana alerts --dry-run`
- **THEN** no external request is made and the planned alert rules query is printed

#### Scenario: Dry run on grafana dashboards list
- **WHEN** user executes `devops grafana dashboards list --dry-run`
- **THEN** no external request is made and the planned dashboard search request is printed

#### Scenario: Dry run on grafana datasources
- **WHEN** user executes `devops grafana datasources --dry-run`
- **THEN** no external request is made and the planned datasources query is printed

### Requirement: grafana-no-external-request
The `grafana dashboards lint` command SHALL carry the `no-external-request` dry-run class. Under dry run, the command executes normally and inspects local JSON files.

#### Scenario: Dry run on grafana dashboards lint
- **WHEN** user executes `devops --dry-run grafana dashboards lint tests/fixtures/`
- **THEN** the command executes locally and lints dashboard files without making external requests

### Requirement: prometheus-request-plans
Five commands in `prometheus` SHALL carry the `request-plan` dry-run class:
`prometheus analyze`, `prometheus query`, `prometheus query-range`, `prometheus rules`, and `prometheus targets`.
Under dry run, each command makes zero HTTP or network requests and outputs its planned requests.

#### Scenario: Dry run on prometheus query
- **WHEN** user executes `devops prometheus query "up" --dry-run`
- **THEN** no external request is made and the planned PromQL query request is printed

#### Scenario: Dry run on prometheus rules
- **WHEN** user executes `devops prometheus rules --dry-run`
- **THEN** no external request is made and the planned rules request is printed

#### Scenario: Dry run on prometheus targets
- **WHEN** user executes `devops prometheus targets --dry-run`
- **THEN** no external request is made and the planned targets request is printed

### Requirement: telemetry-request-plans
Five commands in `telemetry` SHALL carry the `request-plan` dry-run class:
`telemetry connect`, `telemetry profile`, `telemetry semconv refresh`, `telemetry status`, and `telemetry test`.
Under dry run, each command makes zero external requests or subprocess calls and outputs its planned requests.

#### Scenario: Dry run on telemetry status
- **WHEN** user executes `devops telemetry status --dry-run`
- **THEN** no external request is made and the planned collector connection test is printed

#### Scenario: Dry run on telemetry test
- **WHEN** user executes `devops telemetry test --dry-run`
- **THEN** no external request is made and the planned test trace export is printed

#### Scenario: Dry run on telemetry semconv refresh
- **WHEN** user executes `devops telemetry semconv refresh --commit main --dry-run`
- **THEN** no external request is made and the planned weaver command is printed

### Requirement: telemetry-no-external-request
Two commands in `telemetry` SHALL carry the `no-external-request` dry-run class:
`telemetry logfire` and `telemetry open-ui`. Under dry run, each command executes normally without making external requests.

#### Scenario: Dry run on telemetry logfire
- **WHEN** user executes `devops --dry-run telemetry logfire`
- **THEN** the command executes locally and displays logfire bridge status

#### Scenario: Dry run on telemetry open-ui
- **WHEN** user executes `devops --dry-run telemetry open-ui`
- **THEN** the command executes locally and displays the tempo URL
