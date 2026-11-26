## MODIFIED Requirements

### Requirement: The runner Job knows it is a runner and holds a home volume
Each container of CronJob `devops-cli-runner` SHALL set `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` to `true`, mount ConfigMap `devops-cli-config` read-only and an `emptyDir` of its own as its home and as `/tmp`, and use no `envFrom`. Only `prepare` and `publish` SHALL take `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and only `agent` `DEVOPS_CLI_AI_API_KEY`. The `ephemeral-storage` limit of `agent` SHALL cover every volume.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** each volume has a `sizeLimit`, each runner container sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER`, and the pod of `roadmap-service` does not

#### Scenario: The keys of the Secret
- **WHEN** `kubectl kustomize k8s/devops` renders CronJob `devops-cli-runner`, and `uv run devops ci --check --only k8s` builds the implement Job and the fix-checks Job of the Service from it
- **THEN** no container has `envFrom`, `prepare` and `publish` take only `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and `agent` takes only `DEVOPS_CLI_AI_API_KEY`

## REMOVED Requirements

### Requirement: Image Updater keeps the runner image on its latest digest
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
