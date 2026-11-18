# Tasks

## 1. Dashboard Configuration

- [x] 1.1 Add `job` and `repo` template variables and label matchers to `k8s/devops/dashboards/project-metrics.json`
  - Verification: `$ uv run pytest tests/prometheus/test_k8s_monitoring_dashboards.py`
- [x] 1.2 Update panels for instant quantiles, bar charts, CI pass rate, and matrix grouping
  - Verification: `$ uv run pytest tests/prometheus/test_dashboard_queries.py`

## 2. Test Verification

- [x] 2.1 Add promtool test cases in `tests/fixtures/dashboard_queries/project-metrics.yaml`
  - Verification: `$ uv run pytest tests/prometheus/test_dashboard_queries.py`
- [x] 2.2 Add invariant test in `tests/prometheus/test_k8s_monitoring_dashboards.py`
  - Verification: `$ uv run pytest tests/prometheus/test_k8s_monitoring_dashboards.py`
- [x] 2.3 Update config reads ceiling in `tests/gate/tree_checks/config_reads.toml`
  - Verification: `$ uv run devops ci --check --only test-tree`
