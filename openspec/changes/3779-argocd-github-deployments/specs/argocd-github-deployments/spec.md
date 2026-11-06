## Purpose

Argo CD writes a GitHub deployment for the synced commit each time an Application that has one GitHub source deploys, so GitHub records each deploy. It uses only the Deployments permission of its own GitHub App.

## ADDED Requirements

### Requirement: The GitHub notifier reads the keys of the secret push
The Argo CD Helm values SHALL define the notifier `service.github` with `appID: $github-appID`, `installationID: $github-installationID` and `privateKey: $github-privateKey`. Each `$key` that a notifier reads SHALL be a key of `argocd/argocd-notifications-secret` that the cluster secret push writes. The Cluster Secrets table of `k8s/README.md` SHALL list it. The values SHALL keep `notifications.secret.create: false`.

#### Scenario: The notifier keys match the push and the README
- **WHEN** `k8s/argocd/values.yaml`, the entries of `argocd/argocd-notifications-secret` in `CLUSTER_SECRETS` and `k8s/README.md` are read
- **THEN** `service.github` holds the three keys above
- **AND** every `$key` of every notifier is a pushed key and a key in a README row of that Secret

### Requirement: The push requires the three GitHub keys
The three GitHub entries of `argocd/argocd-notifications-secret` SHALL be required entries of the cluster secret push. The engine builds all notifiers together, so a notifier that lacks a key stops all notifications.

#### Scenario: A missing GitHub value blocks the push
- **WHEN** the push runs for `argocd/argocd-notifications-secret` and one of the three values has no source
- **THEN** the push writes nothing
- **AND** it exits with status 1 and names the command that sets the value

### Requirement: A deploy writes a GitHub deployment with no merge and no required check
The template `app-deployed` SHALL hold a `github.deployment` block with state `success`, environment `{{.app.metadata.name}}`, `autoMerge: false` and `requiredContexts: []`. The block SHALL set no `logURL`, no `environmentURL` and no `reference`, and the template SHALL read no `.context` value.

#### Scenario: The template has the deployment block
- **WHEN** the template `app-deployed` of `k8s/argocd/values.yaml` is parsed
- **THEN** its `github.deployment` block holds exactly the four fields above
- **AND** its `webhook.mattermost` block is still present
- **AND** the template `app-sync-failed` has no `github` block

### Requirement: The trigger keys a deploy by the revision of the last sync
The trigger `on-deployed` SHALL set `oncePer` to `app.status.operationState?.syncResult?.revision`. The notifier SHALL keep its default `revisionPath` and `repoURLPath`. The `message` of the template SHALL read the same revision.

#### Scenario: The trigger key is the revision that the notifier reads
- **WHEN** the trigger `on-deployed` and the notifier `service.github` of `k8s/argocd/values.yaml` are parsed
- **THEN** `oncePer` is `app.status.operationState?.syncResult?.revision`
- **AND** the notifier sets no `revisionPath` and no `repoURLPath`

### Requirement: Only single-source GitHub Applications subscribe
Each Application under `k8s/argocd/apps/` that has one `spec.source` whose repository host is github.com SHALL carry the annotation `notifications.argoproj.io/subscribe.on-deployed.github: ""`. No other Application SHALL carry it. `notifications.subscriptions` SHALL hold no `github` recipient.

#### Scenario: The annotated set follows the sources
- **WHEN** the Application manifests under `k8s/argocd/apps/` are read
- **THEN** the Applications with the annotation are exactly the Applications with one `spec.source` on github.com
- **AND** a multi-source Application carries no annotation

#### Scenario: The rule leaves out another host and a multi-source Application
- **WHEN** the rule runs on a source of a Gitea host, a Helm chart repository host and a multi-source Application
- **THEN** it selects none of them
