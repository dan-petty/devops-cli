# Tasks

## 1. State and guard the classic schema of the devops-cli dashboard

Kind: manifest. Reads: `k8s/devops/dashboards/devops-cli.json`, `tests/grafana/test_grafana_dashboards.py`, `k8s/monitoring/dashboards/devops-sre-service.json`. Changes: `k8s/devops/dashboards/devops-cli.json`, `tests/grafana/test_grafana_dashboards.py`.

- [ ] 1.1 The case `test_cli_dashboard_keeps_the_classic_schema` in `tests/grafana/test_grafana_dashboards.py` fails on the staged file, which states `schemaVersion` 38 while the provisioned Grafana 13 dashboards state 42
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` fails on the base
- [ ] 1.2 In `k8s/devops/dashboards/devops-cli.json`, change the top-level `schemaVersion` from 38 to 42, the value that `k8s/monitoring/dashboards/devops-sre-service.json` and `k8s/monitoring/dashboards/devops-roadmap-service.json` state. In `tests/grafana/test_grafana_dashboards.py`, add `test_cli_dashboard_keeps_the_classic_schema` after `test_cli_dashboard_shows_the_selected_sub_commands_in_one_table`: it reads `(_PRODUCT_DASHBOARDS / "devops-cli.json")`, parses it with `json.loads`, and asserts that `panels` is a list, that `apiVersion` is absent, and that `schemaVersion` is 42
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` passes
