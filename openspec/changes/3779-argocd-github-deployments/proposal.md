# Proposal

## Why

The cluster secret push stores the App ID, the installation ID and the private key of the GitHub App `devops-cli-argocd` in `argocd/argocd-notifications-secret`. No notifier reads them: `k8s/argocd/values.yaml` defines only `service.webhook.mattermost`, and `k8s/README.md` says that `service.github` refers to the keys. So GitHub records no deployment when Argo CD deploys an Application (#3779).

## What Changes

- `k8s/argocd/values.yaml` defines the notifier `service.github` with `appID: $github-appID`, `installationID: $github-installationID` and `privateKey: $github-privateKey`.
- The template `template.app-deployed` gains a `github.deployment` block: state `success`, environment set to the Application name, `autoMerge: false` and `requiredContexts: []`. It sets no `logURL`, because `notifications.argocdUrl` is empty in git and the host of Argo CD is per-cluster configuration. The template gains a `message` that holds only the short sync revision, read with `dig`.
- Each Application under `k8s/argocd/apps/` that has one `spec.source` on github.com carries the annotation `notifications.argoproj.io/subscribe.on-deployed.github: ""`. That is 12 Applications. A multi-source Application and an Application of another host carry none. `notifications.subscriptions` gains no `github` entry, so `on-sync-failed` and the Mattermost subscriptions stay as they are.
- `k8s/README.md` says what the values define: the notifier, the subscription rule, the permission and the way to list the deployments.
- The invariant tests in `tests/invariants/test_k8s_argocd_apps.py` pin the notifier keys against the secret push and the README, the template block, and the set of subscribed Applications, which they derive from the files.
- The change alters a manifest that a consumer observes, so it carries a spec delta: the new capability `argocd-github-deployments`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `argocd-github-deployments`: Argo CD writes a GitHub deployment for each deploy of an Application that has one GitHub source

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/argocd/values.yaml`, 12 files of `k8s/argocd/apps/`
- Documents: `k8s/README.md`
- Tests: `tests/invariants/test_k8s_argocd_apps.py`
- Argo CD syncs the change from `main`. The notifications controller reads the new keys of the Secret when it builds a notification, so no workload restarts. A person applies nothing by hand.

## Feasibility

- Chart `argo-cd` 10.9.6 (the pin of `k8s/argocd/apps/argocd.yaml`) has the application version v3.5.3 (`appVersion` in the Argo Helm repository index). `go.mod` of Argo CD v3.5.3 requires `notifications-engine` at commit `0cff13b8a717`. Its `pkg/services/github.go` has the options `appID`, `installationID` and `privateKey`, the template field `GitHubNotification.Deployment` with `state`, `environment`, `environmentURL`, `logURL`, `requiredContexts`, `autoMerge`, `transientEnvironment` and `reference`, and the defaults `repoURLPath: {{.app.spec.source.repoURL}}` and `revisionPath: {{.app.status.operationState.syncResult.revision}}`.
- `Send` lists the deployments of the revision and the environment, creates one with `Ref` set to the revision when none exists, then creates a deployment status. So it needs the permission Deployments (read and write) and no other. `AutoMerge` defaults to true and `RequiredContexts` is passed as given, so the template sets `autoMerge: false` and `requiredContexts: []`: GitHub then reads no commit status and merges no branch.
- The defaults of `repoURLPath` and `revisionPath` read `.app.spec.source` and `syncResult.revision`. A multi-source Application has `spec.sources` and a list of revisions, so those paths are empty for it. So only a single-source Application with a github.com `repoURL` is subscribed: 12 of the 30 Applications under `k8s/argocd/apps/`. Eighteen are multi-source, and the other repositories (Helm chart repositories and Gitea) are no GitHub repository.
- The Argo CD documentation of the GitHub service (`operator-manual/notifications/services/github`) gives the same options, the `github.deployment` fields and the subscription annotation `notifications.argoproj.io/subscribe.<trigger>.github`.
- `helm template x argo-cd --repo https://argoproj.github.io/argo-helm --version 10.9.6 -f k8s/argocd/values.yaml` renders the ConfigMap `argocd-notifications-cm` with `service.github` and the new template, and renders no Secret `argocd-notifications-secret`. `notifications.secret.create` stays false.
- The perimeter network policy `k8s/argocd/networkpolicy.yaml` applies to every pod of `argocd` (`podSelector: {}`). Its egress rule 4 allows TCP 443 to any address except `169.254.169.254/32`, so the controller reaches `api.github.com` with no policy change.
- The notifications ConfigMap renders `context.argocdUrl` as a chart default when `notifications.argocdUrl` is empty, so a `logURL` would be wrong. The change sets none.
- The issue #2003 asks for a wider change: a commit status, the four catalog triggers, and a failure state. This change writes only the deployment of `on-deployed`. It makes none of the other edits of #2003.

## Existing Tool Considered

Argo CD Notifications has a built-in GitHub service with a `deployment` block (notifications-engine, Apache-2.0, maintained with Argo CD). The change adds values and annotations and no code. It deletes no internal code.
