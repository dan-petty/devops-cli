# Tasks

## 1. The invariants

- [x] 1.1 Replace `test_every_series_is_read_through_rate_or_increase` in `tests/test_telemetry_instruments.py` with `test_every_series_is_read_through_the_function_of_its_kind`, which covers every devops-cli dashboard, and add `test_a_counter_name_ends_in_total_and_no_other_name_does`. On origin/main both fail. Verify with `uv run devops ci test tests/test_telemetry_instruments.py`

## 2. The names and the queries

- [x] 2.1 Drop `_total` from the 13 project gauges and their constants in `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/github/metrics.py`, `tests/test_github_metrics.py` and `tests/test_roadmap_run.py`. Verify with `uv run devops ci test tests/test_telemetry_instruments.py tests/test_github_metrics.py tests/test_roadmap_run.py`
- [x] 2.2 Make each gauge panel of `k8s/monitoring/dashboards/project-metrics.json` read `last_over_time(<metric>[$__range])` with no `or vector(0)`, and say so in its description. Verify with `uv run devops ci test tests/test_telemetry_instruments.py tests/test_grafana_dashboards.py tests/test_k8s_monitoring_dashboards.py tests/test_stack_dashboards.py`

## 3. Documents

- [x] 3.1 Say in `src/devops_cli/docs/generator.py` how a dashboard reads a gauge, and regenerate `docs/TELEMETRY.md`, which names the gauges by their new names. Verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- Pending a person: scale the roadmap Service above 0 replicas, or run `devops gh metrics --emit-telemetry`, then open the dashboard and see each panel with data.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
