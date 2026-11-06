## Purpose

Argo CD writes a GitHub deployment for the synced commit each time an Application that has one GitHub source deploys, so GitHub records each deploy. It uses only the Deployments permission of its own GitHub App.

## ADDED Requirements

### Requirement: The GitHub notifier reads the keys of the secret push
The Argo CD Helm values SHALL define the notifier `service.github` with `appID: $github-appID`, `installationID: $github-installationID` and `privateKey: $github-privateKey`. Each `$key` that a notifier reads SHALL be a key that the cluster secret push writes to `argocd/argocd-notifications-secret` and that the Cluster Secrets table of `k8s/README.md` lists. The values SHALL keep `notifications.secret.create: false`.

#### Scenario: The notifier keys match the push and the README
- **WHEN** `k8s/argocd/values.yaml`, the entries of `argocd/argocd-notifications-secret` in `CLUSTER_SECRETS` and `k8s/README.md` are read
- **THEN** `service.github` holds the three keys above
- **AND** every `$key` of every notifier is a pushed key and a key in a README row of that Secret

### Requirement: A deploy writes a GitHub deployment with no merge and no required check
The template `app-deployed` SHALL hold a `github.deployment` block with state `success`, environment `{{.app.metadata.name}}`, `autoMerge: false` and `requiredContexts: []`. The block SHALL set no `logURL`, no `environmentURL` and no `reference`, and the template SHALL read no `.context` value.

#### Scenario: The template has the deployment block
- **WHEN** the template `app-deployed` of `k8s/argocd/values.yaml` is parsed
- **THEN** its `github.deployment` block holds exactly the four fields above
- **AND** its `webhook.mattermost` block is still present
- **AND** the template `app-sync-failed` has no `github` block

### Requirement: Only single-source GitHub Applications subscribe
Each Application under `k8s/argocd/apps/` that has one `spec.source` whose repository host is github.com SHALL carry the annotation `notifications.argoproj.io/subscribe.on-deployed.github: ""`. No other Application SHALL carry it. `notifications.subscriptions` SHALL hold no `github` recipient.

#### Scenario: The annotated set follows the sources
- **WHEN** the Application manifests under `k8s/argocd/apps/` are read
- **THEN** the Applications with the annotation are exactly the Applications with one `spec.source` on github.com
- **AND** a multi-source Application carries no annotation

#### Scenario: The rule leaves out another host and a multi-source Application
- **WHEN** the rule runs on a source of a Gitea host, a Helm chart repository host and a multi-source Application
- **THEN** it selects none of them
