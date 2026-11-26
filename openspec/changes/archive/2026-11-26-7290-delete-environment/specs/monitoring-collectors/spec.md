## REMOVED Requirements

### Requirement: The alloy-metrics write-ahead log is on a volume claim
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The alloy-metrics pod does not run on the control-plane node
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The alloy-profiles pod does not run on the node hawk
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The OpenTelemetry collector sends metrics to the Prometheus OTLP receiver
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: A stream with no delta for an hour starts again from zero
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Alloy keeps the cAdvisor thread series
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
