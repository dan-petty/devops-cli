## REMOVED Requirements

### Requirement: DCGM exporter resource requests and limits fit its footprint
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The DCGM exporter collects the counter list of its values and restarts when the list changes
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
