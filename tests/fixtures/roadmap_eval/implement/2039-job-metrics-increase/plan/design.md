# Design

## Context

See proposal.md - Why.
Cluster jobs run in ephemeral pods. Each pod exports its metrics once upon completion.
Prometheus `increase()` and `rate()` functions drop any series containing fewer than two samples.
Consequently, usage counters from cluster jobs never show in Prometheus dashboards.

## Goals / Non-Goals

**Goals:**
- Enable `export_created_metric: true` on the OpenTelemetry Collector `prometheus_remote_write` exporter.
- Enable `created-timestamp-zero-ingestion` on the Prometheus Server via `server.extraArgs`.
- Update `docs/TELEMETRY.md` to document the cluster job metric lifecycle and ingestion.
- Add tests verifying the collector and Prometheus configuration and verifying that two Job runs accumulate in the dashboard increase query.

**Non-Goals:**
- Change cluster jobs to long-running daemons.
- Force cluster jobs to share a single instance identifier (which causes out-of-order delta drops during concurrent runs).

## Decisions

### Decision: Export created metrics and enable zero ingestion in Prometheus
The OpenTelemetry Collector `prometheus_remote_write` exporter will set `export_created_metric: true`.
The Prometheus Server will configure `enable-feature: created-timestamp-zero-ingestion`.
- Rationale: The collector derives `_created` timestamps from `startTimeUnixNano`. Prometheus ingests a synthetic zero sample at the creation timestamp. This satisfies the two-sample requirement of `increase()` without modifying job run concurrency.
- Rejected alternative: Share `service.instance.id=devops-cli-job` across all Job pods.
  - Evidence that rejected it: `cronjob.yaml` sets `concurrencyPolicy: Allow`. Concurrent jobs send interleaved deltas, causing `deltatocumulative` to drop points with `ErrOutOfOrder` and `ErrOlderStart`.
- Rejected alternative: Push metrics to Pushgateway.
  - Evidence that rejected it: devops-cli does not run Pushgateway and uses the OpenTelemetry Collector as its unified ingestion pipeline.

## Risks / Trade-offs

- [Risk] Enabling `created-timestamp-zero-ingestion` in Prometheus requires restarting Prometheus Server during deployment.
  -> Mitigation: Prometheus runs as a managed StatefulSet/Deployment in Kubernetes with persistent volume storage; a restart preserves all existing TSDB blocks.
