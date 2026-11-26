## MODIFIED Requirements

### Requirement: deploy-stack deploys Gitea as stack gitea
The deploy-stack stack `gitea` SHALL install release `gitea` (chart `gitea-charts/gitea` of repository `https://dl.gitea.com/charts/`) with the version and the values files of Application `gitea` of the environment tree, and SHALL apply the path sources of Application `gitea-manifests`. `--stack all` SHALL include it, and it SHALL NOT be a detached stack.

#### Scenario: A test reads the stack tables
- **WHEN** a test reads deploy-stack's tables
- **THEN** the stack `gitea` holds that repository and release, and the Application `gitea-manifests`

#### Scenario: A test resolves the stacks
- **WHEN** a test resolves `gitea` and `all`
- **THEN** `gitea` resolves to `["gitea"]`, `all` includes `gitea`, and `gitea` is not a detached stack

### Requirement: The Gitea admin Secret comes from the keyring
For stack `gitea`, the push SHALL write the row `gitea/gitea-admin` of the Secret table of the environment tree. The managed secret option `gitea.admin_password` SHALL read the keyring key `gitea_admin_password` and the environment variable `DEVOPS_CLI_GITEA_ADMIN_PASSWORD`. The password SHALL be required and never generated.

#### Scenario: A test reads the push table and the option tables
- **WHEN** a test reads the table of the fixture environment tree, the option tables and the secret registry
- **THEN** the row `gitea/gitea-admin` reads that keyring key with no generator, and the option has that keyring key and environment variable

#### Scenario: A dry run of the gitea stack's push
- **WHEN** `devops k8s push-secrets --stack gitea --dry-run --k8s-dir <tree>` runs on a fixture tree
- **THEN** it lists the reads of namespace `gitea`, Secret `gitea-admin` and keyring key `gitea_admin_password`, the apply with placeholders, and the restart of `deployment/gitea`, in order, makes no request and shows no value

## REMOVED Requirements

### Requirement: Argo CD installs the Gitea chart
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Argo CD applies the Gitea perimeter from git
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The homelab projects admit the Gitea sources and namespace
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gitea namespace refuses a privileged pod and keeps its data
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Gitea runs one pod on a SQLite database in WAL mode
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Gitea keeps its data on a kept claim on a worker node
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Gitea is a closed forge with no SSH and no egress need
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Gitea runs rootless as a non-root user with bounded resources
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Gitea builds its public URLs from each request
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Traefik routes the git host to the Gitea HTTP Service
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The Gitea perimeter admits only the HTTP port of Gitea
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
