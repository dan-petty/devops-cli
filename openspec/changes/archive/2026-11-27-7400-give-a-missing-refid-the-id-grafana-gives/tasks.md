# Tasks

## 1. The ids of Grafana

Kind: behavior. Changes: `src/devops_cli/grafana/linter.py`, `src/devops_cli/grafana/schema.py`, `tests/grafana/test_grafana_dashboards.py`.

- [x] 1.1 Write the tests of `grafana_ref_ids` and of the duplicate check with targets that state no refId
  - Verification: `$ uv run pytest -q tests/grafana/test_grafana_dashboards.py` failed 8 tests before the code
- [x] 1.2 Leave `Target.ref_id` empty for a target with no refId, add `grafana_ref_ids`, and check duplicates on its ids
  - Verification: `$ uv run pytest -q tests/grafana tests/prometheus/test_dashboard_queries.py` passes
