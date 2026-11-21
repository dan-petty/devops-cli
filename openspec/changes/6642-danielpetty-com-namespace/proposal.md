# Proposal: #6642

## Why

The private repository dan-petty/danielpetty.com will run on this cluster at `danielpetty-com.<domain>` (#6642). The site repository keeps its own Kustomize manifests (dan-petty/danielpetty.com#29). The platform side does not exist yet:

- `k8s/namespaces.yaml` has no namespace for the site.
- No AppProject admits the site repository. Project `homelab` allows every cluster-scoped kind, so a second repository in it could write any cluster-scoped object.
- The event-stream of the site reads `NOTE_API_KEY`, the bearer key of `POST /api/notes`, and an optional `GITHUB_TOKEN`. No row of the cluster Secret table holds them.
- `monitoring-default-perimeter` lets Alloy reach only the namespaces and ports of its egress list, so Alloy cannot scrape the metrics port of the site.
- Project `homelab` reports the repository credential Secret of the site as an orphan in namespace `argocd`.

## What Changes

- `k8s/namespaces.yaml`: namespace `danielpetty-com` with Pod Security `restricted` for enforce, warn and audit, and with `argocd.argoproj.io/sync-options: Prune=false,Delete=false`.
- `k8s/argocd/apps/projects.yaml`: the new AppProject `danielpetty-com`. Its only source repository is `https://github.com/dan-petty/danielpetty.com`, and its only destination is namespace `danielpetty-com`. It sets `clusterResourceWhitelist: []` and puts `Role` and `RoleBinding` in `namespaceResourceBlacklist`. It warns on orphans and ignores Secret `event-stream`, which the push writes.
- Project `homelab`: an orphan ignore entry for Secret `repo-danielpetty-com`, as for `repo-homelab`.
- `src/devops_cli/k8s/cluster_secrets.py`: stack `danielpetty-com` goes into `DETACHED_STACKS`. The new row `danielpetty-com/event-stream` holds `NOTE_API_KEY` (keyring `danielpetty_com_note_api_key`, required, generator `token_urlsafe(32)`) and `GITHUB_TOKEN` (keyring `danielpetty_com_github_token`, optional, no generator), and restarts `deployment/event-stream`. Both keyring keys are keyring-only: no setting reads them.
- `k8s/monitoring/networkpolicy.yaml`: egress from the monitoring namespace to namespace `danielpetty-com` on TCP 9090, the metrics port of dan-petty/danielpetty.com#28.
- `k8s/README.md`: the two rows of the Secret in the Cluster Secrets table, a note on the detached stack, and the repository Secret `repo-danielpetty-com` in the GitOps section.
- `src/devops_cli/config/defaults.py`: the comment of `DEFAULT_ROADMAP_PROJECT_REVIEW_NAMESPACES` says that the list holds the namespaces of this project, and that namespace `danielpetty-com` holds the workloads of another project. The list does not change.
- The push, `deploy-stack` and the manifests change in a way that a person sees, so the change has spec deltas: the new capability `danielpetty-com-platform`, and added requirements of `homelab-project-destinations` and `k8s-network-policies`.
- The change adds no Argo CD Application. #6644 adds it after a person pushes the Secret.

## Capabilities

- `danielpetty-com-platform` (new): the namespace, the AppProject and the cluster Secret of the site.
- `homelab-project-destinations` (added requirement): project `homelab` ignores the repository credential of the site as an orphan.
- `k8s-network-policies` (added requirement): the monitoring perimeter reaches the metrics port of the site.

## Impact

- After the merge, Application `base` creates namespace `danielpetty-com`, and Application `cluster` creates AppProject `danielpetty-com`. No workload runs in the namespace until #6644.
- `devops k8s push-secrets --stack danielpetty-com` and each `deploy-stack` run push the Secret wherever namespace `danielpetty-com` exists. A push with an empty keyring generates the note key and skips the GitHub token.
- `devops k8s deploy-stack` dry runs list one more Secret, with the condition `(if namespace danielpetty-com exists)`.
- No new dependency. No new setting. No config file and no ConfigMap must change.
- The change fits one pull request.

## Feasibility

- The premise holds on origin/main e01bf8458. `git grep` finds no freeze check of #5134 plan step 12 under `src/` or `.github/`, so the change goes to this repository.
- The cited lines hold on origin/main: `k8s/namespaces.yaml` declares 14 namespaces and none for the site; project `homelab` has `clusterResourceWhitelist` `*/*`; project `trial` has `clusterResourceWhitelist: []`; `DETACHED_STACKS` is `("devops",)`.
- `_push_stacks` in `src/devops_cli/commands/k8s/cluster_secret_push.py` accepts each stack of the table, so a new row makes `--stack danielpetty-com` valid. `deploy-stack` pushes a detached stack only where its namespace exists (`src/devops_cli/commands/k8s/stack_lifecycle.py`, `_push_stacks_for`), and `push-secrets` skips a row whose namespace does not exist (`src/devops_cli/k8s/secret_push.py`, `_present`).
- `kubectl explain appproject.spec` on the cluster (Argo CD v3.6.2, read-only) lists `clusterResourceWhitelist`, `namespaceResourceBlacklist`, `orphanedResources`, `sourceRepos` and `destinations`. `kubectl get ns danielpetty-com` gives `NotFound`.

## Existing Tool Considered

- Argo CD AppProject is the open tool that fences a repository to its namespaces and kinds. The change uses it and builds no fence of its own.
- The cluster Secret table and `devops k8s push-secrets` already write, generate and adopt each Secret value. The change adds one row and builds no new code path.
- The change deletes no internal code.
