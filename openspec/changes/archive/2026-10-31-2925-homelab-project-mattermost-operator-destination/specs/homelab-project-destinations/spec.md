# Spec Delta

## Purpose

Enforces Argo CD AppProject destination boundaries for the homelab project so base cluster infrastructure can deploy cleanly.

## ADDED Requirements

### Requirement: Homelab AppProject destination namespaces
AppProject `homelab` SHALL admit `mattermost-operator` and `cnpg-system` in its destination namespaces list, alongside `mattermost`.

#### Scenario: Homelab AppProject permits operator and system namespaces
- **WHEN** a test inspects `k8s/argocd/apps/projects.yaml`
- **THEN** AppProject `homelab` destinations include `namespace: mattermost-operator` and `namespace: cnpg-system`
