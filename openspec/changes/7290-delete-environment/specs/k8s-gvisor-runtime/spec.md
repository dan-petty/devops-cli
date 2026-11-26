## REMOVED Requirements

### Requirement: The environment tree declares RuntimeClass gvisor for the runsc nodes
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: RuntimeClass gvisor declares the measured pod overhead
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
