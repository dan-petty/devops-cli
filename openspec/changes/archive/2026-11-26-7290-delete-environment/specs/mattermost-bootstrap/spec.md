## MODIFIED Requirements

### Requirement: mattermost-bootstrap-keyring-and-secrets
The command SHALL store the extracted webhook tokens and slash command token into the workstation OS keyring (`mattermost.alerts_hook`, `mattermost.deploys_hook`, `mattermost.command_token`). When `--push-secrets` is enabled, it SHALL read the Secret table of the environment tree, of `--k8s-dir` when given, before it changes anything, and SHALL push `monitoring/alertmanager-mattermost`, `argocd/argocd-notifications-secret` and `devops/devops-cli` from that tree.

#### Scenario: Keyring and secret push
- **WHEN** `bootstrap-mattermost` successfully provisions integrations with `--push-secrets`
- **THEN** tokens are stored in the OS keyring and secret push is executed

#### Scenario: The tree that the option gives
- **WHEN** `devops k8s bootstrap-mattermost --k8s-dir <tree>` runs from a repository with no environment tree
- **THEN** it reads the Secret table of `<tree>` and goes on to the cluster

#### Scenario: A tree with no Secret table
- **WHEN** `devops k8s bootstrap-mattermost --dry-run` runs with a push on a tree with no `cluster-secrets.toml`
- **THEN** it exits non-zero and names `cluster-secrets.toml` and `--k8s-dir`
