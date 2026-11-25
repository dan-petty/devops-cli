# Proposal

## Why

The linter at `src/devops_cli/grafana/linter.py:136:issues.extend(_check_panel_ids(dashboard.panels))` checks identity, panel ids, layout, datasources and PromQL syntax only, and it reads the top-level panels only, so a dashboard ships a graph over the whole range, a fixed rate window, a constant-zero fallback, an unbounded label or a histogram count on a seconds axis and nothing reports it (#4743).

## What Changes

- Adds `panels` to `src/devops_cli/grafana/schema.py:class Panel`, and `instant`, `label_selector` and `profile_type_id` to `src/devops_cli/grafana/schema.py:class Target`, so the linter reads a collapsed row and a Pyroscope target.
- Makes the datasource of a target optional at `src/devops_cli/grafana/schema.py:71: datasource: Datasource = Field(default_factory=Datasource)`, and resolves it from the panel at `src/devops_cli/grafana/linter.py:110: expression = query.datasource.type == CONST_GRAFANA_EXPRESSION_DATASOURCE_TYPE`, so the Pyroscope and Loki targets of the generated dashboards are no longer read as Prometheus.
- Reads the panels of a collapsed row at `src/devops_cli/grafana/linter.py:138:issues.extend(_check_targets(dashboard.panels))` and counts them in the report, while the overlap check keeps the top-level panels.
- Checks a Pyroscope target by its label selector and profile type, and deletes the `expr` that `k8s/monitoring/dashboards/pyroscope.json` carried only for the linter.
- Adds five query rules beside `src/devops_cli/grafana/linter.py:def _check_targets` for a range variable in a graph target, a fixed window in a time series target, a constant-zero fallback, an unbounded label in a grouping or legend, and a histogram count on a seconds axis.
- Replaces each fixed rate, irate, increase or delta window of `k8s/monitoring/dashboards/coredns.json`, `k8s/monitoring/dashboards/ingress-tunnel.json`, `k8s/monitoring/dashboards/otel-collector.json` and `k8s/monitoring/dashboards/prometheus-server.json` with `$__rate_interval`.
- Replaces each fixed window of `k8s/monitoring/dashboards/cloudnative-pg.json`, `k8s/monitoring/dashboards/system-topology.json` and `k8s/monitoring/dashboards/seaweedfs.json`, and of `k8s/devops/dashboards/ai-spend.json`, where the unit override of the slot wait panel moves from the legend regexp to the refId `B`.
- Adds `tests/grafana/test_grafana_dashboard_rules.py`, with a failing case for each rule, a case for a nested panel and a target with no datasource of its own, a timing case that times `_check_graph_queries` and `_check_histogram_units` alone over the 21 shipped dashboards, and a census over the 21 shipped dashboards.
- Lists the five rules and the nested panels in the dashboard section of `k8s/README.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `grafana-dashboard-lint`: The linter reads the datasource of a target from its panel, The linter checks the panels of a collapsed row, A range variable in a graph target is an error, A fixed window in a time series target is an error, A constant-zero fallback in a time series target is an error, An unbounded label in a grouping or legend is an error, A histogram count on a seconds axis is an error, A Pyroscope target is checked by its label selector and profile type, Each shipped dashboard lints clean, The new rules keep the dashboard lint test fast

## Impact

- Code: `src/devops_cli/grafana/schema.py`, `src/devops_cli/grafana/linter.py`, `src/devops_cli/config/constants.py`, `k8s/monitoring/dashboards/pyroscope.json`, `k8s/monitoring/dashboards/coredns.json`, `k8s/monitoring/dashboards/ingress-tunnel.json`, `k8s/monitoring/dashboards/otel-collector.json`, `k8s/monitoring/dashboards/prometheus-server.json`, `k8s/monitoring/dashboards/cloudnative-pg.json`, `k8s/monitoring/dashboards/system-topology.json`, `k8s/monitoring/dashboards/seaweedfs.json`, `k8s/devops/dashboards/ai-spend.json`
- Documents: `k8s/README.md`
- Tests: `tests/grafana/test_grafana_dashboard_rules.py`

## Feasibility

- The probe lines confirm the cited dashboard paths word for word: The path `k8s/monitoring/dashboards/coredns.json` is a file of the staging commit. and The path `k8s/monitoring/dashboards/prometheus-server.json` is a file of the staging commit. The one query check of the module is `src/devops_cli/grafana/linter.py:def _check_targets`.
- The probes stopped before the identifiers, word for word: Not probed, the bound of 10 commands is reached: `pod`, `histogram_count`, `test_repository_dashboards_lint_clean`, `timeseries`, `barchart`, `panels`. The reads of this run decide each of them.
- The linter runs five checks and reads the top-level panels only: `src/devops_cli/grafana/linter.py:136:issues.extend(_check_panel_ids(dashboard.panels))` and `src/devops_cli/grafana/linter.py:86:def _check_targets`, so no rule covers a range, a window, a fallback, a label or a unit, and no check reads a panel inside a collapsed row.
- The schema cannot carry the new rules yet: `src/devops_cli/grafana/schema.py:class Target` holds `expr`, `expression`, `legend_format`, `ref_id` and `datasource`, `src/devops_cli/grafana/schema.py:71: datasource: Datasource = Field(default_factory=Datasource)` makes a target with no datasource a Prometheus target, and `src/devops_cli/grafana/schema.py:class Panel` holds `collapsed` and no nested `panels`.
- The review's missing-path finding is corrected at its place: `k8s/monitoring/dashboards/devops-sre-service.json:1724: "labelSelector": "{service_namespace=\"$namespace\", service_name=\"$workload\"}",` is a Pyroscope target with no `expr` and no target datasource, so group 1 resolves the datasource of a target from its panel and checks it by its selector and profile type, and no generated dashboard and no builder changes for it.
- The review's first false-premise finding is corrected at its place: the two burn-rate targets of `k8s/monitoring/dashboards/devops-roadmap-service.json:488: "legendFormat": "1 h burn rate",` and `k8s/monitoring/dashboards/devops-roadmap-service.json:493: "legendFormat": "6 h burn rate",` each divide two `increase` aggregates over one window, which rule 2 does not report, so the two generated service dashboards keep their queries.
- The review's second false-premise finding is corrected at its place: `references` for `[5m]`, `[1h]` and `[6h]` names `k8s/monitoring/dashboards/prometheus-server.json` with 3, 2 and 1 lines, so group 3 replaces every fixed window of that file and not the `[5m]` lines only.
- The review's third false-premise finding is corrected at its place: `references` for `[1h]` names `k8s/devops/dashboards/ai-spend.json` with 6 lines, and group 5 replaces every fixed window of that file, including the three panels that the finding quotes.
- The review's timing finding is corrected at its place: the earlier plan timed the whole lint run, which `tests/grafana/test_grafana_dashboards.py:90: report = lint_dashboard_file(dashboard_file)` already does on the base. Group 2 now times `_check_graph_queries` and `_check_histogram_units` alone over the 21 parsed dashboards, so the case measures what the five rules add, and it fails on the base because the two functions do not exist.
- `list_files` on `k8s/monitoring/dashboards` lists 16 JSON files and on `k8s/devops/dashboards` 5, so the census and the timing case cover 21 dashboards, and `tests/grafana/test_grafana_dashboards.py:31: for directory in (_REPO_DASHBOARDS, _PRODUCT_DASHBOARDS)` builds that same set from the two folders.
- `references` counts the fixed windows of each shipped dashboard: `k8s/monitoring/dashboards/coredns.json` 10 lines of `[5m]`, `k8s/monitoring/dashboards/ingress-tunnel.json` 25 of `[2m]`, `k8s/monitoring/dashboards/otel-collector.json` 8 of `[5m]`, `k8s/monitoring/dashboards/prometheus-server.json` 3 of `[5m]`, 2 of `[1h]` and 1 of `[6h]`, `k8s/monitoring/dashboards/cloudnative-pg.json` 19 of `[5m]`, `k8s/monitoring/dashboards/system-topology.json` 9 of `[5m]` and 2 of `[1h]`, `k8s/monitoring/dashboards/seaweedfs.json` 20 of `[1m]`, and `k8s/devops/dashboards/ai-spend.json` 2 of `[5m]`, 2 of `[30m]`, 6 of `[1h]` and 1 of `[15m]`.
- Groups 3, 4 and 5 change those 8 files; the plan decides each of the other 13 as kept, and group 5's census case stops when a rule reports one: `k8s/monitoring/dashboards/llm-stack.json`, `k8s/monitoring/dashboards/nvidia-dcgm.json`, `k8s/monitoring/dashboards/k8s-views-global.json`, `k8s/monitoring/dashboards/k8s-views-namespaces.json`, `k8s/monitoring/dashboards/k8s-views-nodes.json`, `k8s/monitoring/dashboards/k8s-views-pods.json`, `k8s/monitoring/dashboards/pyroscope.json`, `k8s/monitoring/dashboards/devops-roadmap-service.json`, `k8s/monitoring/dashboards/devops-sre-service.json`, `k8s/devops/dashboards/devops-ai-rag.json`, `k8s/devops/dashboards/devops-cli.json`, `k8s/devops/dashboards/project-metrics.json` and `k8s/devops/dashboards/roadmap-service-telemetry.json`.
- Two of those 13 keep a window or a fallback that no rule reports: `k8s/devops/dashboards/roadmap-service-telemetry.json:288: "expr": "max(last_over_time(devops_cli_service_budget_spent_requests{job=~\"$job\"}[5m]))",` reads a gauge with no rate, and `k8s/devops/dashboards/ai-spend.json:285: "type": "stat",` shows that the target at `k8s/devops/dashboards/ai-spend.json:292: "expr": "count(sum by (server, backend) (increase(devops_cli_ai_requests_total{cached=\"false\"}[15m])) > 0) or vector(0)",` sits in a stat panel.
- The `$__range` and `or vector(0)` targets stay: `references` counts 5 `$__range` lines in `k8s/devops/dashboards/ai-spend.json`, 15 in `k8s/devops/dashboards/devops-ai-rag.json`, 16 in `k8s/devops/dashboards/devops-cli.json`, 9 in `k8s/devops/dashboards/roadmap-service-telemetry.json` and 3 in `k8s/monitoring/dashboards/llm-stack.json`, and `k8s/devops/dashboards/devops-ai-rag.json:830: "expr": "sum(increase(devops_cli_ai_spend_usd_total{job=~\"$job\"}[1d])) or vector(0)",` shows the instant shape that rules 1 and 3 leave alone; the census case of group 5 stops if a rule reports one of them.
- `references` for `[5m]` also names `k8s/devops/dashboards/roadmap-service-telemetry.json` with 8 lines and `k8s/devops/dashboards/project-metrics.json` with 23 `[1h]` lines, and both read their gauges with `last_over_time`, which no rule covers.
- The constants of the staged tree that the plan relies on: `src/devops_cli/config/constants.py:2484:CONST_GRAFANA_DASHBOARD_GRID_WIDTH: Final[int] = 24`, `src/devops_cli/config/constants.py:2486:CONST_GRAFANA_SCHEMA_VERSION: Final[int] = 39`, `src/devops_cli/config/constants.py:2487:CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE: Final[str] = "prometheus"` and `src/devops_cli/config/constants.py:2493:CONST_GRAFANA_PANEL_TYPE_TIMESERIES: Final[str] = "timeseries"`.
- The histogram rule reads the panel unit and the override that the staged AI spend panel holds: `k8s/devops/dashboards/ai-spend.json:918: "unit": "s"` and `k8s/devops/dashboards/ai-spend.json:924: "options": "^calls "` sit in the panel whose `k8s/devops/dashboards/ai-spend.json:973: "expr": "histogram_count(sum by (priority) (increase(devops_cli_ai_ollama_slot_wait_seconds[1h])))",` has refId `B`; `search_code` for `histogram_count` names 11 target lines in `k8s/devops/dashboards/ai-spend.json`, `k8s/devops/dashboards/devops-ai-rag.json`, `k8s/devops/dashboards/devops-cli.json` and `k8s/devops/dashboards/roadmap-service-telemetry.json`, and the census case of group 5 stops when another panel with a seconds unit holds one.
- No function that the plan calls needs a checkout of a repository, a client of a service or a network: `src/devops_cli/grafana/linter.py:164:payload = json.loads(path.read_text(encoding="utf-8"))` reads one local JSON file, and the PromQL check is the pure `validate_promql`.
- The plan introduces no new program: `uv run devops ci test` runs `pytest` from the runner image with the failure class test, `uv run devops ci docs` runs `devops` from the image with the failure class test, no program is `NOT_IN_RUNNER`, and the pod keeps readOnlyRootFilesystem true, runAsNonRoot true, capabilities.drop ALL and allowPrivilegeEscalation false.
- The first checks against the real system: `uv run devops ci test tests/grafana/test_grafana_dashboards.py` passes on the base over the 21 files; `uv run devops grafana dashboards lint k8s/monitoring/dashboards/coredns.json` exits 0 on the base and exits 1 once group 2 lands; `uv run devops ci test tests/grafana/test_grafana_dashboard_rules.py` fails on the base because the module does not exist.

## Existing Tool Considered

grafana/dashboard-linter v0.4.0 (Apache-2.0, maintained) covers only a `rate()` that has no `$__rate_interval` and takes no custom rule, so it reports none of the five rules; the rules here cost about 100k tokens to build, 3k tokens a month to keep and 2 hours elapsed.

## Dependencies

- #7032 shares `k8s/README.md` with this plan; it writes the SLO section and this plan writes the dashboard section, so the two changes touch different paragraphs of the same file.
- #4684: it sends the cumulative samples that the increase windows of the dashboards read, so a window moved to `$__rate_interval` reads a series that has a first sample.
- #4707: it makes the GitHub and command panels of the command dashboard readable, so this plan leaves the 16 `$__range` targets of `k8s/devops/dashboards/devops-cli.json` alone.
- #4718: it makes the Service row panels readable, and the generated service dashboards keep their SLO windows, so the new rules leave them alone.
- #4712: it shows one repository at a time in Project Velocity, and that dashboard reads its gauges with `last_over_time`, so the window rule leaves it alone.
- #4724: it reads AI spend from the gateway counter, and this plan changes only the windows that remain in that dashboard.
- #4728: it opens the SRE dashboard on the Service namespace, so this plan leaves its panels alone.
- #4732: it tidies the LLM stack windows, units and lines, and every rate window of that dashboard already uses the interval, so this plan leaves it alone.
