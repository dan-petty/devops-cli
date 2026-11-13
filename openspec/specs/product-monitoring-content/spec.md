# product-monitoring-content Specification

## Purpose
Where the monitoring content of the devops-cli product lives: the Grafana dashboards and the Prometheus alert rules that read the `devops_cli_*` series. The product content is apart from the environment content of `k8s/monitoring/`, so that the environment can move to its own repository and leave the product content in devops-cli.

## Requirements

### Requirement: The product dashboards have their own generator
`k8s/devops/dashboards/kustomization.yaml` SHALL generate the ConfigMap `grafana-devops-cli-dashboards` in namespace `monitoring` from `devops-cli.json`, `ai-spend.json` and `project-metrics.json`, with no content hash and with the label `grafana_dashboard: "1"`. `k8s/monitoring/dashboards/kustomization.yaml` SHALL list `../../devops/dashboards`, so Application `monitoring` and `kubectl apply -k k8s/monitoring` apply the ConfigMap.

#### Scenario: The generators of the dashboards
- **WHEN** a test reads the dashboards kustomization of `k8s/monitoring` and each kustomization that it lists
- **THEN** the generators make the same ConfigMaps, with the same files, namespace and labels, as one generator for each group, and `grafana-devops-cli-dashboards` comes from `k8s/devops/dashboards`

### Requirement: Application devops does not own the product dashboards
Neither `k8s/devops/kustomization.yaml` nor the overlay of Application `devops` SHALL reach `k8s/devops/dashboards`, because then two Applications own one ConfigMap and sync it in turn.

#### Scenario: Application devops leaves the ConfigMap to Application monitoring
- **WHEN** a test follows the resources of `k8s/overlays/homelab/devops`
- **THEN** it reaches `k8s/devops` and does not reach `k8s/devops/dashboards`

### Requirement: The product alert rules have their own values file
`k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold only `serverFiles.devops_cli_alerting_rules.yml`, with the rule groups `roadmap-service`, `roadmap-service-webhooks`, `roadmap-service-activity`, `roadmap-service-items`, `roadmap-service-tools`, `crawl4ai`, `research`, `ai-spend` and `rag-ingest`. Each group that selects a `devops_cli_` series SHALL be in this file, and no environment group SHALL select one.

#### Scenario: The product file holds the groups that watch a devops_cli series
- **WHEN** a test reads the groups of both values files
- **THEN** the product file holds the 9 product groups, each selects a `devops_cli_` series, and no group of `k8s/monitoring/prometheus-values.yaml` selects one

### Requirement: The server loads the product rule file
`serverFiles.prometheus.yml.rule_files` of `k8s/monitoring/prometheus-values.yaml` SHALL name the 4 rule files of the chart and `/etc/config/devops_cli_alerting_rules.yml`. Application `prometheus` SHALL give the chart the product file after the environment values. A group name SHALL be unique over the rule files that the server loads, and promtool SHALL accept each file.

#### Scenario: The server loads both rule files
- **WHEN** a test reads both values files
- **THEN** `rule_files` is `/etc/config/recording_rules.yml`, `/etc/config/alerting_rules.yml`, `/etc/config/rules`, `/etc/config/alerts` and `/etc/config/devops_cli_alerting_rules.yml`, and the files with groups are `alerting_rules.yml` and `devops_cli_alerting_rules.yml`
