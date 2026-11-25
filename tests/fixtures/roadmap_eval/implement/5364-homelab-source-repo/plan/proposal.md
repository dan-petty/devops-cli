# Proposal: #5364

## Why
#5134 moves the source of the homelab environment of Argo CD from devops-cli to the private repository dan-petty/homelab. Argo CD refuses an Application source whose repository is not in the `sourceRepos` of its AppProject. Today the AppProjects `homelab` and `homelab-system` admit devops-cli and the Helm chart repositories only, so the switch of plan step 11 would fail with a refused source. The owner made the repository credential Secret `repo-homelab` in namespace `argocd` on 2026-11-13. No Application tracks it, so project `homelab` reports it as an orphan: Applications `argocd`, `argocd-image-updater` and `base` each show `OrphanedResourceWarning` with 1 orphaned resource. This change (#5364) is plan step 8 of #5134 and is part of #5134; the later steps stay open on #5134.

## What Changes
- AppProjects `homelab` and `homelab-system` (`k8s/argocd/apps/projects.yaml`) add `https://github.com/dan-petty/homelab` to `sourceRepos` and keep `https://github.com/dan-petty/devops-cli`. Application `devops` reads `k8s/devops` from devops-cli after the switch, so both stay.
- AppProject `homelab` adds Secret `repo-homelab` to `orphanedResources.ignore`. Project `homelab-system` has no `orphanedResources` block, so it reports no orphan and needs no entry.
- A new runbook, `docs/HOMELAB_REPO_SWITCH.md`, gives plan steps 10 to 17 with the work, the check and the revert of each step: the drift check and the baseline, the switch with `devops argo cd apps bootstrap-gitops`, the freeze and soak, prune on, the live patches into homelab, the deletion of the override path, the homelab environment checks, the deletion of the environment files, and the revert of the switch. It names roles only: no host name, no address and no real domain. `.nav.yml` adds it to the Guides tab.
- `k8s/README.md` says in its GitOps section that both AppProjects admit the homelab repository and that project `homelab` ignores the credential, and it links the runbook. The sentence that sent the private values to a repository on the in-cluster Gitea (#1291) now names step 14 of the runbook, because the owner picked dan-petty/homelab on 2026-11-12.
- The AppProjects are manifests that Argo CD applies, so the change has a delta of the capability `homelab-project-destinations`.

The change fits one pull request. The private-domain guard of plan step 8 merged before this change (#5295).

## Capabilities
- `homelab-project-destinations` (modified): ADDED requirements "Homelab AppProjects admit the homelab repository" and "Project homelab ignores the homelab repository credential".

## Impact
- At the merge, Application `cluster` syncs the two AppProjects. Each gets one more `sourceRepos` entry, and `homelab` gets one more `orphanedResources.ignore` entry. No Application changes its source, so all 34 Applications stay Synced. No workload restarts, because no pod template changes.
- The `OrphanedResourceWarning` of `argocd`, `argocd-image-updater` and `base` goes away, because `repo-homelab` was their one orphan.
- dan-petty/homelab#23 copies `projects.yaml` at commit S, which comes after this change. So the copy admits homelab and ignores the credential with no edit, and its checksum check stays true.
- Rollback: `git revert`. Nothing reads the homelab repository before the switch, so a revert only brings the warning back.

## Feasibility
- `git show origin/main:k8s/argocd/apps/projects.yaml` (origin/main `19d13d7ca`): `sourceRepos` of `homelab` (line 12) and `homelab-system` (line 140) list devops-cli and no homelab entry. Only `homelab` has an `orphanedResources` block (`warn: true`, line 54).
- `kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=repository -o name` gives `secret/repo-homelab`, and its labels are `{"argocd.argoproj.io/secret-type":"repository"}`. The issue comment of the owner of 2026-11-13 records `argocd repo list --core --refresh hard` as Successful.
- The untracked objects with no owner in namespace `argocd` are `argocd-initial-admin-secret`, `argocd-notifications-secret`, `argocd-redis` and `repo-homelab` (Secrets), `kube-root-ca.crt` and the ServiceAccount `default`. Argo CD skips the last two, and project `homelab` ignores the first three. So `repo-homelab` is the 1 orphaned resource of `argocd`, `argocd-image-updater` and `base`, the 3 Applications of project `homelab` in namespace `argocd`.
- `kubectl get applications -n argocd` lists 34 Applications, all Synced: 32 Healthy and 2 Progressing. `argocd app diff --core --exit-code` (argocd v3.5.4) gave exit code 0 for all 34.
- AppProject `default`, the project of `bootstrap` and `cluster`, has `sourceRepos: ["*"]`, so the two root Applications need no change to read homelab.
- `kubectl diff -f k8s/argocd/apps/projects.yaml` (a server dry run) shows only the 2 new `sourceRepos` entries, the new ignore entry and the generation of each project. The tracking annotation that it also shows comes from Argo CD at each sync.
- The runbook commands were probed against the live cluster, read only, and print names, keys, counts or exit codes only. `kubectl apply --dry-run=client -o json` merged the live object into the output, so the runbook reads files with `kubectl create --dry-run=client`. `argocd --core` failed with `configmap "argocd-cm" not found` in a context whose namespace is not `argocd`, so the runbook uses a kubeconfig copy with the namespace `argocd`.

## Existing Tool Considered
- Argo CD AppProject `sourceRepos` and `orphanedResources.ignore` (https://argo-cd.readthedocs.io/en/stable/user-guide/projects/) cover the need. The change only adds entries to them.
- The runbook uses the existing tools: `devops argo cd apps bootstrap-gitops`, `argocd app diff`, `kubectl`, `jq` and `devops prometheus query`.
- Cost to build: about 0.4M tokens and 2 hours, and nearly 0 to keep, because the runbook ends with step 17.
- Internal code that the change deletes: none.
