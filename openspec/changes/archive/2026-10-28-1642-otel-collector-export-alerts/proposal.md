# Proposal

## Why

Issue #1642: no alert rule covers the export failures of the OpenTelemetry collector. From the deploy of Tempo until its pod ran, the collector dropped every span that it received, and no alert fired. The failure showed only on the OpenTelemetry Collector dashboard and in the collector's log. A loss of logs or of remote-written metrics through the collector can also last with no alert.

## What Changes

- A new alert group, `otel-collector`, in `k8s/monitoring/prometheus-values.yaml`, with two rules. Both wait 15 minutes, have the severity `warning`, and have no `node` label:
  - `OtelCollectorExportFailing` fires for each exporter whose `send_failed` count of spans, metric points or log records increased in the last 15 minutes, and also in the 15 minutes before. It names the exporter and the signal in `data_type` (`traces`, `metrics` or `logs`), as the queue gauges do.
  - `OtelCollectorExportQueueFull` fires for each exporter queue that stays at 90% or more of its capacity.
- `tests/fixtures/metrics/otel-collector.yaml` is captured again from the deployed collector (contrib 0.161.0, chart 0.175.0). Its `from_source` holds the three `send_failed` families, which the collector does not print until a send fails.
- `tests/test_k8s_monitoring_alerting.py` pins the two rules, checks that each series they select is a family of the capture, and runs `promtool test rules` on `tests/fixtures/prometheus_rules/otel_collector_tests.yaml`. The promtool test of the roadmap Service groups now runs over each group that has unit tests.
- The Alerting table in `k8s/README.md` lists both alerts.
- An alert rule is behavior that a person sees, so the change carries a spec delta: the new capability `otel-collector-alerts`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `otel-collector-alerts`: the alerts on the export health of the OpenTelemetry collector.

## Impact

- `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`.
- `tests/test_k8s_monitoring_alerting.py`, `tests/fixtures/metrics/otel-collector.yaml`, `tests/fixtures/prometheus_rules/otel_collector_tests.yaml`.
- Alertmanager has no receiver until the webhook Secret exists, so the alerts show in Grafana's Alerting view and notify no one until then.

## Feasibility

- The live collector, read through the Kubernetes API proxy to its pod on 2026-10-28 (image `otel/opentelemetry-collector-contrib:0.161.0`, 3.5 hours up), prints `otelcol_exporter_queue_size` and `otelcol_exporter_queue_capacity` with the labels `data_type` and `exporter`, for the exporters `otlp_grpc/tempo` (traces), `prometheus_remote_write` (metrics) and `otlp_http/loki` (logs). Its counters have no `_total` suffix (`otelcol_exporter_sent_spans`).
- It printed no `send_failed` family, because no send failed since its start, and the OpenTelemetry SDK prints a counter only from its first event. The Prometheus server holds `otelcol_exporter_send_failed_spans` (exporter `otlp_grpc/tempo`) and `otelcol_exporter_send_failed_metric_points` (exporter `prometheus_remote_write`) from earlier failures (`/api/v1/label/__name__/values` and `/api/v1/series`, 14 days).
- No capture shows `otelcol_exporter_send_failed_log_records`. The collector's documentation at v0.161.0 (`exporter/exporterhelper/documentation.md`) declares it as a monotonic sum, and `obs_report_sender.go` at v0.161.0 (lines 67 to 101) adds a failed send to it with the attributes of the sent counter. The collector runs at the default telemetry level (its `service.telemetry` sets no level), so the `error.type` and `error.permanent` attributes are not kept. The family therefore has the labels of `otelcol_exporter_sent_log_records`: `exporter`, `server_address`, `server_port` and `url_path`.
- `promtool` (on PATH, as the existing rule tests use it) accepts the rules, and `promtool test rules` passes the new unit tests. With the threshold of the queue rule changed to 0.96, the unit test fails.

## Existing Tool Considered

Prometheus alerting rules and `promtool test rules`, which the repository already uses for the roadmap Service, cover the need. The collector's own exporter metrics are the data. Nothing new is built, and no code is deleted.
