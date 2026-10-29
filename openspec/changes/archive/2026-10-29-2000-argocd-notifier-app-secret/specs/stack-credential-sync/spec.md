## ADDED Requirements

### Requirement: The push writes Argo CD's GitHub notifier Secret
The cluster Secret push SHALL write Secret `argocd/argocd-notifications-secret` of stack `infra`: key `github-appID` from setting `argocd.github_app_id`, key `github-installationID` from setting `argocd.github_app_installation_id`, and key `github-privateKey` from keyring entry `argocd_github_app_private_key`, each byte for byte. A change of the Secret SHALL restart no workload.

#### Scenario: A PEM key and two IDs reach the Secret
- **WHEN** namespace `argocd` exists, the keyring holds a three-line PEM-shaped value under `argocd_github_app_private_key`, and `DEVOPS_CLI_ARGOCD_GITHUB_APP_ID` and `DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID` are set
- **THEN** `devops k8s push-secrets --only argocd/argocd-notifications-secret` writes the three keys with those values byte for byte, restarts nothing, and prints no value

#### Scenario: The dry run names the keys and makes no request
- **WHEN** `devops k8s push-secrets --only argocd/argocd-notifications-secret --dry-run` runs
- **THEN** the output names each key with a placeholder of its source and no value, and no command runs

### Requirement: Each notifier key is optional and is never generated
Each key of `argocd/argocd-notifications-secret` SHALL be optional. A missing value SHALL be left out with a warning that names `devops config set <key>`, and the push SHALL generate no value for it.

#### Scenario: No value is set
- **WHEN** namespace `argocd` exists and neither setting nor the keyring entry has a value
- **THEN** the push exits 0, writes no Secret, and names `devops config set argocd.github_app_id`, `devops config set argocd.github_app_installation_id` and `devops config set argocd.github_app_private_key`

### Requirement: The Argo CD chart creates no notifications Secret
The Argo CD values SHALL set `notifications.secret.create` to false, so the push is the one owner of `argocd-notifications-secret`, and the `homelab` AppProject SHALL ignore that Secret as an orphan.

#### Scenario: The values and the project
- **WHEN** `k8s/argocd/values.yaml` and `k8s/argocd/apps/projects.yaml` are read
- **THEN** `notifications.secret.create` is false and the `homelab` project's `orphanedResources.ignore` holds Secret `argocd-notifications-secret`
