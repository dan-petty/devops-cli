## MODIFIED Requirements

### Requirement: Only the gateway and the operator reach the database
Policy `llm-gateway-db-perimeter` SHALL admit to the database pods on 5432 only the gateway's pods and the CloudNativePG operator (which also uses 8000). It SHALL admit namespace `monitoring` on the metrics port 9187 only, and its egress SHALL be DNS and the Kubernetes API only. The gateway's policy SHALL admit egress to the database pods on 5432 by pod selector. `llm-default-perimeter` SHALL leave the database pods out.

#### Scenario: The database perimeter
- **WHEN** a test reads `llm-gateway-db-perimeter`
- **THEN** it selects the pods with `cnpg.io/cluster: llm-gateway-db`, its ingress peers are the pods of `llm-gateway` (5432), namespace `cnpg-system` (8000 and 5432) and namespace `monitoring` (9187), and its egress rules cover ports 53 and ports 443 and 6443

#### Scenario: The gateway reaches the database by label
- **WHEN** a test reads `llm-gateway-perimeter`
- **THEN** exactly one egress rule names TCP 5432, and its peer is a pod selector on `cnpg.io/cluster: llm-gateway-db`

#### Scenario: The default perimeter leaves the database out
- **WHEN** a test reads `llm-default-perimeter`
- **THEN** its pod selector excludes pods with `cnpg.io/cluster: llm-gateway-db`

## ADDED Requirements

### Requirement: Alloy scrapes the metrics exporter of the gateway database
`k8s/llm/gateway-db.yaml` SHALL hold PodMonitor `llm-gateway-db` in namespace `llm`, which selects the pods with `cnpg.io/cluster: llm-gateway-db` on their port `metrics`. k8s-monitoring SHALL read PodMonitors, and the egress of `monitoring-default-perimeter` to namespace `llm` SHALL admit TCP 9187.

#### Scenario: The PodMonitor and the egress
- **WHEN** a test reads `k8s/llm/gateway-db.yaml`, `k8s/monitoring/k8s-monitoring-values.yaml` and `k8s/monitoring/networkpolicy.yaml`
- **THEN** the PodMonitor `llm-gateway-db` selects `cnpg.io/cluster: llm-gateway-db` with the one endpoint port `metrics`, `prometheusOperatorObjects.enabled` is true, and an egress rule to namespace `llm` names port 9187

### Requirement: Rules warn on the gateway database
Group `llm-gateway-db` of the alerting rules SHALL hold the warning rules `GatewayDatabaseDown`, `GatewayDatabaseConnectionsNearMax` and `GatewayDatabaseNearClaim` over the pods of the Cluster in namespace `llm`. Each rule SHALL have promtool cases, and a row in the Alerting table of `k8s/README.md`.

#### Scenario: The exporter is down
- **WHEN** promtool gives the group a `cnpg_collector_up` of 0 for `llm-gateway-db-1`, or no series of it, for 5 minutes
- **THEN** `GatewayDatabaseDown` fires, and a value of 1 keeps it quiet

#### Scenario: The connections near the limit
- **WHEN** promtool gives the group client connections of `llm-gateway-db-1` above 80% of `max_connections` for 10 minutes
- **THEN** `GatewayDatabaseConnectionsNearMax` fires, and 50% keeps it quiet

#### Scenario: The data nears the claim
- **WHEN** promtool gives the group databases and WAL of `llm-gateway-db-1` above 80% of the claim `llm-gateway-db-1` for 15 minutes
- **THEN** `GatewayDatabaseNearClaim` fires, and the same series of the Mattermost database fire no rule

#### Scenario: The rules select the gateway database only
- **WHEN** a test reads the group
- **THEN** each CloudNativePG selector names `namespace="llm"` and `pod=~"llm-gateway-db-[0-9]+"`, and the claim selector names `persistentvolumeclaim=~"llm-gateway-db-[0-9]+"`

### Requirement: Grafana provisions the CloudNativePG dashboard
`k8s/monitoring/dashboards/cloudnative-pg.json` SHALL be the upstream CloudNativePG dashboard, in the generated ConfigMap `grafana-database-dashboards`, and SHALL pass `devops grafana dashboards lint` with no error. The operator chart SHALL NOT make its own dashboard ConfigMap.

#### Scenario: The dashboard is provisioned once
- **WHEN** a test reads the dashboards kustomization and `k8s/mattermost/cloudnative-pg-values.yaml`
- **THEN** ConfigMap `grafana-database-dashboards` holds `cloudnative-pg.json` under the annotation limit, and `monitoring.grafanaDashboard.create` is false

### Requirement: The gateway keeps its spend logs for 30 days
`general_settings.maximum_spend_logs_retention_period` SHALL be `30d` in `k8s/llm/gateway/config.yaml`, with the default daily interval.

#### Scenario: The retention holds
- **WHEN** a test reads `general_settings` of `k8s/llm/gateway/config.yaml`
- **THEN** `maximum_spend_logs_retention_period` is `30d`, and `maximum_spend_logs_retention_interval` is absent
