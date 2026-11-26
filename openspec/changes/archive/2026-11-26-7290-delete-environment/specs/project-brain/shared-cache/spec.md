## REMOVED Requirements

### Requirement: The cache Valkey keeps its data bound below its limit
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
