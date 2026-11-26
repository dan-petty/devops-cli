## REMOVED Requirements

### Requirement: A second gateway replica needs shared cooldowns and a disruption budget
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
