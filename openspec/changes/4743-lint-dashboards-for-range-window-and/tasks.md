# Tasks

## 1. Read the panels of a collapsed row and the datasource of a target

Kind: behavior. Reads: `tests/grafana/test_grafana_dashboards.py`, `k8s/monitoring/dashboards/devops-sre-service.json`, `k8s/monitoring/dashboards/pyroscope.json`. Changes: `src/devops_cli/grafana/schema.py`, `src/devops_cli/grafana/linter.py`, `src/devops_cli/config/constants.py`, `tests/grafana/test_grafana_dashboard_rules.py` (new), `k8s/monitoring/dashboards/pyroscope.json`.
Adds: `_iter_panels`, `_target_datasource`, `CONST_GRAFANA_PYROSCOPE_DATASOURCE_TYPE`

- [ ] 1.1 `test_a_duplicate_panel_id_inside_a_collapsed_row_is_reported` fails on the base because `src/devops_cli/grafana/linter.py:136:issues.extend(_check_panel_ids(dashboard.panels))` reads the top-level panels only, and `test_a_target_takes_the_datasource_of_its_panel` fails because the flattened Pyroscope and Loki targets of `k8s/monitoring/dashboards/devops-sre-service.json` resolve to the Prometheus datasource
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` fails on the base
- [ ] 1.2 Add `panels: list[Panel]` to `Panel` and `instant`, `label_selector` and `profile_type_id` to `Target` of `src/devops_cli/grafana/schema.py`, and make the `datasource` of a target optional. Add `_iter_panels` and `_target_datasource` to `src/devops_cli/grafana/linter.py`, call `_iter_panels` once in `lint_dashboard` so the panel id, target and datasource checks read each panel of a collapsed row, count them in the report, and keep `_check_layout` on the top-level panels. Resolve each target datasource through `_target_datasource`, and check a target of the Pyroscope datasource by its label selector and profile type: an empty one is an error and its expression is not read. Add `CONST_GRAFANA_PYROSCOPE_DATASOURCE_TYPE` to `src/devops_cli/config/constants.py`. Delete the `expr` of each target of `k8s/monitoring/dashboards/pyroscope.json`
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` passes

## 2. Add the five query rules to the dashboard linter

Kind: behavior. Reads: `src/devops_cli/grafana/schema.py`, `src/devops_cli/grafana/service_dashboard.py`, `tests/grafana/test_grafana_dashboards.py`. Changes: `src/devops_cli/grafana/linter.py`, `src/devops_cli/config/constants.py`, `tests/grafana/test_grafana_dashboard_rules.py`.
Adds: `_check_graph_queries`, `_check_histogram_units`, `CONST_GRAFANA_UNBOUNDED_LABELS`, `CONST_GRAFANA_ALLOWED_INTERVALS`, `CONST_GRAFANA_PANEL_TYPE_BARCHART`, `CONST_GRAFANA_PANEL_TYPE_GRAPH`

- [ ] 2.1 `test_a_range_variable_in_a_graph_target_is_an_error`, `test_a_fixed_window_in_a_time_series_target_is_an_error`, `test_a_share_keeps_its_window`, `test_a_constant_zero_fallback_is_an_error`, `test_an_unbounded_label_in_a_grouping_or_legend_is_an_error`, `test_a_histogram_count_on_a_seconds_axis_is_an_error` and `test_the_new_rules_add_less_than_two_seconds` fail on the base and pass with the rules; the timing case fails on the base because `_check_graph_queries` and `_check_histogram_units` do not exist
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` fails on the base
- [ ] 2.2 Add `_check_graph_queries` and `_check_histogram_units` to `src/devops_cli/grafana/linter.py` and call both from `lint_dashboard`. `_check_graph_queries` reads each non-instant target of a panel whose type is a time series, graph or bar chart panel, and reports `$__range`, a rate, irate, increase or delta window outside `CONST_GRAFANA_ALLOWED_INTERVALS` unless the target divides two windowed aggregates over one window, `or vector(0)`, and a `by()` clause or legend over a label of `CONST_GRAFANA_UNBOUNDED_LABELS` when the dashboard defines a template variable of that name and the target holds no positive matcher for it. `_check_histogram_units` reports a target that holds `histogram_count` in a time series panel whose unit is `s` or `ms` when no override of the panel sets the unit of its refId by `byFrameRefID`. Each message names the panel and the refId, and the report names the dashboard. Add `CONST_GRAFANA_UNBOUNDED_LABELS`, `CONST_GRAFANA_ALLOWED_INTERVALS`, `CONST_GRAFANA_PANEL_TYPE_BARCHART` and `CONST_GRAFANA_PANEL_TYPE_GRAPH` to `src/devops_cli/config/constants.py`, and assert in the test module that `CONST_GRAFANA_UNBOUNDED_LABELS` holds the ten labels that the issue names. Add `test_the_new_rules_add_less_than_two_seconds`, which parses the 21 dashboards of the two folders, times `_check_graph_queries` and `_check_histogram_units` over them with `time.perf_counter`, and asserts that their total elapsed time is under 2 s; the other checks stay unchanged, so the case measures the cost that the five rules add
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` passes

