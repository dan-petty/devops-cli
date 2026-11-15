# Tasks

## 1. Delete the builders

Reads: `src/devops_cli/grafana/builders.py`, `tests/grafana/test_grafana_dashboards.py`.

Changes: `src/devops_cli/grafana/__init__.py`, `tests/grafana/test_grafana_dashboards.py`, and the deletion of `src/devops_cli/grafana/builders.py`.

- [x] 1.1 Delete the module, its exports and its tests, and keep the linter and schema tests.
  - Verification: `$ uv run devops ci test tests/grafana`
- [x] 1.2 Check the dashboard lint.
  - Verification: `$ uv run devops grafana dashboards lint k8s/monitoring/dashboards`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
