## MODIFIED Requirements

### Requirement: The runner Job knows it is a runner and holds a home volume
Each container of CronJob `devops-cli-runner` SHALL set `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` to `true`, mount ConfigMap `devops-cli-config` read-only and an `emptyDir` of its own as its home and as `/tmp`, and use no `envFrom`. Only `prepare` and `publish` SHALL take `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_VALKEY_PASSWORD`, and only `agent` `DEVOPS_CLI_AI_API_KEY`. The `ephemeral-storage` limit of `agent` SHALL cover every volume.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** each volume has a `sizeLimit`, each runner container sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER`, and the pod of `roadmap-service` does not

#### Scenario: The keys of the Secret
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders CronJob `devops-cli-runner`, and `uv run devops ci --check --only k8s` builds the implement Job and the fix-checks Job of the Service from it
- **THEN** no container has `envFrom`, `prepare` and `publish` take only `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_VALKEY_PASSWORD`, and `agent` takes only `DEVOPS_CLI_AI_API_KEY`

### Requirement: The policy pins the secrets, the volumes and the host of a Job of the Service
The policy SHALL refuse a Job unless each `env` entry with `valueFrom` reads `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, `DEVOPS_CLI_AI_API_KEY` or `DEVOPS_CLI_VALKEY_PASSWORD` of Secret `devops-cli` through `secretKeyRef` in the variable of its name, on the three containers the model key only in `agent` and the App key and the password of the cache only elsewhere, the volumes are those of the template, and the pod sets no `hostNetwork`, `hostPID` or `hostIPC`.

#### Scenario: A Job with another source or volume
- **WHEN** `uv run devops ci --check --only k8s` changes the Job from the template in one way: an `env` with `valueFrom` from another Secret, a fourth key of Secret `devops-cli` such as `DEVOPS_CLI_QDRANT_API_KEY` or `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN`, the App key or the password of the cache in `agent`, the model key in `prepare` or `publish`, a `hostPath` volume, a Secret volume, a ConfigMap volume of another name, `hostNetwork`, `hostPID` or `hostIPC`
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The keys of the template
- **WHEN** a person creates the Job from the template as the Service with `kubectl --as=system:serviceaccount:devops:roadmap-service create --dry-run=server`
- **THEN** the policy admits the Job with the key of each container in `secretKeyRef`