## 3. Replace the fixed windows of the four monitoring dashboards

Kind: manifest. Reads: `tests/grafana/test_grafana_dashboards.py`. Changes: `k8s/monitoring/dashboards/coredns.json`, `k8s/monitoring/dashboards/ingress-tunnel.json`, `k8s/monitoring/dashboards/otel-collector.json`, `k8s/monitoring/dashboards/prometheus-server.json`, `tests/grafana/test_grafana_dashboard_rules.py`.

- [ ] 3.1 `test_the_four_window_dashboards_lint_clean` fails after the rules land, because `k8s/monitoring/dashboards/coredns.json` holds 10 fixed windows, `k8s/monitoring/dashboards/ingress-tunnel.json` 25, `k8s/monitoring/dashboards/otel-collector.json` 8 and `k8s/monitoring/dashboards/prometheus-server.json` 6
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` fails on the base
- [ ] 3.2 Replace every fixed rate, irate, increase or delta window of a non-instant target of `k8s/monitoring/dashboards/coredns.json`, `k8s/monitoring/dashboards/ingress-tunnel.json`, `k8s/monitoring/dashboards/otel-collector.json` and `k8s/monitoring/dashboards/prometheus-server.json` with `$__rate_interval`, including the `[1h]` and `[6h]` windows of the last file. Change no other field. Add `test_the_four_window_dashboards_lint_clean` to `tests/grafana/test_grafana_dashboard_rules.py`, which lints the four files and asserts no error
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` passes

## 4. Replace the fixed windows of the nested and old style dashboards

Kind: manifest. Reads: `tests/grafana/test_grafana_dashboards.py`. Changes: `k8s/monitoring/dashboards/cloudnative-pg.json`, `k8s/monitoring/dashboards/system-topology.json`, `k8s/monitoring/dashboards/seaweedfs.json`, `tests/grafana/test_grafana_dashboard_rules.py`.

- [ ] 4.1 `test_the_nested_and_old_style_dashboards_lint_clean` fails after the rules land, because `k8s/monitoring/dashboards/cloudnative-pg.json` holds 19 fixed windows, `k8s/monitoring/dashboards/system-topology.json` 11 and `k8s/monitoring/dashboards/seaweedfs.json` 20
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` fails on the base
- [ ] 4.2 Replace every fixed rate, irate, increase or delta window of a non-instant target of `k8s/monitoring/dashboards/cloudnative-pg.json`, `k8s/monitoring/dashboards/system-topology.json` and `k8s/monitoring/dashboards/seaweedfs.json` with `$__rate_interval`, including the windows inside the collapsed rows of the first file. Change no other field. Add `test_the_nested_and_old_style_dashboards_lint_clean` to `tests/grafana/test_grafana_dashboard_rules.py`, which lints the three files and asserts no error
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` passes

## 5. Fix the AI spend windows and the count unit override

Kind: manifest. Reads: `tests/grafana/test_grafana_dashboards.py`. Changes: `k8s/devops/dashboards/ai-spend.json`, `tests/grafana/test_grafana_dashboard_rules.py`.

- [ ] 5.1 `test_the_ai_spend_dashboard_lints_clean` fails after the rules land, because `k8s/devops/dashboards/ai-spend.json` holds 9 fixed windows in non-instant time series targets and sets the count unit of the slot wait panel by a legend regexp
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` fails on the base
- [ ] 5.2 Replace every fixed rate, irate, increase or delta window of a non-instant target of `k8s/devops/dashboards/ai-spend.json` with `$__rate_interval`, and change the matcher of the override of the slot wait panel from `byRegexp` `^calls ` to `byFrameRefID` `B`, so the count series keeps unit `short` and the right axis. Change no other field. Add `test_the_ai_spend_dashboard_lints_clean` and `test_each_shipped_dashboard_lints_clean` to `tests/grafana/test_grafana_dashboard_rules.py`; the second lints the 21 files of the two dashboard folders and asserts no error
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` passes

## 6. Document the five dashboard rules

Kind: other. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 6.1 Add a paragraph to the dashboard section of `k8s/README.md`, beside the lint command, that lists the five rules: a range variable in a graph target, a fixed window in a time series target, a constant-zero fallback, an unbounded label in a grouping or legend, and a histogram count on a seconds axis. Say that a share or a burn rate keeps its window, that the linter reads the panels of a collapsed row and counts them, and that it takes the datasource of a target from its panel
  - Verification: `$ uv run devops ci docs` passes
- [ ] 6.2 Edit `k8s/README.md` to list the five rules of the linter, the nested panels it reads and the window of a share or a burn rate
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: For each rule, a test dashboard makes the linter report an error with the dashboard, the panel and the refId, and a corrected copy lints clean.
- Group 5: test_repository_dashboards_lint_clean passes for all 16 dashboards with no per-file or per-rule exemption.
- Group 2: The new rules add less than 2 s to the test run.
- Group 6: k8s/README.md lists the 5 rules.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
