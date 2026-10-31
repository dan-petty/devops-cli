# Proposal

## Why
Issue #2945 addresses automated onboarding and configuration for Mattermost in Kubernetes. Setting up Mattermost integrations currently requires manual steps in the web interface: creating the team and channels (`alerts` and `deploys`), creating incoming webhooks with "Lock to this channel" for Alertmanager and Argo CD, creating the `/roadmap` custom slash command, extracting tokens and storing them into the workstation keyring (`mattermost.alerts_hook`, `mattermost.deploys_hook`, `mattermost.command_token`), and pushing secrets to the cluster (`monitoring/alertmanager-mattermost`, `argocd/argocd-notifications-secret`, `devops/devops-cli`). The homelab needs a deterministic CLI command to apply project configuration to Mattermost and automate onboarding, matching the pattern of `devops k8s bootstrap-openwebui`.

## What Changes
- Add `devops k8s bootstrap-mattermost` CLI command in `src/devops_cli/commands/k8s/mattermost_bootstrap.py` and register it in `src/devops_cli/commands/k8s/__init__.py`.
- Classify `bootstrap-mattermost` under `@dry_run_class("request-plan")`.
- Provide options:
  - `--context` / `-c`: Target Kubernetes context (default: config default or active).
  - `--team`: Mattermost team name (default: "homelab").
  - `--admin-user`: Username or ID of the administrator user to own the integrations (default: auto-detect first system admin).
  - `--push-secrets / --no-push-secrets`: Push updated secrets to the cluster after saving tokens to keyring (default: True).
  - `--dry-run`: Preview planned actions and exec requests without modifying state.
- In normal execution:
  - Verify Mattermost pod is running in namespace `mattermost`.
  - Ensure the target team exists.
  - Ensure channels `alerts` and `deploys` exist.
  - Ensure locked incoming webhooks for Alertmanager and Argo CD exist and extract their tokens.
  - Ensure custom slash command `/roadmap` exists and extract its token.
  - Store tokens into the workstation OS keyring (`mattermost.alerts_hook`, `mattermost.deploys_hook`, `mattermost.command_token`).
  - Push secrets to the cluster when `--push-secrets` is enabled.
- Add test suite in `tests/commands/test_k8s_bootstrap_mattermost.py` verifying dry run, command execution, error cases, and zero external requests under dry run.

## Capabilities

### New Capabilities
- `mattermost-bootstrap`: Automated bootstrapping of Mattermost teams, channels, webhooks, slash commands, keyring credentials, and cluster secrets.

### Modified Capabilities
- `command-dry-run-class`: Add `k8s bootstrap-mattermost` to the list of commands classified under `request-plan`.

## Impact
- Command interface: Adds `devops k8s bootstrap-mattermost`.
- Operations: Eliminates manual browser-based onboarding and secret synchronization for the chat stack.
- Tests: Adds comprehensive unit tests covering offline process mocking.

## Feasibility
Confirmed against the running homelab cluster and repository sources:
- `deploy/mattermost` runs in namespace `mattermost` with `MM_SERVICESETTINGS_ENABLELOCALMODE=true` and `LocalModeSocketLocation=/var/tmp/mattermost_local.socket`.
- `mmctl --local` operates over the local Unix domain socket through `kubectl exec` without external network egress or API credentials.
- Verified in-cluster `mmctl` commands:
  - `mmctl --local team list`
  - `mmctl --local channel list homelab`
  - `mmctl --local webhook list homelab`
  - `mmctl --local command list homelab`
- Keyring storage uses established `store_keyring_secret` / `_KEYRING_KEYS` mapping.
- Secret push uses existing `push_secrets` in `devops_cli.commands.k8s.cluster_secret_push`.
- Fits in one pull request.

## Existing Tool Considered
The upstream `mmctl` CLI is the official, maintained management tool for Mattermost. Rather than creating a custom API client requiring authentication tokens or browser automation, `bootstrap-mattermost` executes `mmctl --local` in the workload container. No custom HTTP client library is built.
