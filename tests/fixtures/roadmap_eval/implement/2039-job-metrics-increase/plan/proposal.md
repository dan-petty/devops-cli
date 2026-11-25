# Proposal

## Why

Issue #2039: each in-cluster Job (`k8s/devops/cronjob.yaml`) runs in a new pod that exports metrics once when it exits.
Because the series holds only one sample, `increase()` and `rate()` over it in Prometheus produce nothing.
The AI usage counters of cluster jobs never show in dashboards.

## What Changes

- Configure `export_created_metric: true` on the OpenTelemetry Collector `prometheus_remote_write` exporter in `k8s/otel/values.yaml`.
- Configure `enable-feature: created-timestamp-zero-ingestion` on the Prometheus Server in `k8s/monitoring/prometheus-values.yaml`.
- Document the cluster job counter export and ingestion behavior in `docs/TELEMETRY.md`.
- Add tests verifying the collector and Prometheus server configurations and verifying that two Job runs add up in the dashboard increase query.
- The change alters no CLI commands or capability specifications, so it sets `skip_specs: true`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/otel/values.yaml`, `k8s/monitoring/prometheus-values.yaml`.
- Documentation: `docs/TELEMETRY.md`.
- Tests: `tests/test_telemetry_instruments.py`, `tests/test_k8s_devops_runtime.py`.

## Feasibility

- The OpenTelemetry Collector uses `open-telemetry/opentelemetry-collector` Helm chart 0.175.0, whose `prometheusremotewrite` exporter supports `export_created_metric: true`.
- The Prometheus Server uses `prometheus-community/prometheus` Helm chart 29.35.0 (Prometheus v3), which supports `--enable-feature=created-timestamp-zero-ingestion`.
- With `export_created_metric: true`, the exporter includes `_created` timestamps derived from `StartTimeUnixNano`.
- With `created-timestamp-zero-ingestion`, Prometheus ingests a synthetic zero sample at the creation timestamp, giving `increase()` the required baseline sample.
- Two consecutive Job runs produce their own series with start and end timestamps, and add up in `sum(increase(...))` queries.

## Existing Tool Considered

OpenTelemetry Collector `prometheusremotewrite` exporter and Prometheus Server `created-timestamp-zero-ingestion` are upstream open tools that provide this capability. No custom compensating code is built.
