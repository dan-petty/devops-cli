# Tasks

## 1. Read the spend panels from the gateway spend counter

Kind: manifest. Reads: `k8s/devops/dashboards/ai-spend.json`, `tests/prometheus/test_dashboard_queries.py`, `tests/fixtures/metrics/litellm.yaml`. Changes: `k8s/devops/dashboards/ai-spend.json`, `tests/fixtures/dashboard_queries/ai-spend.yaml` (new), `tests/prometheus/test_k8s_monitoring_dashboards.py`, `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 1.1 Add the promtool cases of the spend panels to `tests/fixtures/dashboard_queries/ai-spend.yaml`: spend in range $30, hourly bars that add up to $30, bars by model of $24 and $6, projections that give the same value for a range of 6 h and 7 d, and coverage 0.75. Add `test_the_spend_panels_take_gateway_spend_from_the_gateways_spend_counter` and `test_the_hourly_spend_panels_draw_bars_that_follow_the_step`, and change the coverage assertions of `test_the_gateway_row_shows_attempts_by_status_traffic_by_caller_and_devops_cli_coverage`, the projection assertions of `test_grafana_dashboard_projections_and_dcgm_grid_layout` and the set of `test_every_spend_query_shows_zero_when_no_spend_series_matches`
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py tests/prometheus/test_k8s_monitoring_dashboards.py tests/grafana/test_grafana_dashboards.py tests/telemetry/test_telemetry_instruments.py` fails on the base
- [x] 1.2 Change the spend panels of `k8s/devops/dashboards/ai-spend.json`: Cloud Spend in Range, the spend target of the three projections, Spend: USD per hour, Spend by model: USD per hour and devops-cli Coverage of Gateway Spend, with their titles, descriptions, units and bar settings
  - Verification: `$ uv run devops ci test tests/prometheus/test_dashboard_queries.py tests/prometheus/test_k8s_monitoring_dashboards.py tests/grafana/test_grafana_dashboards.py tests/telemetry/test_telemetry_instruments.py tests/commands/k8s/test_stack_dashboards.py` passes
- [x] 1.3 Lint the dashboard
  - Verification: `$ uv run devops grafana dashboards lint k8s/devops/dashboards/ai-spend.json`

## 2. Documents

Kind: other. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 2.1 Tell in `k8s/README.md` how the spend panels read the gateway spend counter, and what the coverage stat shows
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: promtool gives the expected spend, bars, projections and coverage of the fixture series.
- Group 1: live at 7 d, the hourly spend bars add up to within 1 % of the spend in range.

## Workflow follow-up

- #5914 prices the local savings at the reference model and reads their tokens from the gateway.
- #5784 makes the local-savings windows follow the step.
- #5922 makes the request, token and slot-wait panels and the spend panels of `devops-ai-rag.json` follow the step.
- After the merge, a comment on #4724 gives the 7-day value of devops-cli Coverage of Gateway Spend (owner decision of 2026-11-13).
