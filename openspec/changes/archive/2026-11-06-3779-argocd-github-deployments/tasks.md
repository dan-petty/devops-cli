# Tasks

## 1. Argo CD writes a GitHub deployment for each deploy

Reads: `k8s/argocd/networkpolicy.yaml`. Changes: `k8s/argocd/values.yaml`, `src/devops_cli/k8s/cluster_secrets.py`, `tests/invariants/test_k8s_argocd_apps.py` and `tests/k8s/test_cluster_secret_plan.py`.
Also changes the 12 Application files of `k8s/argocd/apps/` with one GitHub source: `agents`, `argo-workflows-manifests`, `base`, `devops`, `gitea-manifests`, `gpu-feature-discovery`, `ingress`, `llm`, `logging`, `mattermost`, `monitoring` and `otel`.

- [x] 1.1 In `tests/invariants/test_k8s_argocd_apps.py`, write the failing cases:
  - the notifier keys against the secret push and the README, with the three GitHub keys required;
  - the `github.deployment` block of the template `app-deployed`;
  - every notifier, trigger and template value as a string;
  - the `oncePer` key of the trigger `on-deployed`;
  - the set of subscribed Applications, with a case that pins the single-source rule on a Gitea source, a chart repository and a multi-source Application.
  - Verification: `uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` fails on the base
- [x] 1.2 In `k8s/argocd/values.yaml`, add the notifier `service.github`. Add the `github.deployment` block and the `message` to the template `app-deployed`. Set `oncePer` to `app.status.operationState?.syncResult?.revision`.
  - Verification: `uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` passes
- [x] 1.2a In `k8s/argocd/values.yaml`, write each notifier as a block scalar string. This repairs the ConfigMap that the sync refused.
  - Verification: `uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` passes, and `helm template` of the pinned chart renders only strings in `argocd-notifications-cm`
- [x] 1.3 Add the annotation `notifications.argoproj.io/subscribe.on-deployed.github: ""` to the 12 Applications of `k8s/argocd/apps/` that have one `spec.source` on github.com
  - Verification: `uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` passes
- [x] 1.4 In `src/devops_cli/k8s/cluster_secrets.py`, make the three GitHub entries of `argocd/argocd-notifications-secret` required. Update `tests/k8s/test_cluster_secret_plan.py`.
  - Verification: `uv run devops ci test tests/k8s/test_cluster_secret_plan.py` passes

## 2. Document the GitHub deployments

Changes: `k8s/README.md`.

- [x] 2.1 In the Notifications section of `k8s/README.md`, replace the line that leaves GitHub deployments to another issue. Write the rule, the permission, the network path, the trigger key and the command that lists the deployments. Mark the three GitHub keys as required in the Cluster Secrets table.
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge and the Argo CD sync, read `kubectl -n argocd logs deploy/argocd-notifications-controller`. It must show no error for service `github`.
- Pending a person: after the next deploy of `monitoring`, run `devops gh api "repos/<owner>/<name>/deployments?environment=monitoring"`. It must list a deployment for the synced commit.
- Pending a person: confirm that the installation of the App `devops-cli-argocd` lists the repository. Confirm that the App holds only Deployments (read and write).
- Work this item does not do: a commit status, a failure state and the triggers `on-sync-failed`, `on-health-degraded` and `on-sync-status-unknown` for GitHub stay with #2003.
