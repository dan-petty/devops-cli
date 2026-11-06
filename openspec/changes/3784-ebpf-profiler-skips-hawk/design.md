# Design

## Context

k8s-monitoring 4.5.2 renders each collector as an `Alloy` resource. The Alloy Operator 1.12.1 renders the Alloy chart 1.12.1 from it. The `alloy-profiles` collector is a DaemonSet that runs on every node and has the toleration `NoSchedule Exists`. The `alloy-metrics` collector already uses `controller.affinity` for a node exclusion.

## Goals / Non-Goals

**Goals:**

- Keep the eBPF profiler off the node `hawk` until the cause of its crashes is found (#3785).
- Keep the profiler on for the other nodes.

**Non-Goals:**

- Do not turn the profiler off on the other nodes. They show no crash with the same config.
- Do not change the other collectors, the cluster, or the node.
- Do not look for the cause of the crashes: #3785 holds that work.

## Decisions

- **Decision: a required node affinity on the hostname.**
  *Choice:* `controller.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution` with the expression `kubernetes.io/hostname` `NotIn [hawk]`, the same form as the `alloy-metrics` affinity.
  *Rejected alternative:* a taint on the node. A taint is a host change that only a person makes, and every other pod on the node would need a toleration. `alloy-logs` and the exporters must keep running on `hawk`.
  *Rejected alternative:* turn off `profiling.ebpf` for all nodes. The other nodes show no crash, and the owner asked for the exclusion of one node.

- **Decision: no alert change.**
  The Prometheus rules hold no rule on the number of `alloy-profiles` pods or on DaemonSet counts. The DaemonSet has one desired pod less, and no rule reads it.

## Risks / Trade-offs

- The pods of `hawk` have no profile while the exclusion stays. The entry is removed when #3785 records the cause.
