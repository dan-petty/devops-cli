## REMOVED Requirements

### Requirement: Loki discover_log_levels pinned
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: README dashboard entry
**Reason**: `k8s/README.md` of devops-cli describes the product base and the commands only (#7290).
**Migration**: The README of the environment repository describes its own services.

### Requirement: The template builds the generic service dashboard
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The log row shows the warnings above all lines of the workload pods
**Reason**: Moved: this change adds the product behavior to another capability (#7290).
**Migration**: See the requirement of the same name in `service-dashboard-template`.
