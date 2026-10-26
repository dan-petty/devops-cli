# Design

## Context

See proposal.md - Why.
Gauges sent over OTLP have stable `service.instance.id=roadmap-service`.
Gauges scraped on `/metrics` have an `instance` label with the ephemeral pod IP address.
When both paths emit the same gauge, Prometheus collects duplicate series with different labels, and dashboard panels add them together.

## Goals / Non-Goals

**Goals:**
- Send project gauges and upstream status gauges through OTLP only.
- Delete code that populates the in-memory Prometheus registry with project and upstream status gauges.
- Add an invariant test that asserts no gauge is sent through both paths.

**Non-Goals:**
- Remove the Prometheus scrape annotations or endpoint from the roadmap Service. The roadmap Service continues to expose service operational metrics (`devops_cli_service_*`) on `/metrics`.

## Decisions

### Decision: Send project metrics through OTLP and delete in-memory registry recording
Project metrics and upstream service status gauges will be emitted only over OpenTelemetry OTLP.
The functions `record_project_metrics_in_registry` and `record_service_status_in_registry` will be deleted.
- Rationale: OTLP series use `service.instance.id=roadmap-service`. A new pod writes over the old pod series in Prometheus instead of creating an orphaned series.
- Rejected alternative: Keep both paths and filter by `job="roadmap-service"` in dashboard panels.
  - Evidence that rejected it: Modifying dashboard panels hides the duplicate series rather than fixing the cause. A panel that omits the filter would still add both paths. Furthermore, old scraped series persist after pod restarts.
- Rejected alternative: Remove the Prometheus scrape from `k8s/devops/roadmap-service/deployment.yaml`.
  - Evidence that rejected it: The roadmap Service exposes operational metrics (`devops_cli_service_*`, such as queue depth and job execution metrics) on port 8000 `/metrics`. Keeping the scrape allows those operational metrics to reach Prometheus.

### Decision: Add an invariant test verifying single-path gauge emission
An invariant test will verify that no gauge instrument defined in `src/devops_cli/telemetry/instruments.py` shares a name with any gauge recorded in the in-memory registry or exposed via Prometheus scraping.
- Rationale: Prevents future regressions where a developer adds a gauge to both paths.

## Risks / Trade-offs

- [Risk] Direct scraping of project metrics from `roadmap-service:8000/metrics` will no longer include `devops_cli_project_*` metrics.
  -> Mitigation: Dashboards and alert rules read project metrics from Prometheus, which receives them from OTLP.
