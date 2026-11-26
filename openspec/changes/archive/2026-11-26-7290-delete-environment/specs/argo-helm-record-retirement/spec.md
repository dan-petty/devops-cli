## REMOVED Requirements

### Requirement: The homelab AppProject reports a left-over record
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The knowledge base runs no Helm command against an adopted release
**Reason**: The check needs the Applications of the cluster, which devops-cli no longer holds (#7290).
**Migration**: None.
