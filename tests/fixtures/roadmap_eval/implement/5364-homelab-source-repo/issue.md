### Problem or Motivation

This item is plan step 8 of the homelab migration in #5134. The migration moves the source of the homelab environment of Argo CD from devops-cli to the private repository https://github.com/dan-petty/homelab.

Argo CD refuses an Application source whose repository is not in the `sourceRepos` of its AppProject. Now the AppProjects `homelab` and `homelab-system` admit devops-cli and the Helm chart repositories only. Thus the switch of the Applications to the homelab repository (plan step 11) fails with a refused source.

The owner made the repository credential `repo-homelab` in namespace `argocd`. No Application tracks it, so project `homelab` reports it as an orphan. The Applications `argocd`, `argocd-image-updater` and `base` each show `OrphanedResourceWarning` with 1 orphaned resource.

Plan step 9 copies the environment into the homelab repository at the merge commit of this change. Thus this change must merge first, so that the copy of `k8s/argocd/apps/projects.yaml` admits the homelab repository with no edit.

### Proposed Solution & Architectural Design

- AppProject `homelab` (`k8s/argocd/apps/projects.yaml`): add `https://github.com/dan-petty/homelab` to `sourceRepos`, and add `{group: '', kind: Secret, name: repo-homelab}` to `orphanedResources.ignore`.
- AppProject `homelab-system`: add `https://github.com/dan-petty/homelab` to `sourceRepos`. This project has no `orphanedResources` block, so it needs no ignore entry.
- Both AppProjects keep `https://github.com/dan-petty/devops-cli`, because Application `devops` reads `k8s/devops` from devops-cli after the switch.
- No Application changes. At the merge, Application `cluster` syncs the 2 AppProjects. No workload restarts, because no pod template changes.
- Add the runbook `docs/HOMELAB_REPO_SWITCH.md` for plan steps 10 to 17: the drift check and the baseline, the switch with `devops argo cd apps bootstrap-gitops`, the freeze and soak, prune on, the live patches into homelab, the deletion of the override path and of the environment files, and the revert. Each step has a check and a revert. Each check prints names, keys, counts or exit codes only. The soak count is 12 Applications with the deployment subscription.
- `k8s/README.md` tells that both AppProjects admit the homelab repository and links the runbook.
- An invariant test in `tests/invariants/test_k8s_argocd_apps.py` checks the new entries.

Acceptance:
- After the merge, `kubectl get appproject homelab homelab-system -n argocd -o jsonpath='{.spec.sourceRepos}'` lists `https://github.com/dan-petty/homelab` for each project.
- All 34 Applications stay Synced.
- The `OrphanedResourceWarning` for `repo-homelab` goes away on `argocd`, `argocd-image-updater` and `base`.

### Target Subsystem

Kubernetes & Minikube Automation

### Existing Tool Considered

Argo CD AppProject `sourceRepos` and `orphanedResources.ignore` (https://argo-cd.readthedocs.io/en/stable/user-guide/projects/) cover the need. The change only adds entries to them. The runbook uses existing tools: `devops argo cd apps bootstrap-gitops`, `argocd app diff`, `kubectl`, `jq` and `devops prometheus query`. Cost to build: about 0.4M tokens and 2 hours; nearly 0 to keep, because the runbook ends with step 17.

### Standards Compliance

- [x] I confirm this proposal aligns with AGENTS.md engineering principles (cyclomatic complexity <= 10, nesting <= 4 blocks, zero bare exceptions, tests that cover the changed lines).
- [x] I am willing to submit a pull request implementing this feature with accompanying tests.


Source: https://github.com/dan-petty/devops-cli/issues/5134

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
