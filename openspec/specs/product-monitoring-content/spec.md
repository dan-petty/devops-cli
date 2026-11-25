# product-monitoring-content Specification

## Purpose
Where the monitoring content of the devops-cli product lives: the Grafana dashboards and the Prometheus alert rules that read the `devops_cli_*` series. The product content is apart from the environment content of `k8s/monitoring/`, so that the environment can move to its own repository and leave the product content in devops-cli.

## Requirements

### Requirement: The product dashboards have their own generator
`k8s/devops/dashboards/kustomization.yaml` SHALL generate the ConfigMap `grafana-devops-cli-dashboards` in namespace `monitoring` from `devops-cli.json`, `ai-spend.json` and `project-metrics.json`, with no content hash, with the label `grafana_dashboard: "1"` and with the annotation `grafana_folder: "dan-petty/devops-cli"`. `k8s/monitoring/dashboards/kustomization.yaml` SHALL list `../../devops/dashboards`, so Application `monitoring` and `kubectl apply -k k8s/monitoring` apply the ConfigMap.

#### Scenario: The generators of the dashboards
- **WHEN** a test reads the dashboards kustomization of `k8s/monitoring` and each kustomization that it lists
- **THEN** the generators make the same ConfigMaps, with the same files, namespace and labels, as one generator for each group, and `grafana-devops-cli-dashboards` comes from `k8s/devops/dashboards`

### Requirement: Application devops does not own the product dashboards
Neither `k8s/devops/kustomization.yaml` nor the overlay of Application `devops` SHALL reach `k8s/devops/dashboards`, because then two Applications own one ConfigMap and sync it in turn.

#### Scenario: Application devops leaves the ConfigMap to Application monitoring
- **WHEN** a test follows the resources of `k8s/overlays/homelab/devops`
- **THEN** it reaches `k8s/devops` and does not reach `k8s/devops/dashboards`

