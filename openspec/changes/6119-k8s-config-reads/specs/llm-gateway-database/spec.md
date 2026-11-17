## MODIFIED Requirements

### Requirement: Grafana provisions the CloudNativePG dashboard
`k8s/monitoring/dashboards/cloudnative-pg.json` SHALL be the upstream CloudNativePG dashboard, in the generated ConfigMap `grafana-database-dashboards`, and SHALL pass `devops grafana dashboards lint` with no error. The operator chart SHALL NOT make its own dashboard ConfigMap.

#### Scenario: The dashboard is provisioned once
- **WHEN** a person runs `kubectl get configmap -A -l grafana_dashboard=1` on the cluster
- **THEN** only ConfigMap `grafana-database-dashboards` holds `cloudnative-pg.json`
