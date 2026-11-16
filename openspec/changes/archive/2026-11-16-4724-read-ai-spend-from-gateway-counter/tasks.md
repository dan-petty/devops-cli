# Tasks

## 1. Behavior

- [x] 1.1 Update AI spend dashboard panels in `k8s/devops/dashboards/ai-spend.json`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py`
- [x] 1.2 Update Grafana and telemetry instrument assertions
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/telemetry/test_telemetry_instruments.py`
- [x] 1.3 Add promtool query test cases in `tests/fixtures/dashboard_queries/ai-spend.yaml`
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py`

## 2. Documents

- [x] 2.1 Update spec deltas and OpenSpec change
  - Verification: `$ uv run devops ci openspec`
