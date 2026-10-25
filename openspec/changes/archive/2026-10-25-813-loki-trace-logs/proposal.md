# Proposal

## Why

Issue #813: devops-cli exports traces and metrics to the OpenTelemetry collector, but exports no logs. When a command fails, operators cannot view the corresponding log lines in Loki or navigate from a log line to its trace in Tempo.

## What Changes

- Add OTLP log export for log records of level WARNING and above to the OpenTelemetry collector `/v1/logs` endpoint, carrying the active trace ID and span ID.
- Ensure log export masks secrets and omits LLM prompt and reply text (#606).
- Configure a derived field in the Grafana Loki datasource (`k8s/monitoring/grafana-values.yaml`) to link trace IDs to the deployed Tempo datasource.
- Add a "devops-cli Error Stream" logs panel to the `devops-cli.json` dashboard querying Loki for devops-cli logs.
- The log export, dashboard panel, and derived field alter observable behavior, so the change carries a spec delta for `command-telemetry`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: Export WARNING and ERROR log records via OTLP with trace correlation, configure Loki trace link to Tempo, and add error stream panel to devops-cli dashboard.

## Impact

- `src/devops_cli/telemetry/logging_bridge.py`: Add an OTel logging handler that formats log records into OTLP JSON and attaches trace context.
- `src/devops_cli/telemetry/tracer.py`: Add log record export through the existing asynchronous background executor to `/v1/logs`.
- `src/devops_cli/main.py`: Ensure command failure logs an error with active span context.
- `k8s/monitoring/grafana-values.yaml`: Add `derivedFields` to the Loki datasource definition linking trace IDs to Tempo.
- `k8s/monitoring/dashboards/devops-cli.json`: Add the devops-cli error stream logs panel.
- `tests/test_telemetry_logging_bridge.py`, `tests/test_telemetry_collector_export.py`, `tests/test_grafana_dashboards.py`: Add offline unit tests for log export, secret and prompt scrubbing, and dashboard assertions.

## Feasibility

- The OpenTelemetry collector in `k8s/otel/values.yaml:77-81` and network policy in `k8s/logging/networkpolicy.yaml:52-61` already forward OTLP logs to Loki.
- The Tempo datasource is deployed in `k8s/monitoring/grafana-values.yaml:94-100` with UID `tempo`.
- OpenTelemetry Collector OTLP HTTP receiver handles `/v1/logs` JSON payloads with `resourceLogs`.
- `TraceCorrelationFilter` in `src/devops_cli/telemetry/logging_bridge.py` already populates active `trace_id` and `span_id`.

## Existing Tool Considered

- OpenTelemetry Python SDK and standard library `logging` cover log capture and formatting.
- Grafana Loki and Tempo datasources provide native derived field trace navigation.
- No new external package or third-party dependency is required.
