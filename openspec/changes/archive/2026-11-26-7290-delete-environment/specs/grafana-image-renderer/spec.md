## REMOVED Requirements

### Requirement: Grafana runs the image renderer of its chart at a release tag
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The chart connects Grafana and the renderer by their Services
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: No Ingress routes to the image renderer
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The renderer token comes from the keyring
**Reason**: The row is a row of `cluster-secrets.toml` of the environment tree (#7290).
**Migration**: The environment repository declares the row.

### Requirement: The image renderer pod mounts no ServiceAccount token
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: A missing renderer token stops only panel images
**Reason**: Moved: this change adds the product behavior to another capability (#7290).
**Migration**: See `An optional feature Secret is in the Secret table` of `cluster-secrets-loader`.
