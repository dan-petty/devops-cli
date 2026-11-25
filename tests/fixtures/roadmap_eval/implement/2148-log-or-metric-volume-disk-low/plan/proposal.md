# Proposal

## Why

Issue #2148: `LogOrMetricVolumeDiskLow` in `k8s/monitoring/prometheus-values.yaml` joins `kube_pod_info` with `group_left (node)`. While a pod moves between nodes, `kube_pod_info` has a series for the pod on two nodes. Prometheus refuses the rule with "many-to-many matching not allowed", so the alert does not evaluate. On 2026-10-24 the rule `LocalPathNodeDiskHigh` (#1634) encountered the same live failure while the alloy-metrics pod moved. #1634 resolved `LocalPathNodeDiskHigh` by avoiding multiple series on the right side of a `group_left` join.

## What Changes

- Reorder the inner join in `LogOrMetricVolumeDiskLow` in `k8s/monitoring/prometheus-values.yaml`: `kube_pod_info` is placed on the left side of `group_left (persistentvolumeclaim)`. The right side is `kube_pod_spec_volumes_persistentvolumeclaims_info`, aggregated by `(namespace, pod, persistentvolumeclaim)`.
- When a pod moves between nodes, `kube_pod_info` has multiple series on the left side. The right side has at most one series for the pod's claim. Prometheus evaluates this many-to-one join without error.
- Add an alert rule test to `tests/test_k8s_monitoring_alerting.py` verifying that `LogOrMetricVolumeDiskLow` uses `group_left (persistentvolumeclaim)` rather than `group_left (node)`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `log-and-metric-retention`: alert rule evaluating storage space for log and metric local-path volumes while pods move between nodes.

### Modified Capabilities

None.

## Impact

- `k8s/monitoring/prometheus-values.yaml`
- `tests/test_k8s_monitoring_alerting.py`

## Feasibility

- Confirmed with `devops_cli.prometheus.promql.validate_promql` that the rewritten expression is structurally valid PromQL.
- Confirmed that `kube_pod_info` carries `node`, `namespace`, and `pod`, while `kube_pod_spec_volumes_persistentvolumeclaims_info` carries `namespace`, `pod`, and `persistentvolumeclaim`.
- Joining `kube_pod_info` on the left with `group_left (persistentvolumeclaim)` preserves `node` on each series from `kube_pod_info` and attaches `persistentvolumeclaim` from the right side.
- Because a pod has at most one matching persistentvolumeclaim in the target namespaces, the right side has at most one series per `(namespace, pod)`.
- Multiple series in `kube_pod_info` across nodes satisfy PromQL `group_left` semantics without many-to-many matching errors.

## Existing Tool Considered

PromQL `group_left (persistentvolumeclaim)` with `kube_pod_info` on the many side is standard Prometheus query structure. No external parser or tool is required.
