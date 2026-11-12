# Tasks

## 1. Behavior: the harness adds up the bars of a panel

- [x] 1.1 Add the keys `bars` and `total` to the cases of `tests/prometheus/test_dashboard_queries.py`, a test that checks the subquery, and a test that each expected sum is within 1 % of its total
  - Verification: `$ uv run pytest tests/prometheus/test_dashboard_queries.py -q`

## 2. Behavior: the readable panels of devops-cli.json

- [x] 2.1 Add the cases of the golden signals, the command tables, the GitHub requests and the throttles to `tests/fixtures/dashboard_queries/devops-cli.yaml`, and the chart rule tests (two units in one panel, a second-axis override, the golden signal row order, the table sort and links, the defaults) to `tests/prometheus/test_k8s_monitoring_dashboards.py`, and see them fail
  - Verification: `$ uv run pytest tests/prometheus -q`
- [x] 2.2 Change `k8s/monitoring/dashboards/devops-cli.json`: the golden signals row, the breakdown tables, the GitHub API row, the review, findings and RAG panels, the error stream and the defaults; change the tests that held the old panels
  - Verification: `$ uv run pytest tests/prometheus tests/design tests/grafana tests/telemetry/test_telemetry_instruments.py -q`

## 3. Documents

- [x] 3.1 Name the core requests panel in `k8s/README.md`, add the bars case to `docs/TESTING.md`, and give the time range of a dashboard of sparse series in the Grafana page of the knowledge base
  - Verification: `! git grep -n "GitHub Requests by Resource" -- k8s docs src`

## Workflow follow-up

- #5192 sends a sub-command point for the body of a command group, so the golden signals count `devops ci`.
- #4718 applies the chart rules to the Service rows and removes `SERVICE_ROWS`.
- #4743 moves the window, range and zero rules into `devops grafana dashboards lint`.
- #4762 applies the design colors and the dash patterns of the series.
- #2703 closes as not planned after the merge, with a link to this change.

- Pending a person: open the dashboard in the Grafana light and dark themes after Argo CD syncs it, and check that the bars, the dashed lines and the tables read well. The image renderer (#5185) is not installed, so no test makes a panel image.
- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
