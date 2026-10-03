# Task 550: Logs and Metrics Are Kept for 30 Days

**Issue**: [#550](https://github.com/dan-petty/devops-cli/issues/550)
**Status**: Done
**Milestone**: `v0.2.25`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

The owner decided on 2026-10-03 that homelab logs and metrics are kept for 30 days. Loki's retention is enforced by the compactor, and its volume holds 30 days of pod logs plus the host journals #1080 adds, with headroom. Prometheus keeps 30 days by time, and its size cap must not cut history short once #1080's host series land.

Before this change:

- Loki never deleted logs by age. `limits_config.retention_period: 720h` was set, but `compactor.retention_enabled` was off, so the compactor never applied it. `loki_compactor_apply_retention_last_successful_run_timestamp_seconds` was `0`, and a 2Gi volume held logs going back to the volume's creation.
- Prometheus kept 30 days by time on a 20Gi volume (#738), with no size cap.
- No alert watched either volume.

## 2. Measurements (2026-10-03, read-only)

Taken through the Kubernetes API service proxy, Grafana's Prometheus and Loki datasources, and `du` in the Prometheus and node-exporter pods.

| What | Measured | Source |
| :--- | :--- | :--- |
| Pod logs into Loki | 0.5 to 1.3 GB per UTC day from 2026-09-30 on, when Loki went from 6 streams to about 170; 1.31 GB on the busiest day (2026-10-02), 0.65 GB on 2026-10-01; 0.82 GB in the last 24 h; 0.93 GB a day by `loki_distributor_bytes_received_total` (417.6 MB in 10.8 h since Loki's last restart) | `/loki/api/v1/index/stats?query={service_name=~".+"}` per UTC day (8.69 GB from 2026-09-12 on), Loki `/metrics` |
| Loki's volume | 0.79 GB of chunks hold 8.7 GB of logs (2026-09-12 to now), about 11:1; the TSDB index is under 1 MB | `du` through node-exporter's read-only host mount, index stats summed per day |
| Loki's retention | `retention_enabled: false`, `delete_request_store: ""`; last retention run `0` while compaction runs every 10 minutes | Loki `/config`, `/metrics` |
| Host journals (#1080's input) | Journal files grow 7 to 15 MB a day per node, about 40 MB a day in all, every unit at every priority. This is an estimate of what #1080 will send: it is file growth on disk, not bytes pushed to Loki | `du` and file dates of the host journal directory, through node-exporter |
| Prometheus TSDB | 0.59 GB on the volume after 3.1 days: 464 MB of blocks, 110 MB of WAL. Blocks grew 0.157 GB a day on average, including the redeploy and power-loss days when head series rose from about 50,000 to between 150,000 and 354,000 | `du /data`, `prometheus_tsdb_storage_blocks_bytes`, `prometheus_tsdb_wal_storage_size_bytes`, `prometheus_tsdb_head_series` |
| Prometheus ingest | 868 samples/s over a day, 917 over the last hour; 1.02 bytes a sample after compaction; 63,797 head series | `prometheus_tsdb_head_samples_appended_total`, `prometheus_tsdb_compaction_chunk_size_bytes` / `_samples` |
| #1080's host series | Per node: `node_boot_time_seconds` 1, `node_hwmon_temp_celsius` 14 to 29, `node_hwmon_chip_names` 5 to 7, `node_pressure_*` 5, `node_edac_*_errors_total` 0 to 8, `node_nvme_info` 1, so 26 to 51 per node and 147 in all. `node_systemd_unit_state` (collector off today) adds about 30 per node for 6 units in 5 states. About 270 series, 4.5 samples/s at a 60 s scrape, 0.5% of ingest. `node_filesystem_avail_bytes` and `node_filesystem_size_bytes` are already stored | each node-exporter's `/metrics` |
| Disk under both volumes | Both claims are on one node, whose root filesystem has 41.6 GB of 236 GB free (17.6%) | `node_filesystem_avail_bytes`, `kube_pod_spec_volumes_persistentvolumeclaims_info` |

## 3. Sizing

- **Loki, 20Gi.** 30 days of pod logs at the busiest day's 1.31 GB, stored at the measured 11:1, take 3.6 GB. #1080's journals, budgeted at 0.2 GB a day (five times the estimated 0.04 GB a day of unfiltered journal file growth), add about 0.6 GB at the same ratio, and the WAL, index and compactor files an estimated 0.3 GB (the WAL directory could not be read): about 4.5 GB. At a pessimistic 5:1 with every day as busy as the busiest, (1.31 + 0.2) GB x 30 / 5 + 0.3 GB is about 9.4 GB. 20Gi (21.5 GB) holds that twice over and leaves room for more nodes, which matters because local-path cannot expand a claim in place and every resize means a rebind.
- **Prometheus, 30 days by time, `retentionSize: 16GB`.** Prometheus reads the unit as a power of two, so the cap is 16 GiB, 80% of the 20Gi volume, leaving room for compaction. 30 days of blocks at 0.157 GB a day are 4.7 GB, about 5 GB with the WAL, and #1080 adds about 20 MB: 31% of the cap. Today's TSDB is 3.4% of it. Time retention deletes blocks long before the cap would.

## 4. Key Changes

- **`k8s/logging/loki-values.yaml`**: `loki.compactor` sets `retention_enabled: true` and `delete_request_store: filesystem`. `loki.limits_config.deletion_mode: disabled` closes the log delete API that the delete-request store opens: with `auth_enabled: false` it would take deletes from any pod allowed to reach Loki, and retention does not use it. `singleBinary.persistence.size` is `20Gi`. Comments give the measurements.
- **`k8s/monitoring/prometheus-values.yaml`**: `server.retentionSize: 16GB` under the existing `server.retention: 30d`. `serverFiles.alerting_rules.yml` holds the `log-and-metric-retention` group:
  - `LogOrMetricVolumeDiskLow` (warning, `for: 30m`): the root filesystem of the node holding `storage-loki-0` or `prometheus-server` has under 10% free. local-path keeps a volume on that filesystem and does not hold it to its claimed size, so a volume fills when the filesystem does. The rule follows each claim through `kube_pod_spec_volumes_persistentvolumeclaims_info` and `kube_pod_info` to its node and deduplicates both sides, so it moves with the volume and survives a kube-state-metrics or node-exporter restart.
  - `PrometheusNearRetentionSizeCap` (warning, `for: 1h`): blocks, WAL and head chunks together are over 80% of `prometheus_tsdb_retention_limit_bytes`, which happens before the cap would delete blocks younger than 30 days. It never fires on an unset cap.
- **`k8s/README.md`**: a Log and Metric Retention section says how long each store keeps data, what deletes it, each volume's size, why Loki's volume cannot be resized by an upgrade, and what the alerts watch.
- **`tests/test_k8s.py`**: `test_loki_deletes_logs_once_they_are_thirty_days_old`, `test_both_volumes_hold_thirty_days_and_no_size_cap_cuts_them_short` and `test_an_alert_fires_before_the_log_or_metric_volume_fills`. The alert test requires each rule to be well-formed PromQL (`validate_promql`), and requires the size-cap rule to read only series the Prometheus server serves, according to `tests/fixtures/metrics/prometheus-server.yaml`.
- **`changelog.d/550.md`**: the changelog fragment.

## 5. Acceptance Criteria

- [x] Loki enforces 30 days through compactor retention. `helm template` against loki-7.3.0 renders `compactor: {delete_request_store: filesystem, retention_enabled: true}` and `limits_config.retention_period: 720h`. `loki -verify-config` (3.6.11, the deployed build) reports `config is valid` for the rendered config. With the delete-request store removed it fails: `compactor.delete-request-store should be configured when retention is enabled`.
- [x] Loki's delete API stays closed (`deletion_mode: disabled`). That answers the question left open in the issue.
- [x] Loki's volume is sized for 30 days of pod logs plus #1080's host journals, with headroom (sections 2 and 3).
- [x] Prometheus keeps 30 days by time, and its 16GB size cap does not bind first. `helm template` against prometheus-29.35.0 renders `--storage.tsdb.retention.time=30d` and `--storage.tsdb.retention.size=16GB`, and the projected 30 days fill 31% of the cap.
- [x] An alert fires before either volume fills. `promtool check rules` (3.15.0) finds 2 rules. `promtool test rules` passes cases where the disk alert fires for both claims on a node with 8% free and stays quiet for another claim, another node and today's 17.6%, with kube-state-metrics reporting a pod twice. In other cases the size-cap alert fires at 85% after an hour and stays quiet at 35% and on an unset cap. Evaluated read-only against the live Prometheus, the disk expression returns 0.176 for both claims.
- [x] The three tests fail on the previous values (`KeyError: 'compactor'`, `'retentionSize'`, `'serverFiles'`) and pass now.
- [x] `helm upgrade --dry-run=server` succeeds for both releases against the cluster. That dry run does not submit the StatefulSet update. `kubectl diff --server-side` of the rendered Loki StatefulSet shows the API server refusing the 20Gi claim template: `updates to statefulset spec for fields other than 'replicas', 'ordinals', 'template', 'updateStrategy', 'persistentVolumeClaimRetentionPolicy' and 'minReadySeconds' are forbidden`. Loki therefore needs the migration below.
- [x] The steps in section 6 hold up after other deploys. `helm history <release> -o json | jq -r 'map(select(.status == "deployed")) | last | .revision'` prints `66` for Loki and `31` for Prometheus, the revisions `helm list -A` shows as `deployed`. Helm keeps 10 revisions per release, so a fixed rollback target can also be pruned. The recovery bullet was checked offline: the step 6 JSON patch, run with `kubectl patch --local` against a volume whose claim reference has no `uid` (the state after step 6), fails with `Unable to remove nonexistent key: uid`, so the recovery repeats step 6 only for a `Released` volume.
- [x] Checks after the review fixes: the three tests pass (0.11 s of test time together), `uv run ruff check .` prints `All checks passed!`, `mypy --strict` on `tests/test_k8s.py` (with `MYPYPATH=src`) finds no issues, `uv run devops docs check` reports every file up to date, and `uv run pytest -p no:cacheprovider -q -n 4 tests` ends `8069 passed, 8 xfailed`. `helm template` (loki-7.3.0, prometheus-29.35.0) and `helm upgrade --dry-run=server` for both releases still succeed, and both releases are still at revisions 66 and 31 afterwards.
- Not part of this item: the alerts notify no one until an Alertmanager with a receiver exists, which is #549.

## 6. Applying After Merge

Every command runs from the repository root with `kubectl config current-context` printing `homelab-k3s`, `jq` installed, and the `grafana` and `prometheus-community` Helm repositories added (`helm repo update`). The chart versions are pinned to the ones deployed today, and the other Helm flags match `devops k8s deploy-stack`. The stack is redeployed several times a day (Loki went from revision 59 to 66 between 2026-10-02 13:02 and 2026-10-03 06:02 UTC), so no step names a fixed Helm revision: each section records the revision it starts from and rolls back to that one.

- Pending a person, order: until the Loki migration below has run, `devops k8s deploy-stack --stack logging` (or `--stack all`) cannot upgrade Loki. Helm's update of the StatefulSet fails with `spec: Forbidden: updates to statefulset spec for fields other than 'replicas', 'ordinals', 'template', 'updateStrategy', 'persistentVolumeClaimRetentionPolicy' and 'minReadySeconds' are forbidden`, deploy-stack prints `Failed to install loki: ...` and goes on with `fluent-bit`, and each such run adds a `failed` Loki revision. Loki keeps running on its current StatefulSet. Run the Loki migration before, or in place of, the next deploy-stack that includes the logging stack. `devops k8s deploy-stack` with the default `--stack infra` upgrades Prometheus and is not affected.

### Prometheus (no migration)

- Pending a person: `PROM_REV=$(helm history prometheus -n monitoring -o json | jq -r 'map(select(.status == "deployed")) | last | .revision'); echo "$PROM_REV"` prints the revision Prometheus runs now (31 on 2026-10-03, higher after later deploys). Keep the shell open, because the rollback uses `$PROM_REV`.
- Pending a person: `helm upgrade --install --force-conflicts prometheus prometheus-community/prometheus --version 29.35.0 --namespace monitoring --values k8s/monitoring/prometheus-values.yaml --wait --timeout 10m` prints `STATUS: deployed` with the next revision number. The server restarts and replays its WAL, and history is kept.
- Pending a person: the Prometheus query `prometheus_tsdb_retention_limit_bytes` returns `17179869184`, and `prometheus_tsdb_retention_limit_seconds` returns `2592000`.
- Pending a person: `kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-server:9090/proxy/api/v1/rules?type=alert'` lists the group `log-and-metric-retention` with `LogOrMetricVolumeDiskLow` and `PrometheusNearRetentionSizeCap`, each `"health":"ok"` and `"state":"inactive"`.
- Pending a person, rollback: `helm rollback prometheus "$PROM_REV" --namespace monitoring --wait` restores the flags without the size cap and removes the rules. The TSDB is untouched.

### Loki (claim template change: orphan the StatefulSet and rebind the volume)

Kubernetes refuses a change to a StatefulSet's `volumeClaimTemplates`, and local-path cannot expand a claim. The StatefulSet is therefore deleted without its pod and claim. The existing volume is kept (`Retain`), its declared capacity is raised to 20Gi (local-path never enforced it), and it is reserved for the new claim of the same name. Every stored log is kept. Loki is down from step 4 until step 7 finishes, a few minutes. Alloy and Fluent Bit retry their pushes, but lines older than their retry window can be dropped.

- Pending a person, step 1: `PV=$(kubectl -n logging get pvc storage-loki-0 -o jsonpath='{.spec.volumeName}'); LOKI_REV=$(helm history loki -n logging -o json | jq -r 'map(select(.status == "deployed")) | last | .revision'); echo "$PV $LOKI_REV"` prints the volume's `pvc-...` name and the revision Loki runs now (66 on 2026-10-03, higher after later deploys; the filter skips any `failed` revision a deploy-stack run left). Keep the shell open, because later steps use `$PV` and the rollback uses `$LOKI_REV`.
- Pending a person, step 2: `kubectl patch pv "$PV" --dry-run=server -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain","capacity":{"storage":"20Gi"}}}' && kubectl patch pv "$PV" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain","capacity":{"storage":"20Gi"}}}'` prints `persistentvolume/pvc-... patched (server dry run)`, then `persistentvolume/pvc-... patched`. `kubectl get pv "$PV" -o jsonpath='{.spec.persistentVolumeReclaimPolicy} {.spec.capacity.storage}'` prints `Retain 20Gi`. Do not go on unless it prints `Retain`: otherwise deleting the claim in step 5 deletes the logs.
- Pending a person, step 3: `kubectl -n logging delete statefulset loki --cascade=orphan` prints `statefulset.apps "loki" deleted`. `kubectl -n logging get pod/loki-0 pvc/storage-loki-0` still shows the pod `Running` and the claim `Bound`. `--cascade=orphan` matters: the chart's `persistentVolumeClaimRetentionPolicy` is `whenDeleted: Delete`, so a plain delete removes the claim.
- Pending a person, step 4: `kubectl -n logging delete pod loki-0 --wait=true` prints `pod "loki-0" deleted`, and Loki stops.
- Pending a person, step 5: `kubectl -n logging delete pvc storage-loki-0 --wait=true` prints `persistentvolumeclaim "storage-loki-0" deleted`. `kubectl get pv "$PV" -o jsonpath='{.status.phase}'` prints `Released`.
- Pending a person, step 6: `kubectl patch pv "$PV" --type json -p '[{"op":"remove","path":"/spec/claimRef/uid"},{"op":"remove","path":"/spec/claimRef/resourceVersion"}]'` prints `persistentvolume/pvc-... patched`. `kubectl get pv "$PV" -o jsonpath='{.status.phase} {.spec.claimRef.namespace}/{.spec.claimRef.name}'` prints `Available logging/storage-loki-0`, so the volume is reserved for the new claim.
- Pending a person, step 7: `helm upgrade --install --force-conflicts loki grafana/loki --version 7.3.0 --namespace logging --values k8s/logging/loki-values.yaml --wait --timeout 10m` prints `STATUS: deployed` with the next revision number. `kubectl -n logging get pvc storage-loki-0 -o jsonpath='{.status.phase} {.spec.volumeName} {.status.capacity.storage}'` prints `Bound <the same $PV> 20Gi`, and `kubectl -n logging get pod loki-0` shows `1/1 Running`.
- Pending a person, step 8: `kubectl patch pv "$PV" -p '{"spec":{"persistentVolumeReclaimPolicy":"Delete"}}'` restores the class's reclaim policy, so the volume is removed with its claim as before.
- Pending a person, check: `kubectl get --raw /api/v1/namespaces/logging/services/loki:3100/proxy/config | grep -E '^\s+(retention_enabled|delete_request_store|deletion_mode):'` prints `retention_enabled: true`, `delete_request_store: filesystem` and `deletion_mode: disabled`. Within 15 minutes, `kubectl get --raw /api/v1/namespaces/logging/services/loki:3100/proxy/metrics | grep '^loki_compactor_apply_retention_last_successful_run_timestamp_seconds'` prints a current Unix time instead of `0`.
- Pending a person, check before 2026-10-11, while those days are inside the 30 days: the logs from before the migration are still there. `kubectl get --raw '/api/v1/namespaces/logging/services/loki:3100/proxy/loki/api/v1/index/stats?query=%7Bjob%3D~%22.%2B%22%7D&start=1789084800000000000&end=1789257600000000000'` returns `"chunks":10` (2026-09-11 to 2026-09-13), as it did before the migration.
- Pending a person, check: `kubectl get --raw /api/v1/namespaces/logging/services/loki:3100/proxy/loki/api/v1/delete` fails with `deletion is not available for this tenant`.
- Pending a person, check on or after 2026-10-14, once the oldest logs are 30 days old: `kubectl get --raw /api/v1/namespaces/logging/services/loki:3100/proxy/metrics | grep -E 'retention_marker_count_total|retention_sweeper_chunk_deleted_duration_seconds_count'` shows non-zero counts. The index-stats query above returns `"chunks":0`.
- Pending a person, recovery if step 7 leaves `storage-loki-0` `Pending` or bound to a volume other than `$PV`: repeat step 3, then delete the new pod and claim with the commands of steps 4 and 5 (step 5's `Released` check does not apply here). `kubectl get pv "$PV" -o jsonpath='{.status.phase} {.spec.persistentVolumeReclaimPolicy} {.spec.capacity.storage} {.spec.claimRef.namespace}/{.spec.claimRef.name}'` prints `Available Retain 20Gi logging/storage-loki-0`: step 6 already removed the claim reference's `uid`, so the volume stays reserved for the claim name and is `Available`, and the logs are still on it. Then repeat only step 7. Repeat step 6 first only if the phase is `Released`, which means the deleted claim had been partly bound to `$PV`; on an `Available` volume step 6 fails with `Unable to remove nonexistent key: uid`.
- Pending a person, rollback of the configuration: `kubectl -n logging delete statefulset loki --cascade=orphan && helm rollback loki "$LOKI_REV" --namespace logging --wait`. That revision's 2Gi template reuses the existing `storage-loki-0` claim by name, so the logs stay. Retention goes back to off.

## 7. Trade-offs

- local-path does not enforce sizes, so the claimed 20Gi documents the budget but does not limit Loki. `LogOrMetricVolumeDiskLow` watches the real limit, the node's root filesystem. That filesystem also holds container images and model files, so the alert can fire for growth outside both volumes.
- Loki's own metrics are not scraped into Prometheus, so retention runs are checked through the API proxy (section 6) and not by an alert.
- Both alerts are visible only in Prometheus and Grafana until #549 adds an Alertmanager with a receiver.
