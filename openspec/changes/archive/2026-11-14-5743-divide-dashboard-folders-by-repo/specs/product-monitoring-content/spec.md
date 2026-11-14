## MODIFIED Requirements

### Requirement: The product dashboards have their own generator
`k8s/devops/dashboards/kustomization.yaml` SHALL generate the ConfigMap `grafana-devops-cli-dashboards` in namespace `monitoring` from `devops-cli.json`, `ai-spend.json` and `project-metrics.json`, with no content hash, with the label `grafana_dashboard: "1"` and with the annotation `grafana_folder: "dan-petty/devops-cli"`. `k8s/monitoring/dashboards/kustomization.yaml` SHALL list `../../devops/dashboards`, so Application `monitoring` and `kubectl apply -k k8s/monitoring` apply the ConfigMap.

#### Scenario: The generators of the dashboards
- **WHEN** a test reads the dashboards kustomization of `k8s/monitoring` and each kustomization that it lists
- **THEN** the generators make the same ConfigMaps, with the same files, namespace and labels, as one generator for each group, and `grafana-devops-cli-dashboards` comes from `k8s/devops/dashboards`
