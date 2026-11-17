## MODIFIED Requirements

### Requirement: Mattermost Operator numeric security context
The Mattermost Operator Helm values SHALL specify numeric `runAsUser` and `runAsGroup` identifiers.

#### Scenario: Mattermost Operator specifies numeric UID and GID
- **WHEN** a person runs `kubectl -n mattermost-operator get deployment -o yaml` on the cluster
- **THEN** `podSecurityContext.runAsUser` is `65532`
- **AND** `podSecurityContext.runAsGroup` is `65532`
