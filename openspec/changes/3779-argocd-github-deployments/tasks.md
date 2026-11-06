# Tasks

## 1. Argo CD writes a GitHub deployment for each deploy

Reads: `k8s/argocd/networkpolicy.yaml`, `src/devops_cli/k8s/cluster_secrets.py`. Changes: `k8s/argocd/values.yaml`, `tests/invariants/test_k8s_argocd_apps.py`, `k8s/argocd/apps/agents.yaml`, `k8s/argocd/apps/argo-workflows-manifests.yaml`, `k8s/argocd/apps/base.yaml`, `k8s/argocd/apps/devops.yaml`, `k8s/argocd/apps/gitea-manifests.yaml`, `k8s/argocd/apps/gpu-feature-discovery.yaml`, `k8s/argocd/apps/ingress.yaml`, `k8s/argocd/apps/llm.yaml`, `k8s/argocd/apps/logging.yaml`, `k8s/argocd/apps/mattermost.yaml`, `k8s/argocd/apps/monitoring.yaml`, `k8s/argocd/apps/otel.yaml`.

- [x] 1.1 In `tests/invariants/test_k8s_argocd_apps.py`, write the cases for the notifier keys against the secret push and the README, for the `github.deployment` block of the template `app-deployed`, and for the set of subscribed Applications, with a case that pins the single-source rule on a Gitea source, a chart repository and a multi-source Application
  - Verification: `uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` fails on the base
- [x] 1.2 In `k8s/argocd/values.yaml`, add the notifier `service.github` and the `github.deployment` block and `message` of the template `app-deployed`. Add the annotation `notifications.argoproj.io/subscribe.on-deployed.github: ""` to the 12 Applications of `k8s/argocd/apps/` that have one `spec.source` on github.com
  - Verification: `uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` passes

## 2. Document the GitHub deployments

Changes: `k8s/README.md`.

- [x] 2.1 In the Notifications section of `k8s/README.md`, replace the line that leaves GitHub deployments to another issue with the rule, the permission, the network path and the command that lists the deployments
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge and the Argo CD sync, `kubectl -n argocd logs deploy/argocd-notifications-controller` shows no error for service `github`, and `devops gh api "repos/<owner>/<name>/deployments?environment=monitoring"` lists a deployment for the synced commit after the next deploy of `monitoring`.
- Pending a person: confirm that the installation of the App `devops-cli-argocd` lists the repository, and that the App holds only Deployments (read and write).
- Work this item does not do: a commit status, a failure state and the triggers `on-sync-failed`, `on-health-degraded` and `on-sync-status-unknown` for GitHub stay with #2003.
