## MODIFIED Requirements

### Requirement: deploy-stack deploys the chat stack
The stack `chat` SHALL install Helm release `mattermost-operator`, and apply post-Helm kustomization `k8s/mattermost` after the Helm releases complete. The CloudNativePG operator that the `Cluster` of that kustomization needs SHALL be a release of stack `infra`.

#### Scenario: deploy-stack installs chat releases and post-helm kustomization
- **WHEN** a test reads the Helm releases and the post-Helm paths that `deploy-stack` has for stack `chat`
- **THEN** the releases are `mattermost-operator` and not `cloudnative-pg`, and the post-Helm path is kustomization `mattermost`

## ADDED Requirements

### Requirement: deploy-stack installs the CloudNativePG operator with stack infra and applies the gateway database after the Helm releases
The stack `infra` SHALL install Helm release `cloudnative-pg` after `prometheus-operator-crds`. The stack `llm` SHALL apply `k8s/llm/gateway-db.yaml` as a post-Helm path, so the CloudNativePG CRD exists when the `Cluster` is applied. No other stack SHALL list the release.

#### Scenario: The operator has one stack and the database follows the Helm releases
- **WHEN** a test reads the Helm releases and the post-Helm paths of `deploy-stack`
- **THEN** `cloudnative-pg` is a release of stack `infra` only, and `llm/gateway-db.yaml` is a post-Helm path of stack `llm`
