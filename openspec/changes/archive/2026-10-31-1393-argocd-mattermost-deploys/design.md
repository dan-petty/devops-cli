# Design

## Context

See `proposal.md` - Why.

Argo CD v3.5.3 (chart 10.9.6) includes the notifications controller with the generic webhook notifier engine. Mattermost runs in namespace `mattermost` listening on port 8065. `CONST_K8S_MATTERMOST_URL` defines `http://mattermost.mattermost.svc.cluster.local:8065`.

## Goals / Non-Goals

**Goals:**
- Deliver notifications for `devops` deployment successes to the Mattermost deploys channel.
- Deliver notifications for all application sync failures to the Mattermost deploys channel.
- Keep homelab configuration, channel IDs, and webhook tokens completely out of git.
- Permit network communication between the Argo CD notifications controller and Mattermost.

**Non-Goals:**
- Deliver alerts for lasting `OutOfSync` or `Degraded` states (owned by issue #551 via Alertmanager).
- Deliver deploy notifications for non-devops applications.
- Run an interactive Mattermost bot requiring two-way webhooks or bot accounts.

## Decisions

### Decision 1: Generic Webhook Service over Native Mattermost Service
- **Decision**: Configure `service.webhook.mattermost` using URL variable `$mattermost-deploys-url`.
- **Rationale**: The generic webhook service reads its target URL dynamically from `argocd-notifications-secret`. This avoids committing channel IDs and bot tokens to git.
- **Rejected Alternative**: Argo CD native Mattermost notifier service (`service.mattermost`). Rejected because upstream documentation confirms it requires a bot token and channel IDs in manifests or annotations, which violates the zero-homelab-values-in-git invariant.

### Decision 2: Split Subscriptions (Global Failures, Per-Application Deploys)
- **Decision**: Put `on-sync-failed` in global `notifications.subscriptions` in `k8s/argocd/values.yaml`. Put `on-deployed` in `k8s/argocd/apps/devops.yaml` via annotation `notifications.argoproj.io/subscribe.on-deployed.mattermost: ""`.
- **Rationale**: Any sync failure represents an operational issue needing immediate attention. However, every commit auto-syncs altered applications, so global `on-deployed` would spam the chat with routine manifest adjustments.
- **Rejected Alternative**: Global subscription for `on-deployed`. Rejected because it creates alert fatigue across frequent routine multi-application deployments.

### Decision 3: JSON Payload Serialization with `toJson`
- **Decision**: Format `webhook.mattermost.body` as a JSON object whose text property is computed strictly through the `toJson` pipeline.
- **Rationale**: Sync failure messages often contain multi-line stack traces or unescaped quotes from Kubernetes API responses. The `toJson` helper guarantees valid JSON output.
- **Rejected Alternative**: Raw string concatenation with manual quoting. Rejected because quotes in error strings break JSON parsing in the receiver.

### Decision 4: Secret Management via Push Table
- **Decision**: Add `mattermost-deploys-url` as an optional derived entry to `argocd/argocd-notifications-secret` in `CLUSTER_SECRETS` under stack `infra`.
- **Rationale**: Argo CD notifications engine watches `argocd-notifications-secret` using informers and invalidates its cache automatically. Push-secrets delivers the derived URL without requiring a pod restart.
- **Rejected Alternative**: Direct manual secret creation with `kubectl create secret`. Rejected because manual commands bypass zero-plaintext and keyring lifecycle management.

### Decision 5: Restricted Network Policy Rules
- **Decision**: Admit traffic to `mattermost:8065` specifically from `podSelector: matchLabels: app.kubernetes.io/name: argocd-notifications-controller` in namespace `argocd`. Permit egress from `argocd` to namespace `mattermost` on TCP port 8065.
- **Rationale**: Follows least-privilege perimeter isolation. Only the notifications controller needs access to Mattermost.
- **Rejected Alternative**: Broad ingress from the entire `argocd` namespace. Rejected because only the notifications controller emits webhook traffic.

## Risks / Trade-offs

- [Risk: Keyring entry missing when push-secrets runs] → [Mitigation: Derived entry is marked optional; push-secrets logs a warning and continues without failing the deployment.]
- [Risk: Mattermost service temporarily unavailable] → [Mitigation: `retryMax: 1` limits immediate retry overhead; subsequent sync cycles re-trigger notifications if needed.]
