# Design

## Context

See proposal.md - Why.
Cluster jobs and cli runs export counter metrics.
Remote write 1.0 does not transmit created timestamps in its sample payload.
The `export_created_metric: true` flag exports a separate `_created` series that Prometheus's `created-timestamp-zero-ingestion` feature does not consume.
Prometheus requires remote write 2.0 to ingest zero samples from created timestamps natively.

## Goals / Non-Goals

**Goals:**
- Configure `remote_write_version: 2` on the OpenTelemetry Collector `prometheus_remote_write` exporter.
- Remove obsolete `export_created_metric: true`.
- Update comments in `k8s/otel/values.yaml` and `k8s/monitoring/prometheus-values.yaml`.
- Update telemetry documentation in `src/devops_cli/docs/generator.py` and regenerate `docs/TELEMETRY.md`.
- Add test coverage for the remote write 2.0 configuration.

**Non-Goals:**
- Modify Prometheus scrape configurations or alert rules.
- Change metric instrument definitions.

## Decisions

### Decision: Use remote write 2.0 for prometheus_remote_write exporter
The OpenTelemetry Collector `prometheus_remote_write` exporter sets `remote_write_version: 2` and removes `export_created_metric`.
- Rationale: Remote write 2.0 uses the OTLP data model. It carries the created timestamp natively in each cumulative metric, allowing Prometheus `created-timestamp-zero-ingestion` to record a synthetic zero sample.
- Rejected alternative: Keep remote write 1.0 and `export_created_metric: true`.
  - Evidence that rejected it: `export_created_metric` exports a separate `_created` metric, which Prometheus's zero-ingestion feature does not consume. Single-export series still lack zero samples in Prometheus.
- Rejected alternative: Remove zero-ingestion and document that `increase()` drops single-sample series.
  - Evidence that rejected it: Drops the zero-sample benefit for dashboards and PromQL queries counting job completions.

## Risks / Trade-offs

- [Risk] Remote write 2.0 format compatibility.
  -> Mitigation: Prometheus v3 running in the cluster already enables remote write receiver and created-timestamp zero ingestion, which natively support remote write 2.0 payloads.
