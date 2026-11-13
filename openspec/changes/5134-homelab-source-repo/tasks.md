# Tasks

## 1. The AppProjects admit the homelab repository

Kind: behavior. Reads: `tests/invariants/test_k8s_argocd_apps.py`. Changes: `k8s/argocd/apps/projects.yaml`, `tests/invariants/test_k8s_argocd_apps.py`.

- [x] 1.1 Write the failing tests: both AppProjects list the homelab repository and the devops-cli repository in `sourceRepos`, and project `homelab` ignores Secret `repo-homelab` as an orphan
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py`
- [x] 1.2 Add `https://github.com/dan-petty/homelab` to `sourceRepos` of `homelab` and `homelab-system`, and add Secret `repo-homelab` to `orphanedResources.ignore` of `homelab`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py tests/invariants/test_k8s_manifests.py tests/commands/k8s/test_k8s_gitea.py tests/commands/k8s/test_k8s_monitoring_integration.py`

## 2. Documents

Kind: other. Changes: `docs/HOMELAB_REPO_SWITCH.md`, `.nav.yml`, `k8s/README.md`.

- [ ] 2.1 Add the runbook `docs/HOMELAB_REPO_SWITCH.md` of plan steps 10 to 17, with the work, the check and the revert of each step and roles only, and add it to the Guides tab of `.nav.yml`. Link it from the GitOps section of `k8s/README.md`, and name step 14 of the runbook in place of the in-cluster Gitea of #1291
  - Verification: `$ uv run devops ci test tests/docs/test_docs_inventory.py tests/docs/test_site.py tests/docs/test_docs.py`

## Workflow follow-up

- #5134 keeps plan steps 10 to 17, which `docs/HOMELAB_REPO_SWITCH.md` gives.
- #5134: after the merge, `kubectl get appproject homelab homelab-system -n argocd -o jsonpath='{.spec.sourceRepos}'` lists the homelab repository, and all 34 Applications stay Synced.
