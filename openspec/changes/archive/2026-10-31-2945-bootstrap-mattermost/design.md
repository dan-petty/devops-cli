# Design

## Context
Mattermost Team Edition runs in namespace `mattermost` under Argo CD on CloudNativePG. Once the initial administrator account is registered, Mattermost requires configuration of teams, channels, locked incoming webhooks, and slash commands to receive alerts from Alertmanager, deployment notifications from Argo CD, and roadmap status queries.

Currently, this configuration requires manual steps in the web interface, copying tokens by hand, running `devops config set`, and running `devops k8s push-secrets`.

## Architecture & Implementation

### 1. Pod Discovery and Context Resolution
The command resolves the effective Kubernetes context and queries for the Mattermost workload pod:
```python
pod_cmd = [
    "kubectl",
    "get",
    "pods",
    "-n",
    "mattermost",
    "-l",
    "app.kubernetes.io/name=mattermost",
    "-o",
    "jsonpath={.items[0].metadata.name}",
]
```
If no pod is running, the command raises an error indicating the workload is unavailable.

### 2. In-Pod Execution via Local Mode
Mattermost runs with `MM_SERVICESETTINGS_ENABLELOCALMODE=true`, exposing a Unix domain socket at `/var/tmp/mattermost_local.socket`.
The CLI executes `mmctl --local ... --json` inside the pod via `kubectl exec`:
- Team check/creation: `mmctl --local team list --json`, `mmctl --local team create`
- Channel check/creation: `mmctl --local channel list <team> --json`, `mmctl --local channel create`
- Webhook provisioning: `mmctl --local webhook list <team> --json`, `mmctl --local webhook create-incoming --lock-to-channel`
- Slash command provisioning: `mmctl --local command list <team> --json`, `mmctl --local command create --post`

### 3. Credential Persistence and Secret Push
Extracted tokens are persisted to the workstation keyring via `store_keyring_secret`:
- `mattermost.alerts_hook` -> `mattermost_alerts_hook`
- `mattermost.deploys_hook` -> `mattermost_deploys_hook`
- `mattermost.command_token` -> `mattermost_command_token`

When `--push-secrets` is enabled (default `True`), the command invokes `push_secrets` for:
- `monitoring/alertmanager-mattermost`
- `argocd/argocd-notifications-secret`
- `devops/devops-cli`

### 4. Dry-Run Planning
The command is decorated with `@dry_run_class("request-plan")`. In dry-run mode (`--dry-run`), it executes zero external commands or subprocesses and renders the planned execution steps using `render_dry_run_result`.

## Rejected Alternatives

### Alternative 1: Remote REST API with Personal Access Token
- **Description**: Configure Mattermost via HTTP REST API from the workstation.
- **Evidence for Rejection**: Requires generating and handling an API bearer token, storing additional credentials, and relies on network reachability through the Cloudflare Tunnel. `mmctl --local` over `kubectl exec` is self-contained and secured by Kubernetes RBAC.

### Alternative 2: Pure GitOps manifest injection
- **Description**: Inject channels and webhooks through declarative CRDs or database seeds.
- **Evidence for Rejection**: The Mattermost Operator does not support Custom Resources for channels, webhooks, or slash commands. Direct database manipulation risks schema corruption across version upgrades. Upstream `mmctl` is the sanctioned management route.