### Requirement: The product alert rules have their own values file
The product rule file `k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold, under `serverFiles.devops_cli_alerting_rules.yml`, each rule group that selects a `devops_cli_` series and the four `slo-` groups of this change, and no group of the environment values file SHALL select a `devops_cli_` series.

#### Scenario: The product file holds the groups that watch a devops_cli series
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, the product file holds each group that selects a `devops_cli_` series and the four `slo-` groups, and no group of the environment values file selects one

### Requirement: The server loads the product rule file
`serverFiles.prometheus.yml.rule_files` of `k8s/monitoring/prometheus-values.yaml` SHALL name the 4 rule files of the chart and `/etc/config/devops_cli_alerting_rules.yml`. Application `prometheus` SHALL give the chart the product file after the environment values. A group name SHALL be unique over the rule files that the server loads, and promtool SHALL accept each file.

#### Scenario: The server loads both rule files
- **WHEN** a test reads both values files
- **THEN** `rule_files` is `/etc/config/recording_rules.yml`, `/etc/config/alerting_rules.yml`, `/etc/config/rules`, `/etc/config/alerts` and `/etc/config/devops_cli_alerting_rules.yml`, and the files with groups are `alerting_rules.yml` and `devops_cli_alerting_rules.yml`

### Requirement: The shared row work series have a recording group
The group `roadmap-service-recording` of `serverFiles.devops_cli_alerting_rules.yml` SHALL hold one recording rule for each covered row work selector: the failed jobs of the last hour, the budget used ratio and the suspended rows. Each rule SHALL select `job=~"roadmap-service|roadmap-.+"`.

#### Scenario: The recording group holds one rule for each covered selector
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, and a covered selector with no rule, a fourth rule, or a rule whose matcher is not `job=~"roadmap-service|roadmap-.+"` fails the check

#### Scenario: Each rule carries its own name and expression
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, the failed jobs rule is `repo_lane_row:devops_cli_service_jobs_total:increase1h` and keeps the `result` label, the suspended rows rule is `repo_row_class:devops_cli_service_job_suspended:max`, and the budget rule is `service:devops_cli_service_budget_requests_per_limit:ratio` and divides the sum of `devops_cli_service_budget_spent_requests` by the sum of `devops_cli_service_budget_limit_requests`

### Requirement: A recording rule name has three parts
Each `record` value of the product rule file SHALL have the form `level:metric:operations`, with exactly two colons and no empty or non-identifier part. A ratio SHALL name its two metrics with `_per_` and its operation `ratio`.

#### Scenario: The check parses each record name
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, and a record value without exactly two colons or with an empty or non-identifier part fails the check

### Requirement: A recording rule is not an alert
The alert-rule checks of the monitoring tests SHALL count only the rules that hold an `alert` key, so a recording rule needs no severity, no row in the Alerting table and no `alert_rule_test` case.

#### Scenario: The alert checks skip a recording rule
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, and a recording rule that reaches the alert-rule list or the baseline rule set fails the check

### Requirement: The monitoring tests count each recorded series as served
`SERVED_SERIES` SHALL hold each `record` name of every group of the product rule file, including the four `slo-` groups, and each metric that their rules select.

#### Scenario: A recorded series that nothing serves fails
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, and a record name or a selected metric outside `SERVED_SERIES` fails the check

### Requirement: The recording cases stay within the rounds bound
The promtool test file of `roadmap-service-recording` SHALL hold a `promql_expr_test` case for each of its recording rules, and each case SHALL end within `MAX_PROMTOOL_ROUNDS` rounds of its group.

#### Scenario: The cases of the recording group pass
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, each record value has a case, and a case that evaluates more rounds than `MAX_PROMTOOL_ROUNDS` fails the check

### Requirement: One Sloth spec for each SLO of the product
The product SHALL hold one Sloth `prometheus/v1` spec under `k8s/devops/monitoring/slos/` for each of the four SLOs, and each spec SHALL name a service that the catalog data holds, the objective of its SLO and the 28-day window.

#### Scenario: Each SLO has one spec
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command exits 0, the four specs of the folder each name a service of the catalog data, and each holds the objective of its SLO and the 28-day window

#### Scenario: A spec with a service outside the catalog fails
- **WHEN** a spec names a service that the catalog data does not hold and `uv run devops ci --check --only k8s` runs
- **THEN** the command exits 1 and names the spec file and the service that the catalog data does not hold

### Requirement: The SLO rule groups are the output of the renderer
The four `slo-` groups of the product rule file SHALL equal the render of the specs, the `k8s` row MUST fail when a spec changes and the groups are not rendered again, and `SERVED_SERIES` SHALL hold each record name of the four groups.

#### Scenario: A changed spec with no new render fails
- **WHEN** a spec changes with no new render and `uv run devops ci --check --only k8s` runs
- **THEN** the command exits 1 and prints the difference between the four `slo-` groups and the render of the specs

#### Scenario: Each SLO has its recording rules
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, and each of the four groups holds its seven error-ratio rules, its objective rule, its error-budget rule and its window rule

### Requirement: Each burn-rate alert needs 20 events in its long window
Each burn-rate alert of the four SLOs SHALL require at least 20 events in its long window, and SHALL hold the long window, the short window, the burn rate and the severity of its row of Table 2 of the SRE guideline.

#### Scenario: A quiet row fires no page alert
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs a case of fewer than 20 events in the 1-hour and the 6-hour long windows at a burn rate above the page line
- **THEN** the command exits 0 and the case shows no page alert for that row

#### Scenario: The ticket windows see a low-traffic row
- **WHEN** the command runs a case of at most 5 events in the last hour and at least 20 events in the 1-day window at a burn rate above the ticket line
- **THEN** the command exits 0, the 1-day and the 3-day ticket alerts fire, and the two page alerts stay quiet

#### Scenario: Fewer than 20 events in the long window fires no alert
- **WHEN** the command runs a case of fewer than 20 events in the long window of every row
- **THEN** the command exits 0 and no alert of the SLO fires

### Requirement: One promtool case file for each SLO
`promtool check rules` and `promtool test rules` MUST pass on the four SLO groups, with one case file for each SLO, and each case MUST end within the rounds bound of the monitoring tests.

#### Scenario: Each SLO has a case file
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, `promtool check rules` and `promtool test rules` exit 0, and each alert of the four groups has a case

#### Scenario: A case of days keeps its short window
- **WHEN** the command runs the case of a 1-day or a 3-day long window
- **THEN** the command exits 0, the file evaluates its rules each 5 minutes, each case samples each minute, the 5-minute short window holds five samples, and the case ends within the rounds bound

### Requirement: One place for each SLO objective
The four SLO rows of the Service levels section of `k8s/README.md` that this change covers SHALL name the spec of each SLO and hold no objective and no window, and the SLO 5 row SHALL keep its objective until its own spec holds it.

#### Scenario: Each objective has one place
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command exits 0, each of the four SLO rows of this change names its spec, none of the four holds an objective percentage or a window, and the SLO 5 row keeps its objective

### Requirement: A runbook row for each SLO alert
The Alerting table of `k8s/README.md` SHALL give a row for each alert of the four SLO groups, and each row SHALL render every cell of the header.

#### Scenario: Each SLO alert has a row
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command exits 0, and each alert name of the four `slo-` groups has a row with the four cells
