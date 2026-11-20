## MODIFIED Requirements

### Requirement: The runner Job knows it is a runner and holds a home volume
The container of CronJob `devops-cli-runner` SHALL set `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` to `true`, take only the keys `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY` of Secret `devops-cli`, through `secretKeyRef` and with no `envFrom`, mount ConfigMap `devops-cli-config`, and mount an `emptyDir` of 8 Gi as its home and an `emptyDir` of 1 Gi as `/tmp`. The other CronJob SHALL not set that variable. The `ephemeral-storage` limit SHALL cover both volumes.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** both volumes have a `sizeLimit`, only the runner container sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER`, and the pod of `roadmap-service` does not

#### Scenario: The keys of the Secret
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders CronJob `devops-cli-runner`, and `uv run devops ci --check --only k8s` builds the implement Job and the fix-checks Job of the Service from it
- **THEN** the container and both Jobs have no `envFrom` and take only `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY` through `secretKeyRef`

### Requirement: The policy pins the secrets, the volumes and the host of a Job of the Service
The policy SHALL refuse a Job unless each `env` entry with `valueFrom` reads the key `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` or `DEVOPS_CLI_AI_API_KEY` of Secret `devops-cli` through `secretKeyRef` in the variable of its name, the volumes are only `tmp` and `home` (`emptyDir`) and `config` (ConfigMap `devops-cli-config`), and the pod sets no `hostNetwork`, `hostPID` or `hostIPC`.

#### Scenario: A Job with another source or volume
- **WHEN** `uv run devops ci --check --only k8s` changes the Job from the template in one way: an `env` with `valueFrom` from another Secret, a third key of Secret `devops-cli` such as `DEVOPS_CLI_VALKEY_PASSWORD` or `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN`, a `hostPath` volume, a Secret volume, a ConfigMap volume of another name, `hostNetwork`, `hostPID` or `hostIPC`
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The keys of the template
- **WHEN** a person creates the Job from the template as the Service with `kubectl --as=system:serviceaccount:devops:roadmap-service create --dry-run=server`
- **THEN** the policy admits the Job with its 2 keys in `secretKeyRef`

## ADDED Requirements

### Requirement: The policy admits envFrom only in the update of a runner Job
The policy SHALL refuse a Job with `envFrom`, but not in the `UPDATE` of a runner Job whose `envFrom` names only Secret `devops-cli`. A runner Job that the Service made before #6518 has that `envFrom`, and the Service patches its deadline and resumes it. A Job keeps its pod template, so an `UPDATE` cannot add `envFrom`.

#### Scenario: A Job with envFrom
- **WHEN** `uv run devops ci --check --only k8s` runs the policy against the Job from the template with `envFrom` of a ConfigMap, of another Secret or of Secret `devops-cli`
- **THEN** the policy refuses the `CREATE` of each, admits the `UPDATE` of a runner Job with Secret `devops-cli` in `envFrom`, and refuses the `UPDATE` of a runner Job with another Secret in `envFrom`
