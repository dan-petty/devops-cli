## ADDED Requirements

### Requirement: deploy-stack deploys the chat stack
The stack `chat` SHALL install Helm releases `cloudnative-pg` and `mattermost-operator` in order, and apply post-Helm kustomization `k8s/mattermost` after the Helm releases complete.

#### Scenario: deploy-stack installs chat releases and post-helm kustomization
- **WHEN** `devops k8s deploy-stack --stack chat --dry-run` executes
- **THEN** the output lists Helm releases `cloudnative-pg` and `mattermost-operator` and post-Helm kustomization `mattermost`
