# Tasks

## 1. Service JSON lines carry the span ids, and Grafana links them

Kind: behavior. Reads: `src/devops_cli/server/json_logs.py`, `src/devops_cli/telemetry/logging_bridge.py`, `k8s/monitoring/grafana-values.yaml`. Changes: `src/devops_cli/server/json_logs.py`, `k8s/monitoring/grafana-values.yaml`, `tests/server/test_service_log_trace_ids.py` (new).

- [x] 1.1 Write tests: a line in a span of the own tracer and a line in an OpenTelemetry span carry the span's ids, a line with no span has neither key, and the Loki derived fields find the trace id in a JSON line and in `trace_id` structured metadata
  - Verification: `$ uv run devops ci test tests/server/test_service_log_trace_ids.py` fails on the base
- [x] 1.2 Put `TraceCorrelationFilter` on the `json` handler of `service_log_config`, and write the non-empty `trace_id` and `span_id` in `JsonLogFormatter`
  - Verification: `$ uv run devops ci test tests/server/test_service_log_trace_ids.py tests/server/test_server.py tests/server/test_server_service.py`
- [x] 1.3 Change the regex derived field of the Loki data source to match the JSON key form, and add a label derived field for `trace_id` structured metadata
  - Verification: `$ uv run devops ci test tests/server/test_service_log_trace_ids.py tests/commands/k8s/test_k8s_tempo.py`

## Workflow follow-up

- Pending a person: after the release, check that at least 90 % of the Service job lines carry a `trace_id` with the Loki query in the pull request comment.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
