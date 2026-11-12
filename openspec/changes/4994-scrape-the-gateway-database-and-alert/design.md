# Design

## Decisions

- **The PodMonitor is in `k8s/llm/gateway-db.yaml`.** deploy-stack applies that file after the Helm releases, and `prometheus-operator-crds` is one of them, so the PodMonitor needs no new row in `POST_HELM_BY_STACK`. Argo CD's `llm` Application applies it with the Cluster.
- **The scrape rule admits the namespace `monitoring` on 9187 only**, the form of the Mattermost database policy. Port 5432 stays closed to `monitoring`.
- **The rules select the pods of the Cluster by `namespace` and `pod`.** The Mattermost database sends the same series, and Alloy writes its own `cluster` label on each series that has no `cluster` label, so `cluster` names the Cluster only on `cnpg_collector_up`.
- **Each rule is for each instance, and the Cluster has one.** The connection and size rules group by `namespace` and `pod`. CloudNativePG gives the claim of an instance the name of its pod, so `label_replace` turns `persistentvolumeclaim` into `pod`. `max by` keeps one claim series when a second kube-state-metrics sends it, as on 2026-10-01.
- **All three rules are warnings.** While the database is down, the gateway refuses only the virtual keys. The master key needs no database, so the cluster Jobs, the CLI and Open WebUI keep working (k8s/README.md, Gateway database). `MattermostDatabaseDown` is a warning for the same kind of fault.
- **The size rule adds the WAL to the databases.** `pg_database_size` does not count `pg_wal`, and the WAL is on the same volume. local-path does not enforce the size of a claim, so the rule compares the data with the claim, and `LocalPathNodeDiskHigh` watches the root disk under it.
- **80% for connections and size.** It is the threshold of `ValkeyMemoryNearBound` and `PrometheusStorageNearClaim`. PostgreSQL keeps `superuser_reserved_connections` (3 of 100) for the superuser, so a client sees the limit at 97%.
- **The dashboard is a copy of the upstream file with two changes.** One space of indentation keeps its ConfigMap under the last-applied annotation, and a reader gets the upstream layout back by doubling it. The empty Prometheus target of the replication lag stat is removed: Grafana skips an empty query, and the linter refuses it. docs/DESIGN.md keeps an upstream dashboard as it is published, so no color or unit changes.
- **The chart's dashboard ConfigMap turns off.** It is in `cnpg-system`, where the sidecar does not look, and it has the same uid `cloudnative-pg`. One source of the dashboard stays.
- **The linter reads `expression` for a target of the `__expr__` datasource.** Grafana evaluates such a target on the server from the other targets of the panel; it has no `expr`. An empty expression is still an error. The field is `None` by default, so a generated dashboard has no `expression` key.
- **30 days of spend logs.** No code reads the table: the AI spend dashboard reads Prometheus (#4578), and the Service counts in its own store (#3066). The daily rollups that the LiteLLM UI reads are other tables, which the cleanup does not touch.

## Rejected alternatives

- **The chart option `monitoring.grafanaDashboard.namespace: monitoring`.** The Application `cloudnative-pg` would own a ConfigMap in the namespace of the Application `monitoring`, and the linter and the dashboard tests read only `k8s/monitoring/dashboards/`.
- **A file `cloudnative-pg.json.url` that the sidecar downloads.** Grafana would then load a dashboard that no review saw, from the network, at each start.
- **The dashboard with 2-space indentation in a ConfigMap of its own.** The ConfigMap is 283,726 bytes, over the 262,144 bytes of the last-applied annotation, so `kubectl apply -k` in deploy-stack refuses it (`tests/prometheus/test_k8s_monitoring_dashboards.py`).
- **Minified JSON.** It fits (148,385 bytes), but each change is one line in a diff.
- **A critical `GatewayDatabaseDown`.** The master key works without the database, so no AI work stops.
