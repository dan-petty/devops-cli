## REMOVED Requirements

### Requirement: Loki runs from the open-source chart at a release that fixes CVE-2026-21729
**Reason**: Moved: this change adds the product behavior to another capability (#7290).
**Migration**: See `deploy-stack installs Loki from the open-source chart` of `k8s-helm-deploy`. The environment repository holds the chart version.

### Requirement: The chart version sets the Loki image
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The Loki values render no ServiceAccount that no pod uses
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
