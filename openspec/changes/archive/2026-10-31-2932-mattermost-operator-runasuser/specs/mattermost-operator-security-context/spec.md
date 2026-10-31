# Spec Delta

## Purpose

Enforces numeric user identifiers for the Mattermost Operator so the kubelet can confirm non-root execution.

## ADDED Requirements

### Requirement: Mattermost Operator numeric security context
The Mattermost Operator Helm values SHALL specify numeric `runAsUser` and `runAsGroup` identifiers.

#### Scenario: Mattermost Operator specifies numeric UID and GID
- **WHEN** a test inspects `k8s/mattermost/mattermost-operator-values.yaml`
- **THEN** `podSecurityContext.runAsUser` is `65532`
- **AND** `podSecurityContext.runAsGroup` is `65532`
