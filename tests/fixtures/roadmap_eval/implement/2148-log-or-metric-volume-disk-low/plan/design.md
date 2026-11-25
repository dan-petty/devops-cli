# Design

## Decisions

- **Join `kube_pod_info` on the left with `group_left (persistentvolumeclaim)`.**
  *Choice:* In `LogOrMetricVolumeDiskLow`, join `max by (namespace, pod, node) (kube_pod_info)` on the left with `max by (namespace, pod, persistentvolumeclaim) (kube_pod_spec_volumes_persistentvolumeclaims_info{...})` on the right using `* on (namespace, pod) group_left (persistentvolumeclaim)`.
  *Evidence:* PromQL `group_left` requires at most one series per matching label on the right-hand side. While a pod moves, `kube_pod_info` can have series on multiple nodes. Placing `kube_pod_info` on the left allows many series on the left while the right-hand side has exactly one claim per pod.
- **Aggregate the claim info before joining.**
  *Choice:* Wrap `kube_pod_spec_volumes_persistentvolumeclaims_info` with `max by (namespace, pod, persistentvolumeclaim)`.
  *Evidence:* Strips extraneous labels (`uid`, `volume`, `ephemeral`) and guarantees at most one series per pod claim on the right side.
- **Retain `min by (instance) (...) * on (instance) group_right () (...) < 0.10`.**
  *Choice:* Keep the outer filesystem join and ratio check unchanged.
  *Evidence:* The left side is aggregated by `instance`, guaranteeing at most one series per instance. `group_right ()` permits multiple claim series on the right side while preserving the free ratio value.

## Rejected Alternatives

- **`and` joins on `(namespace, pod, node)`.** `kube_pod_spec_volumes_persistentvolumeclaims_info` does not have a `node` label, and `kube_pod_info` does not have `persistentvolumeclaim`. PromQL `and` returns only the labels of the left-hand vector and cannot join cross-vector labels without a binary operator with `group_left` or `group_right`.
- **`promtool test rules`.** Promtool is not installed on developer workstations or standard GitHub Actions runners, and repository decision record `2026-10-24-2194-dashboard-local-savings` rejected introducing it. Unit tests in `tests/test_k8s_monitoring_alerting.py` validate rule structure and PromQL selectors.
