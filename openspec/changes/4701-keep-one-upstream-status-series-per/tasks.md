# Tasks

## 1. One upstream status series for each service and component

Kind: fix. Changes: `tests/telemetry/test_service_status.py`, `tests/fixtures/dashboard_queries/project-metrics.yaml`, `src/devops_cli/telemetry/service_status.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `k8s/monitoring/dashboards/project-metrics.json`.

- [x] 1.1 Write the tests first: a `major` summary and then a `none` summary give one service series with the last value 0, and one series for each component with the last value 0, through the OTLP fake. Add the promtool cases of the two status panels. They fail on `origin/main`.
- [x] 1.2 Remove the labels `indicator` and `status` from the emitter, and drop "and indicator" from the instrument text and `docs/TELEMETRY.md`.
- [x] 1.3 Change the two status panels to `last_over_time(devops_cli_upstream_service_status{service="<service>"}[1h])` and their descriptions.
- [x] 1.4 Verify: `uv run pytest tests/telemetry/test_service_status.py tests/prometheus/test_dashboard_queries.py tests/docs/test_docs.py` passes, and `uv run devops ci fail-to-pass --base origin/main` shows the new tests fail on the base.
