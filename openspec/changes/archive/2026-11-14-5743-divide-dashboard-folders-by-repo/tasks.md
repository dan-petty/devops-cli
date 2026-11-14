# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for folder annotations and repo variable
  - Verification: `$ uv run pytest tests/prometheus/test_k8s_monitoring_dashboards.py`
- [x] 1.2 Update dashboard folder annotations in kustomization files
  - Verification: `$ uv run devops ci lint`
- [x] 1.3 Add `$repo` variable and metric filters to `roadmap-service-telemetry.json`
  - Verification: `$ uv run devops grafana dashboards lint k8s/devops/dashboards/roadmap-service-telemetry.json`
- [x] 1.4 Update query test fixtures and verify promtool tests
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_dashboard_queries.py`

## 2. Documents

- [x] 2.1 Update living specifications
  - Verification: `$ uv run devops openspec check`
