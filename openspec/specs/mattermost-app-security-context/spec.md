# mattermost-app-security-context Specification

## Purpose
Enforces restricted container security context for the Mattermost workload.

## Requirements

### Requirement: Mattermost container security context
The Mattermost Custom Resource SHALL specify `containerSecurityContext` conforming to the restricted Pod Security standard.

#### Scenario: Mattermost specifies container security context
- **WHEN** a test inspects `k8s/mattermost/mattermost.yaml`
- **THEN** `spec.podTemplate.containerSecurityContext.allowPrivilegeEscalation` is `false`
- **AND** `spec.podTemplate.containerSecurityContext.capabilities.drop` contains `ALL`
