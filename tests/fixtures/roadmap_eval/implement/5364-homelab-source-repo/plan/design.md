# Design

## Decisions

### Add the homelab URL beside devops-cli
Both AppProjects add the exact URL `https://github.com/dan-petty/homelab` after devops-cli. After the switch, every Application reads homelab, except Application `devops`, which reads `k8s/devops` from devops-cli `main`, and one `$values` ref of Application `prometheus`, which reads the product rules from devops-cli `main`. So both repositories stay in both projects. The change keeps devops-cli for the revert of the switch too.

### The ignore entry in project `homelab` only
Argo CD reports orphans only for a project with an `orphanedResources` block. Only `homelab` has one, and it lists `argocd` in its destinations, so it is the project that reports `repo-homelab`. The live warnings agree: `argocd`, `argocd-image-updater` and `base`, all in project `homelab` and namespace `argocd`, each show 1 orphaned resource. The entry names the Secret exactly, as each other Secret entry does.

### The runbook is a page of its own
The steps go across devops-cli, homelab and the cluster, and each step has a check and a revert. One page in `docs/` keeps them in order. The GitOps section of `k8s/README.md` links it, and `.nav.yml` adds it to the Guides tab, because the site build fails for a page that no tab holds.

### Checks print names, keys, counts and exit codes only
The live Applications hold the real hosts in their patches. Each shared check of the runbook prints only names, keys, counts or exit codes, and sends the `argocd app diff` output to `/dev/null`. Step 14 writes each patch list to a file in a temporary directory with `jq` and compares it with `cmp -s`, so no host goes to the output.

### Prune results from the switch time on
The live `operationState` of `cloudnative-pg` and `ingress` holds 2 old `Pruned` results, from 2026-11-12 and 2026-10-29. A count of all results would not give 0 after a clean switch. So the check counts only the syncs that started at or after the switch time.

### Deployments only for Applications that synced
The trigger `on-deployed` (`k8s/argocd/values.yaml`, `oncePer: app.status.operationState?.syncResult?.revision`) sends once for each sync revision. Argo CD runs an automated sync only for an OutOfSync Application. The switch keeps every render the same, so it makes no sync and no deployment. The soak check of step 12 therefore reads deployments only for the Applications that synced a homelab revision in the soak.

### The revert stops when the name sets differ
The plan said to run the revert with `prune: false` when the Application name sets differ. Path `k8s/argocd/bootstrap` of devops-cli holds `bootstrap.yaml` and `cluster.yaml`, both with `prune: true`, and `bootstrap` syncs its own file. So a `prune: false` in the applied root lasts only until the first sync of `bootstrap`, and `cluster` then prunes each Application that devops-cli does not hold. The finalizer `resources-finalizer.argocd.argoproj.io` (31 of the 34 Applications) then deletes the objects of that Application. The runbook stops the revert until a pull request makes the sets equal.

### Read files with `kubectl create --dry-run=client`
The shared check of the name sets and the patch check of step 14 read the homelab files. `kubectl apply --dry-run=client -o json` merges the live object into its output: a probe gave the same patch list for git and for the live Application, but git holds no patch. `kubectl create --dry-run=client` reads the file only. The devcontainer has no `yq`.

### The README Recovery changes with the freeze
At this merge, Argo CD still reads devops-cli, so the Bootstrap and Recovery steps of `k8s/README.md` stay true. Step 12 of the runbook changes them in the pull request of the freeze check, which merges after the switch.

## Rejected alternatives

- **Add the ignore entry only in the homelab copy.** The comment of the owner of 2026-11-13 said that the entry ships with dan-petty/homelab#23. Rejected: the copy takes `projects.yaml` from devops-cli at commit S, after this change, and its checksum check compares each copied file with S. An entry in devops-cli removes the 3 warnings now, and the copy gets it with no edit.
- **A glob such as `https://github.com/dan-petty/*` in `sourceRepos`.** Rejected: it admits every repository of the account, and the switch needs one.
- **The glob `repo-*` in the ignore list.** Rejected: the owner made one credential with a fixed name, and a glob would also hide a credential that someone adds by mistake.
- **A section of `k8s/README.md`.** Rejected: the steps go across two repositories and the cluster, and the README describes the state of the environment. A page of its own keeps the order of the steps, and the README links it.
- **`argocd app diff` with no kubeconfig copy.** Rejected: `argocd --core` reads the namespace of the current kube context, and the command failed with `configmap "argocd-cm" not found` in a context with another namespace. A change of the shared kubeconfig would change the namespace for every other session of the same home.
