# Spec Delta

## ADDED Requirements

### Requirement: Alertmanager Mattermost webhook Secret push
The cluster Secret push table SHALL declare row `monitoring/alertmanager-mattermost` under stack `infra` with optional derived key `url` built from in-cluster base URL constant `CONST_K8S_MATTERMOST_URL`, `/hooks/`, and managed credential `mattermost.alerts_hook`.

#### Scenario: Dry run lists the row with no value
- **WHEN** `devops k8s push-secrets --dry-run` runs
- **THEN** row `monitoring/alertmanager-mattermost` is listed with key `url` and no value

#### Scenario: Keyring lacks the hook value
- **WHEN** the keyring holds no value for `mattermost_alerts_hook` and `devops k8s push-secrets --only monitoring/alertmanager-mattermost` runs
- **THEN** the push skips the entry with a warning naming `devops config set mattermost.alerts_hook`

### Requirement: Secret reference guard yields mounted Secret names
The secret reference guard `_secret_references` SHALL yield `secretName` values used in volume mounts such as `extraSecretMounts` and Pod volume specifications.

#### Scenario: Volume mount references an unlisted Secret
- **WHEN** a Kubernetes manifest or values document defines `extraSecretMounts` with `secretName: unlisted-secret`
- **THEN** `referenced_secrets` includes the unlisted Secret and fails the guard if no table row exists
