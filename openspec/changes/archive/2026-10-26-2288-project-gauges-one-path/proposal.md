# Proposal

## Why

Issue #2288: project gauges reach Prometheus through two paths: the pod scrape on port 8000 and OTLP export.
A dashboard panel that uses `last_over_time` adds both series together and shows double the real values.
A restarted pod writes a new scraped series with a new pod IP address, so old and new pods add together.

## What Changes

- Delete `record_project_metrics_in_registry` and its helpers from `src/devops_cli/github/metrics.py`.
- Delete `record_service_status_in_registry` from `src/devops_cli/telemetry/service_status.py`.
- Stop recording project metrics and service status in the in-memory Prometheus registry in `src/devops_cli/roadmap/run.py` and `src/devops_cli/commands/gh.py`.
- Keep the Prometheus scrape endpoint and pod annotations on the roadmap Service for service operational metrics (`devops_cli_service_*`).
- Send project gauges and upstream status gauges through OTLP only.
- Add an invariant test that fails when two paths send the same gauge name.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-metrics-dashboard`: adds the requirement that gauges reach Prometheus through one path only.

## Impact

- Code: `src/devops_cli/github/metrics.py`, `src/devops_cli/telemetry/service_status.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/gh.py`.
- Tests: `tests/test_github_metrics.py`, `tests/test_roadmap_run.py`, `tests/test_telemetry_instruments.py`.

## Feasibility

- The premise holds. `record_project_metrics_in_registry` records all 13 project gauges into `GLOBAL_METRICS`.
- `record_service_status_in_registry` records the two upstream status gauges into `GLOBAL_METRICS`.
- At the same time, `emit_project_metrics_telemetry` and `emit_service_status_telemetry` emit the same gauges over OTLP.
- `k8s/devops/roadmap-service/deployment.yaml` sets `prometheus.io/scrape: "true"`, so Prometheus scrapes `GLOBAL_METRICS`.
- The scrape path produces `job="kubernetes-pods"` with ephemeral pod addresses.
- The OTLP path produces `job="roadmap-service"` with stable `service.instance.id=roadmap-service`.
- Queries using `sum by (...) (last_over_time(...))` sum both paths and all pod addresses in the time range.
- Removing `record_project_metrics_in_registry` and `record_service_status_in_registry` ensures each project gauge reaches Prometheus through OTLP only.
- The roadmap Service keeps port 8000 scraping for its operational metrics (`devops_cli_service_*`).
- The OTLP series uses `service.instance.id=roadmap-service`, so a new pod replaces the series of the old pod.

## Existing Tool Considered

OpenTelemetry OTLP export and Prometheus scraping are the existing telemetry mechanisms.
This change uses OpenTelemetry OTLP export as the single path for project gauges.
This change deletes obsolete internal functions: `record_project_metrics_in_registry`, `_record_releases_and_traffic`, `_record_releases_breakdown`, `_record_workflow_and_item_metrics`, and `record_service_status_in_registry`.
