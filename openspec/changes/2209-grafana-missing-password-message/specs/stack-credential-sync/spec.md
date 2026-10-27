## ADDED Requirements

### Requirement: A missing Grafana admin password message names the keyring entry and the commands
When the keyring holds no `grafana_password`, `devops k8s sync-secrets` SHALL print a message that names the keyring entry `grafana_password`, the command `devops config set grafana.password`, and the command `devops k8s push-secrets`. It SHALL NOT say that a Secret is missing from the cluster.

#### Scenario: The keyring has no Grafana admin password
- **WHEN** the keyring holds no `grafana_password` and the sync runs for the `infra` stack
- **THEN** the output says that the Grafana admin password is not in the keyring (`grafana_password`) and names `devops config set grafana.password` and `devops k8s push-secrets`
