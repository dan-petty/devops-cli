# mattermost-bootstrap Specification

## Purpose
The automated bootstrapping and onboarding of Mattermost in Kubernetes clusters, configuring primary teams, notification channels, locked webhooks, slash commands, OS keyring credentials, and cluster secrets.

## ADDED Requirements

### Requirement: mattermost-bootstrap-cluster-workload
When `devops k8s bootstrap-mattermost` runs, it SHALL verify that the Mattermost pod in namespace `mattermost` is ready before attempting configuration operations.

#### Scenario: Mattermost pod not found
- **WHEN** no running Mattermost pod exists in namespace `mattermost`
- **THEN** the command exits with an error indicating Mattermost workload is unavailable

### Requirement: mattermost-bootstrap-team-and-channels
The command SHALL ensure that the specified team exists (defaulting to `homelab`) and that public channels `alerts` and `deploys` exist in the team.

#### Scenario: Target team and channels exist
- **WHEN** team `homelab` and channels `alerts` and `deploys` already exist
- **THEN** existing IDs are reused without creating duplicates

#### Scenario: Channels missing
- **WHEN** channels `alerts` or `deploys` are missing
- **THEN** the command creates the missing channels via `mmctl --local channel create`

### Requirement: mattermost-bootstrap-webhooks-and-slash-command
The command SHALL ensure that incoming webhooks for `Alertmanager` (locked to `alerts`) and `Argo CD` (locked to `deploys`) exist, and that custom slash command `/roadmap` exists pointing to the in-cluster roadmap service webhook URL.

#### Scenario: Webhooks and command created
- **WHEN** incoming webhooks or slash command `/roadmap` are not present
- **THEN** the command creates them via `mmctl --local` and extracts their authentication tokens

### Requirement: mattermost-bootstrap-keyring-and-secrets
The command SHALL store the extracted webhook tokens and slash command token into the workstation OS keyring (`mattermost.alerts_hook`, `mattermost.deploys_hook`, `mattermost.command_token`). When `--push-secrets` is enabled, it SHALL push cluster secrets `monitoring/alertmanager-mattermost`, `argocd/argocd-notifications-secret`, and `devops/devops-cli`.

#### Scenario: Keyring and secret push
- **WHEN** `bootstrap-mattermost` successfully provisions integrations with `--push-secrets`
- **THEN** tokens are stored in the OS keyring and secret push is executed

### Requirement: mattermost-bootstrap-dry-run
The command SHALL carry the `request-plan` dry-run class. In dry-run mode, it SHALL make zero external or cluster exec requests and print planned actions.

#### Scenario: Dry-run execution
- **WHEN** user executes `devops k8s bootstrap-mattermost --dry-run`
- **THEN** no kubectl exec or keyring mutation is made and planned steps are rendered
