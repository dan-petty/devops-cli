# Tasks

## 1. Dashboard updates

- [x] 1.1 Update AI spend and tool call panels in devops-ai-rag.json
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py`
- [x] 1.2 Update Service row panels in roadmap-service-telemetry.json
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py`

## 2. Query tests and verification

- [x] 2.1 Add promtool test cases in devops-ai-rag.yaml and roadmap-service-telemetry.yaml
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py`
- [x] 2.2 Run full dashboard and telemetry test suites
  - Verification: `$ uv run devops ci test tests/grafana/ tests/prometheus/ tests/telemetry/`
