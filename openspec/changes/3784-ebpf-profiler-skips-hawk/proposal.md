# Proposal

## Why

Issue #3784: the node `hawk` reboots on its own, several times a day, on kernel 7.2.8 and 7.2.15. Only that node shows it. On 2026-11-05 the Alloy eBPF tracer of the `alloy-profiles` DaemonSet pod died on `hawk` 14 s after it loaded. The kernel then logged `BUG: workqueue leaked atomic, lock or RCU ... workfn=bpf_map_free_deferred`, and the node rebooted. A second crash on 2026-11-02 has no BPF frame in its trace, so the cause is open (#3785). The eBPF profiler is the only eBPF program loader on the nodes. The owner decided on 2026-11-06 to exclude `hawk` from the profiler until the source of the crashes is known.

## What Changes

- `k8s/monitoring/k8s-monitoring-values.yaml` gives `collectors.alloy-profiles.controller` a required node affinity `kubernetes.io/hostname` `NotIn [hawk]`. A comment names #3785 and says to remove the entry when that issue records the cause.
- The profiler stays on for all other nodes. No other collector changes.
- `k8s/README.md` tells in the Pyroscope dashboard row that the node has no profile.
- `tests/commands/k8s/test_k8s_monitoring_integration.py` gets a test that reads the values: only `alloy-profiles` carries the exclusion. The existing profiler test no longer compares the whole `controller` block.
- A manifest is observable, so the change has a spec delta: an ADDED requirement of `monitoring-collectors`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `monitoring-collectors`: the `alloy-profiles` pod does not run on the node `hawk`.

## Impact

- Manifest: `k8s/monitoring/k8s-monitoring-values.yaml`. Argo CD applies it after the merge.
- Document: `k8s/README.md`.
- Test: `tests/commands/k8s/test_k8s_monitoring_integration.py`.
- No alert reads the number of `alloy-profiles` pods: `git grep -n 'alloy-profiles' k8s/monitoring/prometheus-values.yaml` finds nothing, and the Prometheus rules hold no DaemonSet-count rule. The Pyroscope dashboard shows no profile for the pods of `hawk`, which is the intended effect.

## Feasibility

Checked on 2026-11-06 with Helm 4.3.0 at origin/main:

- `helm template k8s-monitoring k8s-monitoring --repo https://grafana.github.io/helm-charts --version 4.5.2 -n monitoring -f k8s/monitoring/k8s-monitoring-values.yaml`, before and after the change, differs only by the `affinity` block in the spec of the `Alloy` resource `k8s-monitoring-alloy-profiles`.
- `helm template ... alloy --version 1.12.1 -f <that spec>` (the chart that the Alloy Operator runs) renders the DaemonSet `k8s-monitoring-alloy-profiles` with that `nodeAffinity` under the pod spec.
- The `alloy-metrics` collector already sets `controller.affinity` the same way, so the chart accepts the value.
- The `hostname` label of a node is the node name, and `NotIn` also matches a node that has the label with another value. The pod stays off `hawk` only.

## Existing Tool Considered

Kubernetes node affinity, through the `controller.affinity` value of the `k8s-monitoring` chart. No new code. The change deletes no internal code.
