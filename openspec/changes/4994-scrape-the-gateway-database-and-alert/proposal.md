# Proposal: #4994

## Why

Issue #4994: the gateway refuses each virtual key while its database is down, and nothing measures that database. `kubectl get podmonitor -A` lists only the operator and `mattermost-db`, so `cnpg_collector_up` exists only for the Mattermost database. Policy `llm-gateway-db-perimeter` closes port 9187 to `monitoring`. The spend-log table gets about 71,000 rows a week with no limit, and the claim is 5 GiB. The operator chart makes the CloudNativePG dashboard, but in `cnpg-system`, where the Grafana sidecar does not look.

## What Changes

- `k8s/llm/gateway-db.yaml` gets PodMonitor `llm-gateway-db` (the pods of the Cluster, port `metrics`), and `llm-gateway-db-perimeter` admits namespace `monitoring` on TCP 9187. The egress of `monitoring-default-perimeter` to namespace `llm` admits 9187.
- `k8s/monitoring/prometheus-values.yaml` gets group `llm-gateway-db` with three warning rules: `GatewayDatabaseDown` (the exporter has no connection or no series, 5 minutes), `GatewayDatabaseConnectionsNearMax` (client connections above 80% of `max_connections`, 10 minutes) and `GatewayDatabaseNearClaim` (the databases and the WAL above 80% of the claim, 15 minutes). `tests/fixtures/prometheus_rules/llm_gateway_db_tests.yaml` holds their promtool cases.
- `k8s/monitoring/dashboards/cloudnative-pg.json` is the upstream CloudNativePG dashboard (Apache-2.0), in its own ConfigMap `grafana-database-dashboards`. It shows `llm-gateway-db` and `mattermost-db`. The chart's own dashboard ConfigMap turns off (`monitoring.grafanaDashboard.create: false`).
- `general_settings.maximum_spend_logs_retention_period` is `30d` in `k8s/llm/gateway/config.yaml`.
- `devops grafana dashboards lint` reads a target of the Grafana expression datasource (`__expr__`) by its `expression`, and no longer reports it as an empty query.
- `k8s/README.md` describes the scrape, the rules, the dashboard and the retention.
- Manifests and a command change, so the change has spec deltas: `llm-gateway-database` and the new capability `grafana-dashboard-lint`.

The change fits one pull request.

## Capabilities

- `llm-gateway-database`: modified (the database perimeter admits the scrape), and added (the scrape, the rules, the dashboard, the spend-log retention).
- `grafana-dashboard-lint`: new (an expression target is checked by its expression).

## Impact

- Files: `k8s/llm/gateway-db.yaml`, `k8s/llm/gateway/config.yaml`, `k8s/monitoring/networkpolicy.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/`, `k8s/mattermost/cloudnative-pg-values.yaml`, `src/devops_cli/grafana/`, `src/devops_cli/config/constants.py`, `k8s/README.md` and their tests.
- After the merge, Argo CD applies the PodMonitor, the policies, the rules and the dashboard, and prunes the chart's dashboard ConfigMap in `cnpg-system`. The changed gateway config restarts the gateway pod with no downtime (one replica, `maxSurge` 1). The first deletion of old spend logs runs one day after the start.

## Feasibility

- The cluster runs CloudNativePG 1.30.1 (`kubectl get deploy -n cnpg-system`: `ghcr.io/cloudnative-pg/cloudnative-pg:1.30.1`, chart 0.29.1). Pod `llm-gateway-db-1` has the container port `metrics` 9187 (`kubectl get pods -n llm -l cnpg.io/cluster=llm-gateway-db`). Since 1.26 CloudNativePG asks for a PodMonitor that the user makes, not `.spec.monitoring.enablePodMonitor`, which is what `k8s/mattermost/podmonitor.yaml` does.
- Prometheus has `cnpg_collector_up`, `cnpg_backends_total`, `cnpg_pg_settings_setting{name="max_connections"}`, `cnpg_pg_database_size_bytes` and `cnpg_collector_pg_wal{value="size"}` for `mattermost-db`, each with `namespace` and `pod`. Alloy puts its own `cluster` label on each series that has none, so the rules select by `namespace` and `pod`. `kube_persistentvolumeclaim_resource_requests_storage_bytes{persistentvolumeclaim="llm-gateway-db-1"}` is 5,368,709,120.
- The gateway runs `ghcr.io/berriai/litellm:v1.103.10`. At that tag, `initialize_scheduled_background_jobs` in `litellm/proxy/proxy_server.py` schedules `SpendLogCleanup.cleanup_old_spend_logs` when `maximum_spend_logs_retention_period` is set, once each `maximum_spend_logs_retention_interval` (default `1d`), with no check of an enterprise license. `spend_log_cleanup.py` parses the value with `duration_in_seconds`, which reads `30d`.
- The upstream dashboard is `charts/cluster/grafana-dashboard.json` of `cloudnative-pg/grafana-dashboards` at commit `7dd1bc255b5202530e1bae7b858a3bb41a2028c7` (the last commit of that file, 2026-07-23). Its variables read `cnpg_collector_up`, whose `cluster` label the exporter sets, and its panels select by `namespace` and `pod`. `devops grafana dashboards lint` reported two errors on it: an empty Prometheus target in the replication lag stat, and a target of the expression datasource, which has `expression` and no `expr`.
- As published (2-space indentation), its ConfigMap is 283,726 bytes, over kubectl's 262,144-byte last-applied annotation. With 1-space indentation it is 228,712 bytes.

## Existing Tool Considered

- The CloudNativePG metrics exporter, the Prometheus Operator PodMonitor that Alloy reads, the upstream CloudNativePG dashboard, promtool, and the spend-log retention of LiteLLM cover the need. No new tool is built.
- The chart option `monitoring.grafanaDashboard.namespace` could write the chart's dashboard to `monitoring`. It is not used: the Application `cloudnative-pg` would then own an object in the namespace of the Application `monitoring`, and the dashboard tests and the linter of the repository would not see it.
- Internal code deleted: none. The linter change is 3 lines.
