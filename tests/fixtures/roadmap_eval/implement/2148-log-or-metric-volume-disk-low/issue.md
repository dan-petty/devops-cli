### What happened

`LogOrMetricVolumeDiskLow` in `k8s/monitoring/prometheus-values.yaml` joins `kube_pod_info` with `group_left (node)`. While a pod moves between nodes, `kube_pod_info` has a series for the pod on two nodes, and Prometheus refuses the rule with "many-to-many matching not allowed", so the alert does not evaluate. On 2026-10-24 the new rule `LocalPathNodeDiskHigh` (#1634) failed live in the same way with a `group_left` form, while the alloy-metrics pod moved, and #1634 wrote it with `and` instead.

### What should happen

`LogOrMetricVolumeDiskLow` evaluates while a pod moves: it joins on a label set that has one series for each pod (for example with `max by (namespace, pod, node)` on `kube_pod_info` before the join, or with `and` as `LocalPathNodeDiskHigh` does).

### Acceptance criteria

- [ ] A rule test (promtool test rules, as the other alert tests do) gives `kube_pod_info` two series for one pod on two nodes and shows that the alert still fires for a low volume.


Source: https://github.com/dan-petty/devops-cli/issues/1634
