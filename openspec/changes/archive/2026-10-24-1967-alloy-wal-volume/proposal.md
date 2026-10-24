# Proposal

## Why

Issue #1967: the `alloy-metrics` collector runs as a StatefulSet with no volume claim. Its write-ahead log is in `/tmp/alloy`, in the container's own filesystem. When the pod restarts, Alloy loses the samples that it buffered and did not send, for example while Prometheus is down. #1955 found this problem.

## What Changes

- `k8s/monitoring/k8s-monitoring-values.yaml` gives `collectors.alloy-metrics` the claim template `alloy-wal` (`controller.volumeClaimTemplates`, `local-path`, `ReadWriteOnce`, 1Gi). `alloy.mounts.extra` mounts the claim at `/var/lib/alloy`, and `alloy.storagePath` points there.
- The pod gets the node affinity `node-role.kubernetes.io/control-plane` `DoesNotExist`. local-path binds the volume on the node where the pod first runs, and the root disk of the control-plane node has the least free space (#1634).
- `k8s/README.md` gets the section "Alloy Metrics Write-Ahead Log". It tells why the volume exists and how it is sized, and it gives the commands that a person runs after Argo CD syncs a change to the claim template: `kubectl -n monitoring delete statefulset k8s-monitoring-alloy-metrics --cascade=orphan`, and the checks before and after.
- `k8s/README.md` (Planned maintenance) tells that the `alloy-metrics` pod no longer moves to another node when its node is drained: like the other pods on local-path volumes, it waits for its node.
- `tests/test_k8s_monitoring_integration.py` gets a test that reads the values: the write-ahead log is on a writable mount of the claim, the claim template is complete, and the affinity keeps the pod off the control-plane node.
- A manifest is observable, so the change has a spec delta: the new capability `monitoring-collectors`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `monitoring-collectors`: what the Alloy collectors of the monitoring stack keep and where they run.

### Modified Capabilities

None.

## Impact

- `k8s/monitoring/k8s-monitoring-values.yaml`: the `alloy-metrics` collector only. The rendered k8s-monitoring 4.5.2 chart changes one object, the `Alloy` resource `k8s-monitoring-alloy-metrics`.
- The live cluster: after the merge, the old StatefulSet must be deleted with `--cascade=orphan` (`k8s/README.md`). The new pod restarts once, and the samples in the old `/tmp/alloy` are lost one last time.
- `k8s/README.md` and `tests/test_k8s_monitoring_integration.py`.

## Feasibility

- The pinned chart: `k8s/argocd/apps/k8s-monitoring.yaml` pins k8s-monitoring 4.5.2. `helm template` (Helm 4.3.0) of that chart with the changed values renders the `Alloy` resource `k8s-monitoring-alloy-metrics` with `controller.volumeClaimTemplates`, `controller.affinity`, `alloy.storagePath` and `alloy.mounts.extra` as written. No other rendered object changes.
- The chart that makes the StatefulSet: k8s-monitoring 4.5.2 runs the Alloy Operator 1.12.1. The live StatefulSet carries `helm.sh/chart: alloy-1.12.1` and an owner reference to the `Alloy` resource. The default values of the operator are the values of the Alloy chart 1.12.1, less `crds.create`. `helm template` of the Alloy chart 1.12.1 with the rendered `Alloy` spec gives a StatefulSet with the claim template `alloy-wal`, the argument `--storage.path=/var/lib/alloy`, the mount of `alloy-wal` at `/var/lib/alloy` and the node affinity. The Alloy chart documents `controller.volumeClaimTemplates` ("volumeClaimTemplates to add when controller.type is 'statefulset'") and `alloy.storagePath` ("By default, data is lost between reboots"). It mounts no claim by itself, so `alloy.mounts.extra` is necessary.
- The live StatefulSet (read-only `kubectl get statefulset -n monitoring -o yaml`): `k8s-monitoring-alloy-metrics` in `monitoring`, `updateStrategy` `RollingUpdate` with `partition: 0`, `podManagementPolicy: Parallel`, `persistentVolumeClaimRetentionPolicy` `Retain`/`Retain`, no `volumeClaimTemplates`, no affinity, and `--storage.path=/tmp/alloy` with no volume at that path.
- Argo CD (read-only `kubectl get application k8s-monitoring -n argocd`): the Application tracks the `Alloy` resource, not the StatefulSet. So the sync of the change succeeds, and the Alloy Operator's upgrade of the StatefulSet fails until the old StatefulSet is gone. The issue said that the Argo CD sync fails; the deploy step in `k8s/README.md` follows the real path.
- The size (read-only `kubectl exec ... du -sh /tmp/alloy` and `ls -la` of the log): 71M in the log. The two closed 2-hour segments are 27.8 MB and 28.2 MB, so Alloy writes about 14 MB an hour. The live `prometheus.remote_write` block sets `truncate_frequency = "2h"` and `max_keepalive_time = "8h"`. While Prometheus is down, the log holds at most about 8 h + 2 h of samples, about 140 MB. 1Gi is about 7 times that.
- The nodes (read-only `kubectl get nodes -L node-role.kubernetes.io/control-plane`): one node carries the label with the value `true`, and the other three do not carry it. The pod runs on a node without the label now. The classes (`kubectl get storageclass`): `local-path` is the default class, with `WaitForFirstConsumer`.

## Existing Tool Considered

The Alloy chart's `controller.volumeClaimTemplates`, `alloy.mounts.extra` and `alloy.storagePath` keep the log on a volume, and the cluster's local-path StorageClass gives the volume. The standard node label `node-role.kubernetes.io/control-plane` and a node affinity choose the node. Nothing is built, and the change deletes no internal code.
