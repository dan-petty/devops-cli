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
`k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold only `serverFiles.devops_cli_alerting_rules.yml`, with the rule groups `roadmap-service`, `roadmap-service-recording`, `roadmap-service-webhooks`, `roadmap-service-activity`, `roadmap-service-items`, `roadmap-service-tools`, `crawl4ai`, `research`, `ai-spend` and `rag-ingest`. Each group that selects a `devops_cli_` series SHALL be in this file, and no environment group SHALL select one.

#### Scenario: The product file holds the groups that watch a devops_cli series
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, the product file holds the 10 product groups, each selects a `devops_cli_` series, and no group of the environment values file selects one

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
`SERVED_SERIES` SHALL hold each `record` name of `roadmap-service-recording` and each metric that its rules select.

#### Scenario: A recorded series that nothing serves fails
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, and a record name or a selected metric outside `SERVED_SERIES` fails the check

### Requirement: The recording cases stay within the rounds bound
The promtool test file of `roadmap-service-recording` SHALL hold a `promql_expr_test` case for each of its recording rules, and each case SHALL end within `MAX_PROMTOOL_ROUNDS` rounds of its group.

#### Scenario: The cases of the recording group pass
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, each record value has a case, and a case that evaluates more rounds than `MAX_PROMTOOL_ROUNDS` fails the check
