# Tasks

## 1. The alloy-metrics write-ahead log is on a volume off the control-plane node

- [x] 1.1 Write the test `test_alloy_metrics_keeps_its_write_ahead_log_on_a_volume_off_the_control_plane_node` in `tests/test_k8s_monitoring_integration.py`: `alloy.storagePath` is under a writable mount of the claim `alloy-wal`, the claim template is complete, and the node affinity holds `node-role.kubernetes.io/control-plane` `DoesNotExist`. Verify that it fails on the base with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 In `k8s/monitoring/k8s-monitoring-values.yaml`, give `collectors.alloy-metrics` the claim template `alloy-wal` (`local-path`, `ReadWriteOnce`, 1Gi), its mount at `/var/lib/alloy`, `alloy.storagePath: /var/lib/alloy` and the node affinity. Verify with `uv run devops ci test tests/test_k8s_monitoring_integration.py`
- [x] 1.3 Render the pinned chart and verify that only the `Alloy` resource `k8s-monitoring-alloy-metrics` changes and that its spec holds the claim template, the mount, the storage path and the affinity: `helm template k8s-monitoring k8s-monitoring --repo https://grafana.github.io/helm-charts --version 4.5.2 -n monitoring -f k8s/monitoring/k8s-monitoring-values.yaml`. Then render the Alloy chart that the Alloy Operator runs with that spec: `helm template k8s-monitoring-alloy-metrics alloy --repo https://grafana.github.io/helm-charts --version 1.12.1 -n monitoring -f <the rendered spec>`
- [x] 1.4 Add the section "Alloy Metrics Write-Ahead Log" to `k8s/README.md`, with the size, the placement and the deploy step. In "Planned maintenance", tell that the `alloy-metrics` pod waits for its node when the node is drained. Verify with `uv run devops docs check`

## 2. After the merge

- [x] 2.1 The lead runs the deploy step of `k8s/README.md` (Alloy Metrics Write-Ahead Log) after the merge, when Argo CD has synced the `Alloy` resource `k8s-monitoring-alloy-metrics`: `kubectl -n monitoring delete statefulset k8s-monitoring-alloy-metrics --cascade=orphan`. Verify with `kubectl -n monitoring get pvc alloy-wal-k8s-monitoring-alloy-metrics-0`, and with `kubectl -n monitoring get pod k8s-monitoring-alloy-metrics-0 -o jsonpath='{.spec.volumes[*].persistentVolumeClaim.claimName}'`, which prints `alloy-wal-k8s-monitoring-alloy-metrics-0`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
