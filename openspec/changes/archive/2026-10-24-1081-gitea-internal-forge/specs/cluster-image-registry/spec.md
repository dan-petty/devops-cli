## ADDED Requirements

### Requirement: Gitea's container registry is on
The Gitea values file `k8s/gitea/values.yaml` SHALL turn on Gitea's packages (`gitea.config.packages.ENABLED: true`), which hold the container registry of the cluster.

#### Scenario: A test reads the Gitea values
- **WHEN** a test reads `k8s/gitea/values.yaml`
- **THEN** `gitea.config.packages` is `{"ENABLED": true}`
