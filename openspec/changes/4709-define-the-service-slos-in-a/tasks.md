# Tasks

## 1. Render a Sloth spec into its recording rules and burn-rate alerts

Kind: behavior. Reads: `docs/guidelines/sre.md`, `src/devops_cli/prometheus/promql.py`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/commands/test_prometheus.py`. Changes: `src/devops_cli/prometheus/slo_rules.py` (new), `tests/prometheus/test_k8s_monitoring_alerting.py`.
Adds: `SloSpec`, `load_slo_specs`, `render_slo_groups`, `write_slo_groups`, `SLO_MIN_EVENTS`, `SLO_WINDOW_DAYS`, `SLO_BURN_RATE_ROWS`, `SLO_RECORD_NAMES`

- [ ] 1.1 `test_render_slo_groups_gives_each_alert_the_event_guard` in `tests/prometheus/test_k8s_monitoring_alerting.py` fails: `src/devops_cli/prometheus/slo_rules.py` holds no `SloSpec`, no `load_slo_specs`, no `render_slo_groups`, no `write_slo_groups` and no `SLO_MIN_EVENTS`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/prometheus/slo_rules.py`. `SloSpec` holds one Sloth `prometheus/v1` spec: its `service`, the `name`, `objective` and `description` of its one SLO, its error query and its total query with the `{{.window}}` placeholder, and the grouping labels that `grouping_labels` of `src/devops_cli/prometheus/promql.py` reads from the total query. `load_slo_specs(directory)` reads each `.yaml` of the folder and refuses two specs with one service and name. `SLO_WINDOW_DAYS` is 28, `SLO_MIN_EVENTS` is 20, and `SLO_BURN_RATE_ROWS` holds the four rows of Table 2 of `docs/guidelines/sre.md`: page 1 h over 5 min at 13.44x, page 6 h over 30 min at 5.6x, ticket 1 d over 2 h at 2.8x and ticket 3 d over 6 h at 0.93x. `SLO_RECORD_NAMES` holds the seven error-ratio names from `slo:sli_error:ratio_rate5m` to `slo:sli_error:ratio_rate3d`, and `slo:objective:ratio`, `slo:error_budget:ratio` and `slo:time_period:days`. `render_slo_groups(specs)` gives one group for each spec, named `slo-<file stem>`, with one recording rule for each name of `SLO_RECORD_NAMES` and four alerts named `<alerting name>Page1h`, `Page6h`, `Ticket1d` and `Ticket3d`. Each recording rule carries `labels: {service: <service>, slo: <name>}` and divides the error query by the total query over the window of its name. Each alert needs both recorded ratios of its row above `<burn rate> * (1 - <objective>)` and ends with `and on (<grouping>) (<total query over the long window>) >= SLO_MIN_EVENTS`, or with a plain `and` when the spec groups by no label; it carries the severity of its row and no `for`. `write_slo_groups(path, groups)` replaces the text between the two marker comments of the values file and leaves the rest. The `__main__` block renders the folder and writes it when it gets `--write`. Add the renderer tests to `tests/prometheus/test_k8s_monitoring_alerting.py`: the failing test builds a spec in a temporary folder, loads it, renders it, and asserts the group name, the record names, the four alerts with their severity, the guard of each expression and the grouping
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 2. Add one Sloth spec for each of the four SLOs

Kind: other. Reads: `k8s/catalog.toml`, `docs/guidelines/sre.md`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/prometheus/slo_rules.py`, `k8s/README.md`. Changes: `k8s/devops/monitoring/slos/roadmap-service-rounds.yaml` (new), `k8s/devops/monitoring/slos/runner-jobs-duration.yaml` (new), `k8s/devops/monitoring/slos/llm-gateway-requests.yaml` (new), `k8s/devops/monitoring/slos/llm-gateway-latency.yaml` (new).

- [ ] 2.1 Write the four specs under `k8s/devops/monitoring/slos/` in the Sloth `prometheus/v1` shape, each with one SLO, its `objective` and the `{{.window}}` placeholder in both queries. `k8s/devops/monitoring/slos/roadmap-service-rounds.yaml` names service `roadmap-service`, objective 99, the error query `sum by (repo, row) (increase(devops_cli_service_jobs_total{result="error"}[{{.window}}]))` and the total query `sum by (repo, row) (increase(devops_cli_service_jobs_total{result=~"success|error"}[{{.window}}]))`, as the recording group of `k8s/devops/monitoring/prometheus-rules-values.yaml` reads the same metric and labels. `k8s/devops/monitoring/slos/runner-jobs-duration.yaml` names service `runner-jobs` and objective 90, counts the runner Jobs that end within 3,600 s over the runner Jobs that end, and its description says that only the runner Jobs that end count, so a Job with no end is not in the SLI. `k8s/devops/monitoring/slos/llm-gateway-requests.yaml` names service `llm-gateway` and objective 99.5, from `litellm_proxy_failed_requests_metric_total` over `litellm_proxy_total_requests_metric_total`. `k8s/devops/monitoring/slos/llm-gateway-latency.yaml` names service `llm-gateway` and objective 95, from the `le="60.0"` series over the `le="+Inf"` series of `litellm_request_total_latency_metric_bucket`. Each `service` is a `name` of `k8s/catalog.toml`
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 3. Check that each spec names a service of the catalog

Kind: other. Reads: `k8s/catalog.toml`, `k8s/devops/monitoring/slos/roadmap-service-rounds.yaml`, `k8s/devops/monitoring/slos/runner-jobs-duration.yaml`, `k8s/devops/monitoring/slos/llm-gateway-requests.yaml`, `k8s/devops/monitoring/slos/llm-gateway-latency.yaml`, `tests/gate/k8s_checks/environment_freeze.py`, `tests/gate/k8s.py`. Changes: `tests/gate/k8s_checks/slo_rules.py` (new), `tests/gate/k8s.py`.

- [ ] 3.1 Add `tests/gate/k8s_checks/slo_rules.py` with `check_each_spec_names_a_catalog_service`, in the shape of `tests/gate/k8s_checks/environment_freeze.py`: it reads the four specs under `k8s/devops/monitoring/slos/` and `k8s/catalog.toml`, and fails with the spec file and the `service` that the catalog does not hold. Update the docstring of `tests/gate/k8s.py`, which names `environment_freeze` as the one module that reads files and no render, so it names the second such module
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 4. Write the four SLO groups into the product rule file

Kind: other. Reads: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `k8s/devops/monitoring/slos/roadmap-service-rounds.yaml`, `k8s/devops/monitoring/slos/runner-jobs-duration.yaml`, `k8s/devops/monitoring/slos/llm-gateway-requests.yaml`, `k8s/devops/monitoring/slos/llm-gateway-latency.yaml`, `src/devops_cli/prometheus/slo_rules.py`, `tests/gate/k8s_checks/slo_rules.py`, `tests/commands/k8s/test_k8s.py`. Changes: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/gate/k8s_checks/slo_rules.py`, `tests/commands/k8s/test_k8s.py`.

