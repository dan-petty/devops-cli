# argocd-mattermost-notifications Specification

## Purpose
Enables the Argo CD notifications controller to report deploy successes for the devops application and failed syncs across all applications directly to Mattermost.

## Requirements

### Requirement: Argo CD notifications controller configuration
The Argo CD Helm values SHALL enable the notifications controller with dedicated CPU and memory requests and limits, an empty `argocdUrl`, disabled Secret creation (`notifications.secret.create: false`), and generic webhook service `mattermost` pointing to `$mattermost-deploys-url` with `Content-Type: application/json` and `retryMax: 1`.

#### Scenario: Values configure notifications controller and service
- **WHEN** `k8s/argocd/values.yaml` is parsed
- **THEN** `notifications.enabled` is true and `notifications.secret.create` is false
- **AND** service `webhook.mattermost` is defined with URL `$mattermost-deploys-url`

### Requirement: Deploy and failed sync triggers and templates
The Argo CD values SHALL declare triggers `on-deployed` and `on-sync-failed` with corresponding templates `app-deployed` and `app-sync-failed`. Each template SHALL emit a single-line JSON payload using the `toJson` filter containing the application name, revision, and sync error details when present.

#### Scenario: Templates format notifications as JSON
- **WHEN** `k8s/argocd/values.yaml` defines template `app-deployed` and `app-sync-failed`
- **THEN** each template defines `webhook.mattermost.body` as a JSON object with a single `toJson` expression

### Requirement: Application subscription split
The Argo CD values SHALL subscribe `on-sync-failed` to the Mattermost webhook across all applications without a selector. The devops Application manifest SHALL subscribe `on-deployed` to the Mattermost webhook via annotation `notifications.argoproj.io/subscribe.on-deployed.mattermost: ""`.

#### Scenario: Global and per-app subscriptions
- **WHEN** Argo CD values and application manifests are evaluated
- **THEN** `on-sync-failed` is listed in global `notifications.subscriptions`
- **AND** `k8s/argocd/apps/devops.yaml` contains the `on-deployed` subscription annotation

### Requirement: Network policy permits notifications controller egress to Mattermost
The perimeter network policy in `k8s/argocd/networkpolicy.yaml` SHALL permit egress to namespace `mattermost` on TCP port 8065. The perimeter network policy in `k8s/mattermost/networkpolicy.yaml` SHALL admit ingress on TCP port 8065 from pods in namespace `argocd` with label `app.kubernetes.io/name: argocd-notifications-controller`.

#### Scenario: Network policy ingress and egress
- **WHEN** network policies for `argocd` and `mattermost` are loaded
- **THEN** `argocd` network policy permits egress to namespace `mattermost` on port 8065
- **AND** `mattermost` network policy admits ingress on port 8065 only from the `argocd-notifications-controller` pod selector
