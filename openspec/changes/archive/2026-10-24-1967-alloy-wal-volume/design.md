# Design

## Context

k8s-monitoring 4.5.2 renders each collector as an `Alloy` resource. The Alloy Operator 1.12.1 renders the Alloy chart 1.12.1 from that resource and makes the StatefulSet `k8s-monitoring-alloy-metrics`. Argo CD tracks the `Alloy` resource only. The `statefulset` preset sets only `controller.type` and `replicas`, so the write-ahead log is in `/tmp/alloy` in the container's own filesystem.

## Goals / Non-Goals

**Goals:**

- Keep the write-ahead log of `alloy-metrics` on a volume that a pod restart keeps.
- Keep the volume off the control-plane node.
- Record the step that a person runs after Argo CD syncs a change to the claim template.

**Non-Goals:**

- Do not change the other collectors. `alloy-logs` keeps its positions on the node through the `host-storage` preset. `alloy-singleton` and `alloy-profiles` keep no write-ahead log.
- Do not change the `wal` block of `prometheus.remote_write`. The chart default keeps unsent samples for 8 hours.
- Do not add a node label or a new StorageClass.

## Decisions

- **Decision: a claim template on the StatefulSet.**
  *Choice:* `controller.volumeClaimTemplates` with the claim `alloy-wal`, mounted at `/var/lib/alloy` through `alloy.mounts.extra`, and `alloy.storagePath: /var/lib/alloy`.
  *Rejected alternative:* the `host-storage` preset, a `hostPath` volume at `/var/lib/alloy`.
  *Evidence for rejection:* the preset is for a DaemonSet. A StatefulSet pod can go to a different node after a restart, and the log on the old node is then lost. A `hostPath` volume also bypasses the StorageClass and the claim records.
  *Rejected alternative:* the `fast-nvme` class.
  *Evidence for rejection:* every other claim in `k8s/` uses `local-path`, and the issue names it. The log is small, so the disk speed is not important.
- **Decision: node affinity `node-role.kubernetes.io/control-plane` `DoesNotExist`.**
  *Choice:* a required node affinity on the pod. local-path binds the volume on the node where the pod first runs, and from then on the volume holds the pod on that node.
  *Rejected alternative:* a node selector on a new label for nodes with disk space.
  *Evidence for rejection:* the lead's decision for #1634 uses the well-known label and adds no new label. Each node without the label has 1 TB or more, with 838 GB or more free.
- **Decision: a 1Gi claim.**
  *Choice:* 1Gi. The live log writes about 14 MB an hour. While Prometheus is down, the log holds at most about 10 hours (`max_keepalive_time` 8h, plus one `truncate_frequency` of 2h), about 140 MB.
  *Rejected alternative:* a claim as large as the Loki or Prometheus claims.
  *Evidence for rejection:* local-path does not hold a volume to its claimed size, so the size is a record, not a limit. A larger number tells a wrong size.
- **Decision: delete the StatefulSet with `--cascade=orphan` after the sync.**
  *Choice:* a person deletes the old StatefulSet after Argo CD syncs the `Alloy` resource. The operator then makes the new StatefulSet, which adopts the pod and replaces it.
  *Rejected alternative:* delete the StatefulSet before the merge.
  *Evidence for rejection:* the operator watches the resources that it owns. It makes the old StatefulSet again from the old `Alloy` spec before Argo CD syncs the new spec.

## Risks / Trade-offs

- [The new pod restarts once, and the samples in the old `/tmp/alloy` are lost one last time.] → Prometheus accepts writes now, so few samples are not sent.
- [The volume holds the pod on one node. A drain of that node no longer moves the pod: it waits for its node, the cluster-wide series stop, and `ClusterMetricsMissing` pages after about 15 minutes.] → Before this change, only a node that powered off stopped the series. The same is true for every local-path claim on this cluster, and the root disk of the control-plane node, which holds Prometheus, does not hold this volume. `k8s/README.md` (Planned maintenance) tells the effect. A class that is not bound to one node would remove it, and the cluster has none.