- [ ] 4.1 Add the two marker comments to the groups of `serverFiles.devops_cli_alerting_rules.yml` in `k8s/devops/monitoring/prometheus-rules-values.yaml`, then render the four groups with `write_slo_groups` by running `src/devops_cli/prometheus/slo_rules.py` as a program with `--write`. Add `check_the_slo_groups_are_the_render_of_the_specs` to `tests/gate/k8s_checks/slo_rules.py`: it reads the text between the markers and the four specs under `k8s/devops/monitoring/slos/`, and fails with the difference when the two differ
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 5. Add a promtool case file for each SLO

Kind: manifest. Reads: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `docs/guidelines/sre.md`. Changes: `tests/fixtures/prometheus_rules/slo_roadmap_service_rounds_tests.yaml` (new), `tests/fixtures/prometheus_rules/slo_runner_jobs_duration_tests.yaml` (new), `tests/fixtures/prometheus_rules/slo_llm_gateway_requests_tests.yaml` (new), `tests/fixtures/prometheus_rules/slo_llm_gateway_latency_tests.yaml` (new), `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [ ] 5.1 `test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series[slo_roadmap_service_rounds_tests]` fails: `RULE_GROUP_TESTS` in `tests/prometheus/test_k8s_monitoring_alerting.py` holds no case file for the group `slo-roadmap-service-rounds`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [ ] 5.2 Write the four case files in the shape of `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`: `rule_files` names the group file, the file sets `evaluation_interval: 5m`, and each case sets `interval: 1m`, so a 5-minute short window holds five samples and a 3-day case makes 864 rounds, under the rounds bound of `MAX_PROMTOOL_ROUNDS`. Each file holds a case in which every window breaches and all four alerts fire, a case of a normal series in which no alert fires, a case of fewer than 20 events in the 1-hour and the 6-hour windows in which the two page alerts stay quiet, and a case of at most 5 events in the last hour and at least 20 in the 1-day window in which the two ticket alerts fire and the page alerts stay quiet. Add the four groups and their files to `RULE_GROUP_TESTS`, and the five metrics `kube_job_status_start_time`, `kube_job_status_completion_time`, `litellm_proxy_total_requests_metric_total`, `litellm_proxy_failed_requests_metric_total` and `litellm_request_total_latency_metric_bucket`, together with the names of `SLO_RECORD_NAMES`, to `SERVED_SERIES` of `tests/prometheus/test_k8s_monitoring_alerting.py`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 6. Name the spec in the README and add the alert rows

Kind: other. Reads: `k8s/README.md`, `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/gate/k8s_checks/slo_rules.py`, `docs/guidelines/sre.md`. Changes: `k8s/README.md`, `tests/gate/k8s_checks/slo_rules.py`.

- [ ] 6.1 In the Service levels section of `k8s/README.md`, give the SLO table a `Spec` column, name the spec of each of the four SLOs of this change, drop the objective and the error budget of those four rows, and replace the sentence that the rows stay here until the specs hold them. Keep the SLO 5 objective and error budget, the note of the low-sample rule and the SLO 2 caveat. Add a row with four cells to the Alerting table for each of the 16 alerts of the four groups. Add `check_each_slo_row_names_its_spec` and `check_each_slo_alert_has_a_runbook_row` to `tests/gate/k8s_checks/slo_rules.py`: the first reads the four spec files of this change, finds the README row whose SLO number matches each spec, and fails when that row names no spec or still holds a percentage; it reads no row of another SLO, so the SLO 5 row, which keeps its objective until its own spec, passes. The second fails on an alert of the four groups with no row
  - Verification: `$ uv run devops ci --check --only k8s` passes
- [ ] 6.2 Edit `k8s/README.md` to name the spec of each of the four SLOs and to give a runbook row for each SLO alert. Update `src/devops_cli/telemetry/instruments.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 5: `promtool check rules` and `promtool test rules` pass, with one fixture for each SLO.
- Pending person: After the Argo CD sync, `slo:sli_error:ratio_rate1h` returns series for each SLO within 10 min., Only a person confirms it after the merge and the Argo CD sync: the runner pod has no cluster token and no step queries the live Prometheus.
- Group 4: The check fails when the spec changes and the file is not generated again.
- Group 5: A fixture with fewer than 20 events in the long window fires no burn alert.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
