## REMOVED Requirements

### Requirement: The manifests deploy no in-cluster Distribution registry
**Reason**: Moved: this change adds the product behavior to another capability (#7290).
**Migration**: See `The k8s row refuses an in-cluster image registry in the product base` of `ci-gate-rows`.

### Requirement: Gitea serves the container registry of the cluster
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
