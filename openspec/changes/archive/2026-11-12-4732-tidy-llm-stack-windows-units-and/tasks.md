# Tasks

## 1. Dashboard panels (behavior)

- [x] 1.1 Write failing tests for the windows, lines, unit, routes, counts in range and Qdrant row of `llm-stack.json`, and remove the `llm-stack.json` rows from the aggregate-lines test
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/commands/k8s/test_stack_dashboards.py`
- [x] 1.2 Change `llm-stack.json`: `$__rate_interval` in each rate, no mean or rolling lines, unit `mbytes`, model routes only, cooldown and fallback stats, one Qdrant status target, the collections stat and the vectors per collection
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/commands/k8s/test_stack_dashboards.py tests/prometheus/test_k8s_monitoring_dashboards.py`

## 2. Documents

- [x] 2.1 Say in `k8s/README.md` how the cooldown and fallback stats read before the first event
  - Verification: `$ uv run devops ci docs`
