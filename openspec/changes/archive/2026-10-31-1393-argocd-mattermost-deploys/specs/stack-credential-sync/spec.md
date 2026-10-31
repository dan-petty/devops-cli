# Spec Delta

## MODIFIED Requirements

### Requirement: The push writes Argo CD's GitHub notifier Secret
The cluster Secret push SHALL write Secret `argocd/argocd-notifications-secret` under stack `infra`: key `github-appID` from setting `argocd.github_app_id`, key `github-installationID` from setting `argocd.github_app_installation_id`, key `github-privateKey` from keyring entry `argocd_github_app_private_key`, and derived key `mattermost-deploys-url` from managed credential `mattermost.deploys_hook`. A change of the Secret SHALL restart no workload.

#### Scenario: A PEM key and two IDs reach the Secret
- **WHEN** namespace `argocd` exists, the keyring holds a three-line PEM-shaped value under `argocd_github_app_private_key`, and `DEVOPS_CLI_ARGOCD_GITHUB_APP_ID` and `DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID` are set
- **THEN** `devops k8s push-secrets --only argocd/argocd-notifications-secret` writes the three keys with those values byte for byte, restarts nothing, and prints no value

#### Scenario: The dry run names the keys and makes no request
- **WHEN** `devops k8s push-secrets --only argocd/argocd-notifications-secret --dry-run` runs
- **THEN** the output names each key with a placeholder of its source and no value, and no command runs

#### Scenario: Mattermost deploys hook is derived
- **WHEN** the keyring holds a value for `mattermost_deploys_hook` and `devops k8s push-secrets --only argocd/argocd-notifications-secret` runs
- **THEN** key `mattermost-deploys-url` is written with the complete Mattermost webhook URL
