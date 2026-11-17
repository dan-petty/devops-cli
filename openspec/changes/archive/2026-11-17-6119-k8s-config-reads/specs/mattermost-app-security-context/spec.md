## MODIFIED Requirements

### Requirement: Mattermost container security context
The Mattermost Custom Resource SHALL specify `containerSecurityContext` conforming to the restricted Pod Security standard.

#### Scenario: Mattermost specifies container security context
- **WHEN** the operator creates the Mattermost pod in namespace `mattermost`, which enforces Pod Security `restricted`
- **THEN** the API server admits the pod, and `kubectl -n mattermost get mattermost -o yaml` shows `allowPrivilegeEscalation: false` and `capabilities.drop` with `ALL`
