## MODIFIED Requirements

### Requirement: deploy-stack deploys the chat stack
The stack `chat` SHALL install Helm release `mattermost-operator`, and apply post-Helm kustomization `k8s/mattermost` after the Helm releases complete. The CloudNativePG operator that the `Cluster` of that kustomization needs SHALL be a release of stack `infra`.

#### Scenario: deploy-stack installs chat releases and post-helm kustomization
- **WHEN** a person runs `uv run devops k8s deploy-stack --stack chat --dry-run`
- **THEN** `helm_releases` is `mattermost-operator` with no `cloudnative-pg`, `post_helm` is the kustomization `k8s/mattermost`, and the command makes no request

### Requirement: deploy-stack installs the CloudNativePG operator with stack infra and applies the gateway database after the Helm releases
The stack `infra` SHALL install Helm release `cloudnative-pg` after `prometheus-operator-crds`. The stack `llm` SHALL apply `k8s/llm/gateway-db.yaml` as a post-Helm path, so the CloudNativePG CRD exists when the `Cluster` is applied. No other stack SHALL list the release.

#### Scenario: The operator has one stack and the database follows the Helm releases
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when `cloudnative-pg` is a release of stack `infra` and of no stack that holds a CloudNativePG `Cluster`, `llm/gateway-db.yaml` is a post-Helm path of stack `llm`, and the kustomization of `k8s/llm` lists the file

### Requirement: deploy-stack installs cert-manager and the Barman Cloud plugin with stack infra after the operator
The stack `infra` SHALL install Helm release `cert-manager` in namespace `cert-manager`, and Helm release `plugin-barman-cloud` in the namespace of release `cloudnative-pg`, after both `cloudnative-pg` and `cert-manager`. No other stack SHALL list the three releases. Argo CD SHALL sync Application `plugin-barman-cloud` in a later sync wave than Application `cert-manager`.

#### Scenario: The plugin follows the operator and cert-manager in stack infra
- **WHEN** a person runs `uv run devops k8s deploy-stack --stack infra --dry-run`
- **THEN** `helm_releases` lists `cloudnative-pg` and `cert-manager` before `plugin-barman-cloud`, and the Helm command of `plugin-barman-cloud` names namespace `cnpg-system`, the namespace of `cloudnative-pg`
- **AND** the dry run of each other stack lists none of the three releases

#### Scenario: Argo CD syncs the plugin after cert-manager
- **WHEN** Argo CD syncs Application `cluster`, and a person runs `kubectl -n argocd get applications cert-manager plugin-barman-cloud`
- **THEN** both Applications are `Synced` and `Healthy`, and the sync of `plugin-barman-cloud` reports no missing cert-manager resource
