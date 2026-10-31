# Proposal

## Why

Issue #1393 addresses homelab operational visibility. Argo CD applies every merge into main, but when a sync fails or the devops application deploys, no notification reaches the team. The homelab operator must inspect Argo CD manually to discover failed rollouts or completed deployments.

## What Changes

- Enable the Argo CD notifications controller in `k8s/argocd/values.yaml` with dedicated resource requests, resource limits, and an empty `argocdUrl`.
- Configure `service.webhook.mattermost` notifier pointing to `$mattermost-deploys-url` with header `Content-Type: application/json` and `retryMax: 1`.
- Define catalog triggers `on-deployed` and `on-sync-failed` with templates `app-deployed` and `app-sync-failed` formatted as single-line JSON payloads through the `toJson` filter.
- Configure global subscription in `k8s/argocd/values.yaml` for `on-sync-failed` targeting the Mattermost webhook.
- Configure application-specific subscription annotation in `k8s/argocd/apps/devops.yaml` for `on-deployed` targeting the Mattermost webhook.
- Add managed credential `mattermost.deploys_hook` with keyring key `mattermost_deploys_hook` and environment variable `DEVOPS_CLI_MATTERMOST_DEPLOYS_HOOK`.
- Add derived key `mattermost-deploys-url` to `argocd/argocd-notifications-secret` in the cluster secrets push table under stack `infra`.
- Add network policy egress in `k8s/argocd/networkpolicy.yaml` allowing traffic to namespace `mattermost` on TCP port 8065.
- Add network policy ingress in `k8s/mattermost/networkpolicy.yaml` admitting traffic on TCP port 8065 from pods in namespace `argocd` with label `app.kubernetes.io/name: argocd-notifications-controller`.
- Update `k8s/README.md` with instructions for configuring the Mattermost deploys webhook and syncing cluster secrets.

## Capabilities

### New Capabilities
- `argocd-mattermost-notifications`: Argo CD notifications controller posts devops application deploys and failed application syncs to the Mattermost deploys channel.

### Modified Capabilities
- `stack-credential-sync`: Cluster secret `argocd/argocd-notifications-secret` gains optional derived key `mattermost-deploys-url`.

## Impact

- Manifests in `k8s/argocd/` and `k8s/mattermost/`.
- Secret definitions in `src/devops_cli/k8s/cluster_secrets.py` and `src/devops_cli/config/env.py`.
- Documentation in `k8s/README.md`.
- Automated test suites verifying network policies, Argo CD values, and secret plan invariants.

## Feasibility

- Argo CD v3.5.3 (chart 10.9.6) includes the notifications controller with the generic webhook service.
- Upstream `argoproj/notifications-engine` replaces `$key` references in webhook URLs from `argocd-notifications-secret` dynamically via informers without pod restarts.
- The webhook payload uses a pure `toJson` template filter to prevent quotation escaping errors.
- Network policies permit egress from `argocd` and ingress to `mattermost` on TCP port 8065.
- The change fits in one pull request.

## Existing Tool Considered

- Considered Argo CD native Mattermost notifier service. The native service requires a bot account, bot API token, and channel ID in git, which violates security rules against homelab identifiers in git. The generic webhook service avoids bot tokens and keeps the webhook URL secret via OS keyring.
