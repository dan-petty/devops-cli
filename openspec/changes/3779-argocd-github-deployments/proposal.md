# Proposal

## Why

The cluster secret push stores the App ID, the installation ID and the private key of the GitHub App `devops-cli-argocd` in `argocd/argocd-notifications-secret`. No notifier reads them: `k8s/argocd/values.yaml` defines only `service.webhook.mattermost`, and `k8s/README.md` says that `service.github` refers to the keys. So GitHub records no deployment when Argo CD deploys an Application (#3779).

The Mattermost notifier is also broken today. With the chart `argo-cd` 10.9.6, a mapping under `notifications.notifiers` renders as a mapping in `ConfigMap.data`. The sync of the Application `argocd` then fails with `cannot unmarshal object into Go struct field ConfigMap.data of type string`, and the ConfigMap `argocd-notifications-cm` does not exist. The notifications controller logs `trigger 'on-deployed' is not configured` about once a minute, and no Mattermost deploy notification posts. The fault came with #2904. The new `service.github` would fail in the same way, so this change repairs both.

## What Changes

- `k8s/argocd/values.yaml` writes each notifier as a block scalar string, which repairs `service.webhook.mattermost`. It defines the notifier `service.github` with `appID: $github-appID`, `installationID: $github-installationID` and `privateKey: $github-privateKey`.
- The template `template.app-deployed` gains a `github.deployment` block: state `success`, environment set to the Application name, `autoMerge: false` and `requiredContexts: []`. It sets no `logURL`, because `notifications.argocdUrl` is empty in git and the host of Argo CD is per-cluster configuration. The template gains a `message` that holds only the short sync revision, read with `dig`.
- Each Application under `k8s/argocd/apps/` that has one `spec.source` on github.com carries the annotation `notifications.argoproj.io/subscribe.on-deployed.github: ""`. That is 12 Applications. A multi-source Application and an Application of another host carry none. `notifications.subscriptions` gains no `github` entry, so `on-sync-failed` and the Mattermost subscriptions stay as they are.
- `k8s/README.md` says what the values define: the notifier, the subscription rule, the permission and the way to list the deployments.
- The trigger `on-deployed` keys `oncePer` on `app.status.operationState?.syncResult?.revision`, the revision that the notifier reads. The message of the template and the Mattermost text read the same value.
- The three GitHub entries of `argocd/argocd-notifications-secret` in `src/devops_cli/k8s/cluster_secrets.py` become required. The README table says so.
- The invariant tests in `tests/invariants/test_k8s_argocd_apps.py` pin four things against the files:
  - every notifier, trigger and template value is a string;
  - the notifier keys against the secret push and the README, with the three keys required;
  - the template block and the trigger key;
  - the set of subscribed Applications.
- The change alters a manifest that a consumer observes, so it carries a spec delta: the new capability `argocd-github-deployments`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `argocd-github-deployments`: Argo CD writes a GitHub deployment for each deploy of an Application that has one GitHub source

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/argocd/values.yaml`, 12 files of `k8s/argocd/apps/`
- Code: `src/devops_cli/k8s/cluster_secrets.py` (three entries become required)
- Documents: `k8s/README.md`
- Tests: `tests/invariants/test_k8s_argocd_apps.py`, `tests/k8s/test_cluster_secret_plan.py`
- Argo CD syncs the change from `main`. The notifications controller reads the new keys of the Secret when it builds a notification, so no workload restarts. A person applies nothing by hand.

## Feasibility

- Chart `argo-cd` 10.9.6 (the pin of `k8s/argocd/apps/argocd.yaml`) has the application version v3.5.3 (`appVersion` in the Argo Helm repository index). `go.mod` of Argo CD v3.5.3 requires `notifications-engine` at commit `0cff13b8a717`.
- `pkg/services/github.go` of that commit has the options `appID`, `installationID` and `privateKey`. It has the template field `GitHubNotification.Deployment` with `state`, `environment`, `environmentURL`, `logURL`, `requiredContexts`, `autoMerge`, `transientEnvironment` and `reference`. Its defaults are `repoURLPath: {{.app.spec.source.repoURL}}` and `revisionPath: {{.app.status.operationState.syncResult.revision}}`.
- `Send` lists the deployments of the revision and the environment. It creates one with `Ref` set to the revision when none exists. Then it creates a deployment status. So it needs the permission Deployments (read and write) and no other.
- `AutoMerge` defaults to true, and `RequiredContexts` is passed as given. So the template sets `autoMerge: false` and `requiredContexts: []`. GitHub then reads no commit status and merges no branch.
- `Send` reuses the deployment of the revision in `revisionPath`. So the trigger must key `oncePer` on that same revision. A live read of the cluster shows that `status.sync.revision` is the new HEAD for every Application, while `operationState.syncResult.revision` differs for each Application. The key is `operationState?.syncResult?.revision`, as in `notifications_catalog/triggers/on-deployed.yaml` of Argo CD v3.5.3.
- `helm template argocd argo-cd --repo https://argoproj.github.io/argo-helm --version 10.9.6 --namespace argocd -f k8s/argocd/values.yaml` showed `service.webhook.mattermost` as a mapping in `argocd-notifications-cm`. With block scalars, every value of `data` renders as a string. The render shows `oncePer` and the template with the `syncResult` revision.
- `NewAPI` of the engine (`pkg/api/api.go`) builds every service and returns the first error. A missing `$github-appID` stays unresolved, and the constructor then fails. An invalid private key fails in the same way. So one bad value stops all notifications, and the push requires the three keys.
- The defaults of `repoURLPath` and `revisionPath` read `.app.spec.source` and `syncResult.revision`. A multi-source Application has `spec.sources` and a list of revisions, so those paths are empty for it. So only a single-source Application with a github.com `repoURL` is subscribed: 12 of the 30 Applications under `k8s/argocd/apps/`. Eighteen are multi-source. The other repositories (Helm chart repositories and Gitea) are no GitHub repository.
- The Argo CD documentation of the GitHub service (`operator-manual/notifications/services/github`) gives the same options. It also gives the `github.deployment` fields and the subscription annotation `notifications.argoproj.io/subscribe.<trigger>.github`.
- `helm template x argo-cd --repo https://argoproj.github.io/argo-helm --version 10.9.6 -f k8s/argocd/values.yaml` renders the ConfigMap `argocd-notifications-cm` with `service.github` and the new template. It renders no Secret `argocd-notifications-secret`, because `notifications.secret.create` stays false.
- The perimeter network policy `k8s/argocd/networkpolicy.yaml` applies to every pod of `argocd` (`podSelector: {}`). Its egress rule 4 allows TCP 443 to any address except `169.254.169.254/32`. So the controller reaches `api.github.com` with no policy change.
- The notifications ConfigMap renders `context.argocdUrl` as a chart default when `notifications.argocdUrl` is empty. So a `logURL` would be wrong, and the change sets none.
- The issue #2003 asks for a wider change: a commit status, the four catalog triggers and a failure state. This change writes only the deployment of `on-deployed`. It makes none of the other edits of #2003.

## Existing Tool Considered

Argo CD Notifications has a built-in GitHub service with a `deployment` block (notifications-engine, Apache-2.0, maintained with Argo CD). The change adds values and annotations and no code. It deletes no internal code.
