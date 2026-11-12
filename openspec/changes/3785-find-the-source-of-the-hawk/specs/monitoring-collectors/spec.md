## MODIFIED Requirements

### Requirement: The alloy-profiles pod does not run on the node hawk
The `alloy-profiles` collector values in `k8s/monitoring/k8s-monitoring-values.yaml` SHALL hold no `controller.affinity`, so its eBPF profiler runs on every node. The `alloy-logs` and `alloy-singleton` collectors SHALL hold no `controller.affinity`, and `alloy-metrics` SHALL keep its one required node selector term with the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`.

#### Scenario: The affinity excludes the node
- **WHEN** A test reads the `collectors` block of `k8s/monitoring/k8s-monitoring-values.yaml`
- **THEN** The alloy-profiles, alloy-logs and alloy-singleton collectors hold no node affinity, and the alloy-metrics collector holds its one term with the control-plane label DoesNotExist
