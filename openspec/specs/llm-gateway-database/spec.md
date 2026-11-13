# llm-gateway-database Specification

## Purpose
The LiteLLM gateway keeps its virtual keys in a Postgres database. This capability fixes how that database runs, how the gateway reads its connection, who may reach it, and what the gateway does while it is down.

## Requirements

### Requirement: The gateway database is a CloudNativePG Cluster whose Secret the operator generates
The manifests SHALL define a CloudNativePG `Cluster` `llm-gateway-db` in namespace `llm` with one instance on `local-path` storage, annotated so that Argo CD neither prunes nor deletes it, with superuser access off. The `Cluster` SHALL name no `bootstrap.initdb.secret` and no manifest SHALL hold a Secret for it, so that git holds no password.

#### Scenario: The Cluster keeps its data and names no secret
- **WHEN** a test reads `k8s/llm/gateway-db.yaml`
- **THEN** it holds one `Cluster` with `instances` 1, storage class `local-path`, sync option `Prune=false,Delete=false`, `enableSuperuserAccess` false and no `bootstrap.initdb.secret`, and it holds no Secret and no PersistentVolumeClaim

### Requirement: The gateway reads its connection from the operator's Secret
The gateway Deployment SHALL set `DATABASE_URL` from the `uri` key of Secret `llm-gateway-db-app` with `secretKeyRef`, and no literal value.

#### Scenario: DATABASE_URL has no literal value
- **WHEN** a test reads the gateway Deployment that Kustomize renders from `k8s/llm`
- **THEN** its container sets `DATABASE_URL` from `secretKeyRef` name `llm-gateway-db-app` and key `uri`

### Requirement: The gateway migrates on a read-only root file system
The gateway container SHALL keep `readOnlyRootFilesystem: true` and SHALL set `LITELLM_MIGRATION_DIR` to a path that an `emptyDir` volume mounts read-write. It SHALL have a `startupProbe` that allows at least ten minutes before the liveness probe starts.

#### Scenario: The migration directory is an emptyDir
- **WHEN** a test reads the gateway Deployment
- **THEN** the mount at the value of `LITELLM_MIGRATION_DIR` is not read-only and its volume is an `emptyDir`, and `readOnlyRootFilesystem` is true

#### Scenario: A migrating pod is not killed
- **WHEN** a test reads the `startupProbe` of the gateway container
- **THEN** its path is `/health/liveliness` on port 4000, and its period times its failure threshold is at least 600 seconds

### Requirement: A failed migration ends the start-up
The gateway container SHALL set `ENFORCE_PRISMA_MIGRATION_CHECK` to `"true"`, so that a failed `prisma migrate deploy` ends the process and the restart loop waits for the database, instead of a start on an empty schema.

#### Scenario: The check is on
- **WHEN** a test reads the gateway container
- **THEN** it sets `ENFORCE_PRISMA_MIGRATION_CHECK` to `"true"`

### Requirement: The readiness of the gateway does not depend on the database
The `readinessProbe` of the gateway container SHALL use `/health/liveliness` on port 4000. `/health/readiness` answers 503 while the database is down, and Kubernetes would then remove every gateway pod from the Service, also for the clients of the master key.

#### Scenario: A database outage keeps the pods in the Service
- **WHEN** a test reads the `readinessProbe` of the gateway container
- **THEN** its path is `/health/liveliness` on port 4000

### Requirement: The gateway refuses a key it cannot check
The gateway config SHALL NOT turn on `general_settings.allow_requests_on_db_unavailable`, and SHALL keep `store_model_in_db` off.

#### Scenario: The defaults hold
- **WHEN** a test reads `general_settings` of `k8s/llm/gateway/config.yaml`
- **THEN** `allow_requests_on_db_unavailable` is absent or false, and `store_model_in_db` is false

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

### Requirement: A gateway rollout lets the old pod finish its open calls
The gateway pod SHALL set `terminationGracePeriodSeconds` to 600, which is shorter than the router timeout of the gateway config. The gateway Deployment SHALL use a rolling update, so the new pod starts before the old pod stops.

#### Scenario: The rendered gateway pod waits 600 s for its open calls
- **WHEN** Kustomize renders `k8s/llm`
- **THEN** the pod template of Deployment `llm-gateway` sets `terminationGracePeriodSeconds: 600`
- **AND** 600 is less than `router_settings.timeout` of `k8s/llm/gateway/config.yaml`
- **AND** the Deployment sets no strategy other than `RollingUpdate`

### Requirement: A restart of the gateway database waits 15 s for open sessions
The CloudNativePG Cluster `llm-gateway-db` SHALL set `smartShutdownTimeout` to 15, which is less than its `stopDelay`.

#### Scenario: The Cluster limits the smart shutdown to 15 s
- **WHEN** the check reads the Cluster of `k8s/llm/gateway-db.yaml`
- **THEN** it sets `smartShutdownTimeout: 15`
- **AND** 15 is less than its `stopDelay`, or less than 1800 when it sets none

### Requirement: One slow request does not fail a probe of the gateway
The startup, liveness and readiness probes of the gateway container SHALL each set `timeoutSeconds` to 5, which is shorter than the period of the probe.

#### Scenario: Each probe of the rendered gateway waits 5 s
- **WHEN** Kustomize renders `k8s/llm`
- **THEN** the `startupProbe`, `livenessProbe` and `readinessProbe` of the gateway container each set `timeoutSeconds: 5`
- **AND** each timeout is less than the `periodSeconds` of its probe
