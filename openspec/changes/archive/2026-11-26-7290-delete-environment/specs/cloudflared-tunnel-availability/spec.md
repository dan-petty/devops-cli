## REMOVED Requirements

### Requirement: The tunnel replicas prefer different nodes
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: A drain keeps one tunnel replica available
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
