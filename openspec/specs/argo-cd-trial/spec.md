# argo-cd-trial Specification

## Purpose
Deploys transient trial workloads from internal Gitea branches into fenced cluster namespaces using Argo CD.

## Requirements

### Requirement: CLI commands for trial lifecycle
The CLI SHALL provide `devops argo cd trial start`, `end`, and `list`.

#### Scenario: Starting a trial application
- **WHEN** `devops argo cd trial start --branch feature --path k8s/devops` runs
- **THEN** it validates branch and path on Gitea, creates Namespace `trial-feature`, and applies Application `trial-feature`

#### Scenario: Ending a trial application
- **WHEN** `devops argo cd trial end trial-feature` runs
- **THEN** it deletes Application `trial-feature`, waits for resource removal, and deletes Namespace `trial-feature`

#### Scenario: Listing trial applications
- **WHEN** `devops argo cd trial list` runs
- **THEN** it displays all Applications in project `trial` with branch, path, sync status, health, and age
