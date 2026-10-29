# Proposal

## Why

Issue #2506: The OpenTelemetry Collector's `prometheus_remote_write` exporter uses remote write 1.0, which has no field for a created timestamp.
The `export_created_metric: true` setting and Prometheus `enable-feature: created-timestamp-zero-ingestion` do not connect.
Prometheus records no zero sample at the start of each counter series.
Because of this, `increase()` drops the first export of every series.
The comments in `k8s/otel/values.yaml` and `k8s/monitoring/prometheus-values.yaml`, and `docs/TELEMETRY.md`, state that the mechanism works, which is false.

## What Changes

- Configure `remote_write_version: 2` on the OpenTelemetry Collector `prometheus_remote_write` exporter in `k8s/otel/values.yaml`.
- Remove `export_created_metric: true` from `k8s/otel/values.yaml`.
- Update comments in `k8s/otel/values.yaml` and `k8s/monitoring/prometheus-values.yaml`.
- Update `src/devops_cli/docs/generator.py` and regenerate `docs/TELEMETRY.md`.
- Update test in `tests/test_telemetry_instruments.py` to assert `remote_write_version: 2` and the absence of `export_created_metric`.
- The change alters no CLI commands or capability specifications, so it sets `skip_specs: true`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/otel/values.yaml`, `k8s/monitoring/prometheus-values.yaml`.
- Documentation: `docs/TELEMETRY.md`, `src/devops_cli/docs/generator.py`.
- Tests: `tests/test_telemetry_instruments.py`.

## Feasibility

- The OpenTelemetry Collector Contrib `prometheusremotewrite` exporter supports remote write 2.0 via `remote_write_version: 2`. Remote write 2.0 transmits created timestamps natively in the OTLP payload.
- Prometheus v3 (`enable-feature: created-timestamp-zero-ingestion`) ingests zero-value samples at created timestamps received via remote write 2.0.
- Confirmed against Prometheus and OpenTelemetry Collector documentation and live configuration in `k8s/otel/values.yaml` and `k8s/monitoring/prometheus-values.yaml`.

## Existing Tool Considered

The OpenTelemetry Collector `prometheusremotewrite` exporter and Prometheus Server `created-timestamp-zero-ingestion` are upstream open tools that provide this capability.
Using remote write 2.0 replaces the obsolete `export_created_metric: true` setting from remote write 1.0. No custom compensating code is built.
