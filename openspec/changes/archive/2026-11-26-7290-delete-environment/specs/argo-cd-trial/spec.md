## MODIFIED Requirements

### Requirement: CLI commands for trial lifecycle
The CLI SHALL provide `devops argo cd trial start`, `end`, and `list`.

#### Scenario: Starting a trial application
- **WHEN** `devops argo cd trial start --branch feature --path k8s/devops` runs
- **THEN** it validates branch and path on Gitea, creates Namespace `trial-feature`, and applies Application `trial-feature`

#### Scenario: Ending a trial application
- **WHEN** `devops argo cd trial end trial-feature` runs
- **THEN** it deletes Application `trial-feature`, waits for resource removal, and deletes Namespace `trial-feature`

#### Scenario: Listing trial applications
- **WHEN** `devops argo cd trial list` runs
- **THEN** it displays all Applications in project `trial` with branch, path, sync status, health, and age

## REMOVED Requirements

### Requirement: AppProject trial definition
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Orphaned resources ignore list
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Argo CD network policy egress to Gitea
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Mainline application git safety
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Argo CD Gitea repository credential Secret
**Reason**: `CLUSTER_SECRETS` holds no row `argocd/gitea-repo-creds`: it is a row of `cluster-secrets.toml` of the environment tree (#7290).
**Migration**: The environment repository declares the row.
