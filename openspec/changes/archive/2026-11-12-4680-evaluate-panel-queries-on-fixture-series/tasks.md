# Tasks

## 1. Tests: the shared promtool run

- [x] 1.1 Move the promtool run of `tests/prometheus/test_k8s_monitoring_alerting.py` to `tests/support/promtool.py`, and make the alerting tests import it.
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 2. Tests: the panel query harness

- [x] 2.1 Add `tests/prometheus/test_dashboard_queries.py`: the Grafana variables, the check of each case query against its panel target, the check of the series shapes and one promtool run for each fixture file.
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py`
- [x] 2.2 Add `tests/fixtures/dashboard_queries/devops-cli.yaml` with the cases of "AI Spend in Range" and "Alternatives Unchecked Items", one test group for each series shape.
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py`

## 3. Documents

- [x] 3.1 In `docs/TESTING.md`, add the section "Dashboard queries", which tells how to add a case.
  - Verification: `$ uv run devops ci docs`
