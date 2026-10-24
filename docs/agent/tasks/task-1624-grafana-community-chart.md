# Task: Grafana moves to the grafana-community chart on a Grafana 13 release that fixes CVE-2026-76154, and provisioning prunes removed datasources (#1624)

**Issue**: [#1624](https://github.com/dan-petty/devops-cli/issues/1624)
**Scope**: scope/k8s
**Feasibility**: Confirmed on 2026-10-23 against the chart indexes, the Grafana advisories, the Grafana v13.2.4 source and the live cluster (read-only). `grafana/grafana` 10.5.15 is the last entry in grafana.github.io/helm-charts and has `deprecated: true`; it runs Grafana 12.3.1, which the cluster runs. The grafana.com advisory for CVE-2026-76154 (High, 7.3) gives the fixed versions `>=12.4.11 <13.0.0`, `>=13.0.9 <13.1.0`, `>=13.1.6 <13.2.0` and `>=13.2.2`. The advisory for CVE-2026-17033 (Medium, 6.8) gives `>=13.1.0`. Grafana 13.2.4 is the latest Grafana release. In grafana-community/helm-charts, charts 13.5.1 to 14.0.1 run Grafana 13.2.4. The Grafana source shows that `prune: true` deletes only datasources that have `is_prunable` set, and Grafana sets it when it provisions a datasource from a file with `prune: true`. The Jaeger datasource left the file before `prune` was set, so `prune` does not delete it.

## Description

The `grafana` release moves from `grafana/grafana` 10.5.15 to `grafana-community/grafana` 14.0.1, which runs Grafana 13.2.4. The release name, the namespace and the `grafana` PVC do not change, so the dashboards, users, service accounts and tokens in the Grafana database stay on the same volume.

Chart 14.0.1 is the latest chart. It runs the same Grafana as 13.7.0, and the chart repository publishes new Grafana patch releases only on its latest major version. Chart 14.0.0 added only a values schema, and Helm validates `grafana-values.yaml` against it without errors. The Argo CD repo-server runs Helm v4.2.1, which reads the draft-07 schema.

`helm template` of 10.5.15 and 14.0.1 with the repository values gives the same twelve objects. These are the differences that the new chart makes:

- The Grafana container runs `grafana:13.2.4-distroless` with `readOnlyRootFilesystem: true` and an `emptyDir` on `/tmp`. The values set no `GF_*__FILE` variable and no `GF_INSTALL_PLUGINS`, which the distroless image does not support. The admin credentials come from Secret `grafana-admin` through `secretKeyRef`.
- The dashboard sidecar moves to `k8s-sidecar` 2.14.1, and the dashboard download init container moves to `curl` 8.23.0. Both get `readOnlyRootFilesystem: true`.
- `GOMEMLIMIT` is a fixed `921MiB` (90% of the 1024Mi limit).
- `grafana.ini` gets `[plugins] preinstall_auto_update = false`. The chart sets this so that Grafana 13 does not try to replace bundled plugins on the read-only image path (grafana-community/helm-charts PR 791). The four preinstalled app plugins on the volume stay at their 2.x versions. Each declares `grafanaDependency` `>=12.2.5-0`, which includes 13.2.4.
- The PVC keeps its name, size, storage class and the `Prune=false,Delete=false` sync options. Only its chart labels change.

Grafana 13 migrates dashboards and folders to unified storage at its first start. Grafana 12 cannot read the result, so a rollback needs the database copy from before the upgrade. The Grafana upgrade guide names `database is locked` errors for SQLite during this migration. Grafana keeps its data in SQLite, and the chart's default rolling update runs the old and the new pod on one database file. The values now set `deploymentStrategy.type: Recreate`, so the old pod stops before the new pod opens the database. `kubectl diff` against the live Deployment accepts the change and removes the old `rollingUpdate` block.

The datasource provisioning file sets `prune: true`. From the next start, Grafana deletes each provisioned datasource that the file no longer lists.

## Acceptance Criteria

- [x] `k8s/argocd/apps/grafana.yaml` installs chart `grafana` 14.0.1 from `https://grafana-community.github.io/helm-charts`, the `homelab` project admits that repository, and deploy-stack installs `grafana-community/grafana` 14.0.1 from the same repository: `test_grafana_runs_the_grafana_community_chart_that_ships_a_patched_grafana`.
- [x] The datasource provisioning file sets `prune: true`: `test_grafana_provisioning_deletes_a_datasource_that_leaves_the_file`.
- [x] The Grafana Deployment uses the `Recreate` strategy while Grafana keeps its data in SQLite on its volume: `test_grafana_stops_the_old_pod_before_the_new_pod_opens_its_sqlite_database`.
- [x] The Prometheus datasource keeps `jsonData.timeInterval: 60s` (#1955): `test_grafana_rate_windows_hold_two_samples_at_the_scrape_interval`.
- [x] `helm template` of chart 14.0.1 with the values renders the PVC `grafana`, Secret reference `grafana-admin`, the dashboard sidecar and the datasource uids `prometheus`, `loki`, `tempo`, `pyroscope` and `alertmanager`. `kubectl diff -n monitoring` of the render against the cluster gives no error.
- Pending a person: before the merge, back up the Grafana database, because Argo CD syncs `main` at once and the migration cannot be undone. Run `kubectl -n monitoring cp -c grafana "$(kubectl -n monitoring get pod -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}')":/var/lib/grafana/grafana.db <backup-dir>/grafana-$(date +%Y%m%d-%H%M%S).db`. Expect a file of approximately 4 MB. Keep it out of git: it holds password hashes and token hashes.
- Pending a person: after the sync, run `kubectl -n monitoring get deploy grafana -o jsonpath='{.spec.template.spec.containers[?(@.name=="grafana")].image}'`. Expect `docker.io/grafana/grafana:13.2.4-distroless`. Then run `devops grafana dashboards list`, and open each provisioned dashboard and the Drilldown apps in Grafana. Expect the 16 dashboards that Grafana 12.3.1 showed.
- Pending a person: delete the stale Jaeger datasource one time. Run `kubectl -n monitoring port-forward svc/grafana 8030:80`, then `curl -sS -u "admin:$(kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d)" -X DELETE http://localhost:8030/api/datasources/uid/jaeger`. Expect `Data source deleted`. Then `devops grafana datasources` lists five datasources and no uid `jaeger`.
- Pending a person: if Grafana 13 does not start, revert this commit and copy the backup to `/var/lib/grafana/grafana.db` before the Grafana 12.3.1 pod starts again.

## Deliverables

- [x] `k8s/argocd/apps/grafana.yaml`: chart source `https://grafana-community.github.io/helm-charts`, `grafana` 14.0.1.
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`: release `grafana` installs `grafana-community/grafana` 14.0.1.
- [x] `k8s/monitoring/grafana-values.yaml`: header names grafana-community, `deploymentStrategy.type: Recreate`, `prune: true` in `datasources.yaml`.
- [x] `k8s/README.md`: the directory tree names `grafana-community/grafana` for `grafana-values.yaml`.
- [x] `tests/test_k8s_monitoring_integration.py`: the three tests above.
- The four preinstalled app plugins (`grafana-lokiexplore-app`, `grafana-metricsdrilldown-app`, `grafana-pyroscope-app`, `grafana-exploretraces-app`) stay at 2.x, because the chart turns off their automatic update. Pinning their 3.x versions, which need Grafana `>=13.1.0`, in the chart's `plugins` value: moved to #2022.
