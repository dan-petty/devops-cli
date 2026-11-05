# Tasks

## 1. Filter the dashboard by job

Reads: `k8s/monitoring/dashboards/devops-cli.json`. Changes: `k8s/monitoring/dashboards/devops-cli.json`, `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 1.1 Add tests to `tests/grafana/test_grafana_dashboards.py`: the first variable is `job`, and each `devops_cli_*` series of each Prometheus query has a selector that starts with `job=~"$job"`. Change the expected queries in the tests of the variables, the sub-command row, the GitHub API row and the embedding hit share
  - Verification: `uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/telemetry/test_telemetry_instruments.py` fails on the base
- [ ] 1.2 Add the variable `job` to `devops-cli.json`, make `command` and `sub_command` filter by it, and add the matcher to each Prometheus query
  - Verification: `uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/telemetry/test_telemetry_instruments.py` passes

## 2. Chart the series of the Service

Reads: `src/devops_cli/config/constants.py`, `k8s/monitoring/prometheus-values.yaml`. Changes: `k8s/monitoring/dashboards/devops-cli.json`, `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 2.1 Add tests to `tests/grafana/test_grafana_dashboards.py`: the row "Roadmap Service" holds its panels with their queries, and each `CONST_SERVICE_METRIC_*` series is in a query of the row. Add the Service series and their kinds to the series that `tests/telemetry/test_telemetry_instruments.py` accepts
  - Verification: `uv run devops ci test tests/grafana/test_grafana_dashboards.py` fails on the base
- [ ] 2.2 Add the row and its panels to `devops-cli.json`
  - Verification: `uv run devops ci test tests/grafana/test_grafana_dashboards.py tests/telemetry/test_telemetry_instruments.py tests/prometheus/test_k8s_monitoring_dashboards.py` passes

## 3. Document the row, the variable and the budget

Changes: `k8s/README.md`.

- [ ] 3.1 Say in `k8s/README.md` that the Jobs act as the same App and do not count in `service.github_requests_per_hour`, and tell the reader of the two GitHub alerts to set the variable `Job`. Name the Service in the line of `devops-cli.json` in the file tree
  - Verification: `git grep -n "do not count in .service.github_requests_per_hour" k8s/README.md`

## Workflow follow-up

- The Service's own gateway key: #3685, blocked by #1635.
- Pending a person: mint the key of #3685 after #1635 merges.
