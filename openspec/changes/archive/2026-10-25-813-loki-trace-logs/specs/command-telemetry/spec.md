# Spec Delta

## ADDED Requirements

### Requirement: Warning and error logs are exported via OTLP with trace correlation
When telemetry is enabled, log records of level WARNING and above SHALL be exported to the collector's `/v1/logs` endpoint carrying the active `trace_id` and `span_id`. No exported log payload SHALL contain prompt or reply text.

#### Scenario: A warning is logged during command execution
- **WHEN** a command executes an active trace span and emits a warning log
- **THEN** the log record is exported to `/v1/logs` with `severityText` `WARN`
- **AND** the log record carries the active `traceId` and `spanId`
- **AND** the payload contains no prompt or reply preview text

#### Scenario: A failed command logs an error with trace context
- **WHEN** a command fails with an unhandled exception
- **THEN** an error log is exported to `/v1/logs` with `severityText` `ERROR`
- **AND** the log record carries the active `traceId` and `spanId`

### Requirement: Loki datasource configures derived trace link to Tempo
The Grafana Loki datasource in `k8s/monitoring/grafana-values.yaml` SHALL configure a derived field targeting the Tempo datasource (`datasourceUid: tempo`) matching trace IDs in log entries.

#### Scenario: Derived field is configured in Loki datasource
- **WHEN** the Loki datasource configuration in `k8s/monitoring/grafana-values.yaml` is read
- **THEN** `jsonData.derivedFields` contains an entry targeting `datasourceUid` `tempo`
- **AND** `matcherRegex` matches trace ID values in logs

### Requirement: devops-cli dashboard includes an error stream panel
The `k8s/monitoring/dashboards/devops-cli.json` dashboard SHALL include a logs panel displaying the error and warning stream from Loki for `devops-cli`.

#### Scenario: Error stream panel is present in the dashboard
- **WHEN** the panels of `devops-cli.json` are read
- **THEN** a panel of type `logs` with title "devops-cli Error Stream" is present
- **AND** the panel targets the `loki` datasource
