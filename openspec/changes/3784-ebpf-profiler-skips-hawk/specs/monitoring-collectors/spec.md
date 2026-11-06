# monitoring-collectors Specification

## ADDED Requirements

### Requirement: The alloy-profiles pod does not run on the node hawk
The `alloy-profiles` DaemonSet SHALL have a required node affinity with the expression `kubernetes.io/hostname` `NotIn [hawk]`, so that its eBPF profiler does not load on that node while the cause of the crashes of that node is open. No other collector SHALL carry this exclusion.

#### Scenario: The affinity excludes the node
- **WHEN** the `alloy-profiles` collector values in `k8s/monitoring/k8s-monitoring-values.yaml` are read
- **THEN** `controller.affinity` holds one required node selector term with the one expression `kubernetes.io/hostname` `NotIn [hawk]`
- **AND** the `alloy-singleton` and `alloy-logs` collectors have no `controller.affinity`
