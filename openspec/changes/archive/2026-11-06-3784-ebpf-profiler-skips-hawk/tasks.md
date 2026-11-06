# Tasks

## 1. The eBPF profiler skips hawk

- [x] 1.1 Write the test `test_the_ebpf_profiler_runs_on_every_node_except_hawk` in `tests/commands/k8s/test_k8s_monitoring_integration.py`: `alloy-profiles` has the required node affinity `kubernetes.io/hostname` `NotIn [hawk]`, and `alloy-singleton` and `alloy-logs` have none. Verify that it fails on the base with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 In `k8s/monitoring/k8s-monitoring-values.yaml`, give `collectors.alloy-profiles.controller` the node affinity, with a comment that names #3785 and says to remove the entry when that issue records the cause. Verify with `uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py`
- [x] 1.3 Render the pinned chart before and after, and verify that only the `Alloy` resource `k8s-monitoring-alloy-profiles` changes and that the Alloy chart renders the affinity in its DaemonSet: `helm template k8s-monitoring k8s-monitoring --repo https://grafana.github.io/helm-charts --version 4.5.2 -n monitoring -f k8s/monitoring/k8s-monitoring-values.yaml`. Then render the Alloy chart that the Alloy Operator runs with that spec: `helm template k8s-monitoring-alloy-profiles alloy --repo https://grafana.github.io/helm-charts --version 1.12.1 -n monitoring -f <the rendered spec>`
- [x] 1.4 In `k8s/README.md`, tell in the Pyroscope dashboard row that the node has no profile. Verify with `uv run devops ci docs`

## Workflow follow-up

- Pending a person: after Argo CD syncs, run `kubectl -n monitoring get pods -l app.kubernetes.io/name=alloy-profiles -o wide`. It shows no pod on `hawk` and one pod on each other node.
- Pending a person: find the cause of the crashes of `hawk` (#3785). Then remove the exclusion.
