# Tasks

## 1. OTLP log export and trace correlation

- [x] 1.1 Write failing tests in `tests/test_telemetry_logging_bridge.py` and `tests/test_telemetry_collector_export.py` for OTLP log export of WARNING and ERROR records, active trace_id and span_id propagation, secret masking, and prompt/reply suppression; verify that they fail with `uv run pytest tests/test_telemetry_logging_bridge.py tests/test_telemetry_collector_export.py`
- [x] 1.2 Implement `OTelLoggingHandler` in `src/devops_cli/telemetry/logging_bridge.py`, log export to `/v1/logs` in `src/devops_cli/telemetry/tracer.py`, and error logging on command failure in `src/devops_cli/main.py`
- [x] 1.3 Run `uv run pytest tests/test_telemetry_logging_bridge.py tests/test_telemetry_collector_export.py` and verify that the tests pass

## 2. Loki derived field and devops-cli dashboard error stream

- [x] 2.1 Write failing tests in `tests/test_grafana_dashboards.py` and `tests/test_k8s_monitoring_dashboards.py` for the Loki datasource derived field targeting Tempo and the "devops-cli Error Stream" logs panel in `devops-cli.json`; verify that they fail with `uv run pytest tests/test_grafana_dashboards.py tests/test_k8s_monitoring_dashboards.py`
- [x] 2.2 Add `derivedFields` to the Loki datasource in `k8s/monitoring/grafana-values.yaml` and add the logs panel to `k8s/monitoring/dashboards/devops-cli.json`
- [x] 2.3 Run `uv run pytest tests/test_grafana_dashboards.py tests/test_k8s_monitoring_dashboards.py tests/test_telemetry_instruments.py` and verify that the tests pass
- [x] 2.4 Regenerate documentation with `uv run devops docs generate --sync-readme` and verify that `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
