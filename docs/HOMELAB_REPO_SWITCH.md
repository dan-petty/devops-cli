# Switch Argo CD to the homelab repository

This runbook moves the source of the homelab environment from devops-cli to the private repository dan-petty/homelab. It gives steps 10 to 17 of the plan of #5134 (tracker #5120). Each step gives the work, the check after it and the revert.

**Status: step 17 deletes the environment files from devops-cli (#7290). The environment of the cluster lives only in dan-petty/homelab, and the [revert of the switch](#revert-of-the-switch) is no longer possible.** This page stays as the record of the switch. Its paths of `k8s/` outside `k8s/devops` are files of dan-petty/homelab now.

Before step 10, these items are done:

- The owner made the repository credential, Secret `repo-homelab` in namespace `argocd`. `argocd repo list --core` shows the homelab repository as Successful.
- The AppProjects `homelab` and `homelab-system` admit `https://github.com/dan-petty/homelab` and keep `https://github.com/dan-petty/devops-cli` (`k8s/argocd/apps/projects.yaml`). Project `homelab` ignores Secret `repo-homelab` as an orphan.
- dan-petty/homelab#23 copied the environment files at devops-cli commit S. Its metadata file `k8s/devops-cli-copy.json` gives S, the release vX, the list of environment paths and their checksums, and the list `applications` with the names of the Applications of the copy.

## Rules for every step

- Public text, such as a pull request or issue comment, holds exit codes, counts and key names only. The live objects hold the real hosts. So never post `argocd app diff` output, Application YAML, a patch list or a host.
- This page names roles, not machines: `<homelab-checkout>` and `<devops-cli-checkout>` are clones of the two repositories, and `<temp-dir>` is a new temporary directory.
- The steps give no fixed count of Applications, because each new Application changes the count. "Each Application of the copy" means each name of the list `applications` of `k8s/devops-cli-copy.json` in homelab. "Each child Application of `cluster`" means each Application of the copy, without `bootstrap` and `cluster`. The dated baselines of step 10 give the counts of earlier days.
- Do not change the name of an Application from S until step 13 is done. Most Applications have the finalizer `resources-finalizer.argocd.argoproj.io`, so a prune of an Application also deletes its objects.
- Do not start a step while `devops k8s volume move`, `devops infra apply` or a `devops infra node` command runs.

## Shared checks

The steps use these checks. Each check prints names, keys, counts or exit codes only.

`argocd --core` reads the namespace of the current kube context. Use a copy of the kubeconfig whose context has the namespace `argocd`. The copy holds the cluster credential, so delete it when the step ends.

```bash
(umask 077; kubectl config view --raw --minify --flatten > <temp-dir>/kubeconfig)
export KUBECONFIG=<temp-dir>/kubeconfig
kubectl config set-context --current --namespace argocd
```

1. **Sync and health.** The count of Applications, then a count for each pair of sync and health status.

   ```bash
   kubectl -n argocd get applications -o json | jq '.items | length'
   kubectl -n argocd get applications -o json \
     | jq -r '[.items[] | .status.sync.status + "/" + .status.health.status] | group_by(.) | map("\(.[0]) \(length)") | .[]'
   ```

2. **Paused Applications and volume moves.** The three counts must be 0. A volume move pauses an Application with `automated.enabled: false`, and the bootstrap of step 11 sets it to `true` again.

   ```bash
   kubectl -n argocd get applications -o json | jq '[.items[] | select(.spec.syncPolicy.automated.enabled == false)] | length'
   kubectl get pvc -A -l app.kubernetes.io/component=volume-move -o name | wc -l
   kubectl get pods -A -l app.kubernetes.io/name=pv-migrate -o name | wc -l
   ```

3. **Objects that need a prune.** The Applications that have an object to prune, with the kinds of those objects.

   ```bash
   kubectl -n argocd get applications -o json \
     | jq -r '.items[] | select(any(.status.resources[]?; .requiresPruning)) | .metadata.name + " " + ([.status.resources[] | select(.requiresPruning) | .kind] | join(","))'
   ```

4. **Override keys.** The keys of `spec.source.kustomize` on the three Applications that have deploy-time overrides (#1290). The check prints the keys, never the values.

   ```bash
   kubectl -n argocd get applications -o json \
     | jq -r '.items[] | select(.metadata.name | IN("devops", "ingress", "mattermost")) | .metadata.name + ": " + ((.spec.source.kustomize // {}) | keys | join(","))'
   ```

5. **Diff exit codes.** `argocd app diff` for each Application, with its output sent to `/dev/null`. Each exit code must be 0.

   ```bash
   kubectl -n argocd get applications -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' \
     | while read -r app; do
         argocd app diff "$app" --core --exit-code >/dev/null 2>&1
         echo "$app $?"
       done \
     | awk '{count[$2]++} $2 != 0 {print "diff:", $1, $2} END {for (code in count) print "exit", code, count[code]}'
   ```

6. **Prune results.** The count of `Pruned` and `PruneSkipped` results in the syncs that started at or after `<switch-time>` (UTC, ISO 8601). Older syncs keep their results, so the check reads only the new ones.

   ```bash
   kubectl -n argocd get applications -o json \
     | jq --arg t '<switch-time>' '[.items[] | select(.status.operationState.startedAt >= $t) | .status.operationState.syncResult.resources[]? | select(.status == "Pruned" or .status == "PruneSkipped")] | length'
   ```

7. **devops-cli paths.** Each path that an Application reads from devops-cli, as the Application name and the path: the `path` of a git source, and each Helm value file that starts with the `$` ref of a devops-cli source.

   ```bash
   kubectl -n argocd get applications -o json \
     | jq -r --arg repo https://github.com/dan-petty/devops-cli '.items[] | .metadata.name as $n | (.spec.sources // [.spec.source]) as $s | [$s[] | select(.repoURL == $repo and .ref != null) | "$" + .ref + "/"] as $refs | ($s[] | select(.repoURL == $repo and .path != null) | "\($n) \(.path)"), ($s[] | .helm.valueFiles[]? | select(. as $f | any($refs[]; . as $r | $f | startswith($r))) | "\($n) \(.)")'
   ```

8. **Name sets.** The Application names of the homelab files and of the cluster. `diff` must print nothing. `kubectl create --dry-run=client` reads the files only.

   ```bash
   diff <(kubectl create --dry-run=client -f <homelab-checkout>/k8s/argocd/apps/ -f <homelab-checkout>/k8s/argocd/bootstrap/ -o name | sed -n 's|^application.argoproj.io/||p' | sort) \
        <(kubectl -n argocd get applications -o name | sed 's|^application.argoproj.io/||' | sort)
   ```

9. **Placeholder alert and comparison errors.** Both values must be 0.

   ```bash
   uv run devops prometheus query 'count(ALERTS{alertname="IngressServesPlaceholderHost",alertstate="firing"}) or vector(0)'
   kubectl -n argocd get applications -o json | jq '[.items[] | .status.conditions[]? | select(.type == "ComparisonError")] | length'
   ```

## Step 10: drift check, baseline and pre-checks

Who: an agent, on the day of the switch.

1. In `<devops-cli-checkout>`, run `git fetch origin main`.
2. Compare the environment files at S with `origin/main`. The environment files are the files of `k8s` without the 2 product folders `k8s/devops` and `k8s/overlays/homelab/devops`. Use this pathspec, not the path list of the metadata file. The path list holds only the files at S, so it does not show a new environment file that devops-cli adds after S. devops-cli has no copy of the path list, and `git diff` with no path after `--` compares the full repository.

   ```bash
   git diff --stat <S> origin/main -- k8s ':(exclude)k8s/devops' ':(exclude)k8s/overlays/homelab/devops'
   git diff --quiet <vX> origin/main -- k8s/devops/dashboards; echo $?
   ```

3. If either command shows a change, sync the copy again with a homelab pull request. Then run the checks of dan-petty/homelab#23 again on the branch of that pull request. Run `argocd app diff --local` only on a throwaway export, never on a checkout. `argocd app diff <app> --core --local <folder>` writes the live overrides of the Application, which hold the real hosts, into the `kustomization.yaml` files of the folder: `kustomize edit` writes the images, and a file write adds the patches. `git archive` exports the last commit, so commit the sync first. Delete the export after the diff, because it then holds the real hosts.

   ```bash
   mkdir <temp-dir>/export
   git -C <homelab-checkout> archive HEAD | tar -x -C <temp-dir>/export
   argocd app diff <app> --core --local <temp-dir>/export/<path-of-the-app>
   rm -rf <temp-dir>/export
   ```

4. Record the baseline in a comment on #5134: shared checks 1, 3 and 4, and the exit counts of check 5.
5. Run shared check 2.

Check: The 2 `git diff` commands of item 2 show no change, with S and vX of the last sync. `git -C <homelab-checkout> status --porcelain` prints nothing, and `<temp-dir>/export` does not exist. Shared check 2 gives 0 and 0.

The dated baselines of earlier days, for comparison:

- On 2026-11-13, the baseline had 34 Applications, `requiresPruning` only on `argocd` (3 objects), the keys `images` and `patches` on `devops`, and `patches` on `ingress` and `mattermost`. On 2026-11-12, 31 of the 34 Applications had the finalizer `resources-finalizer.argocd.argoproj.io`.
- On 2026-11-22, the baseline had 36 Applications: 34 Synced and Healthy, and 2 Synced and Progressing. `requiresPruning` was only on `argocd` (3 objects). 33 of the 36 Applications had the finalizer `resources-finalizer.argocd.argoproj.io`. `argocd`, `bootstrap` and `cluster` had no finalizer.

Revert: None. The step changes nothing.

## Step 11: the switch

Who: an agent, after the owner says go. The agent asks for go when steps 1 to 10 of the plan pass their checks.

Before the step, these items must be true:

- The release vX holds the fix of #5294, so `devops k8s deploy-stack` can fetch an Application from the private repository.
- The owner made the credential and installed the GitHub App `devops-cli-argocd` on homelab with Contents: read and Deployments: write.
- Shared check 2 gives 0 and 0.

Do these steps:

1. Write the bootstrap file of homelab `origin/main` to the temporary directory.

   ```bash
   git -C <homelab-checkout> fetch origin main
   git -C <homelab-checkout> show origin/main:k8s/argocd/bootstrap/bootstrap.yaml > <temp-dir>/bootstrap.yaml
   ```

2. Preview the apply. The dry run makes no request.

   ```bash
   uv run devops argo cd apps bootstrap-gitops --root-app <temp-dir>/bootstrap.yaml --dry-run
   ```

3. Record the time as `<switch-time>` with `date -u +%Y-%m-%dT%H:%M:%SZ`.
4. Apply the bootstrap file. The command creates the live `bootstrap`, or merge-patches it when it exists.

   ```bash
   uv run devops argo cd apps bootstrap-gitops --root-app <temp-dir>/bootstrap.yaml
   ```

5. `bootstrap` syncs `cluster` from homelab, and `cluster` applies each of its child Applications. Wait until `uv run devops argo cd apps status bootstrap` and `uv run devops argo cd apps status cluster` show Synced.

Check:

- Shared check 7 prints only 2 lines: Application `devops` with `k8s/devops`, and Application `prometheus` with its value file `k8s/devops/monitoring/prometheus-rules-values.yaml` after the `$` ref. Every other source names homelab.
- Shared check 1 equals the baseline.
- Shared check 5 gives exit code 0 for each Application of the copy.
- Shared check 6 gives 0.
- Shared check 3 equals the baseline.
- Shared check 4 equals the baseline.
- Shared check 9 gives 0 and 0.

Post the exit codes and counts on #5134. Prune is off in each Application of the copy, `bootstrap` and `cluster` included. The Applications keep their names, so their tracking IDs do not change: Argo CD makes no orphan and no duplicate.

Revert: [Revert of the switch](#revert-of-the-switch).

## Step 12: freeze and soak

Who: an agent. A person merges the pull request.

1. A devops-cli pull request adds a temporary check to the `k8s` row of `devops ci`: `tests/gate/k8s_checks/environment_freeze.py`, with its test `tests/invariants/test_environment_freeze_check.py`. `Static Analysis` runs the row, so the check is required. The check refuses a branch that changes an environment path that homelab now holds: a file of the pathspec of item 2 of step 10 that is not a Markdown file. The rule is by folder, so a new environment file is refused too. The check reads the changed paths with `git diff --name-only --no-renames origin/main...HEAD`, and its message names dan-petty/homelab. A Markdown file deploys nothing, and this step and step 15 change `k8s/README.md` in devops-cli, so the check does not refuse it. The check starts after the switch, not at S, because devops-cli `main` deployed the environment until the switch.
2. In the same pull request, a package rule of `.github/renovate.json` turns off the dependencies of the environment paths, so Renovate of devops-cli updates only the product folders, and homelab Renovate updates its copy. The GitOps section of `k8s/README.md` says that Argo CD reads the environment from homelab, and Bootstrap and Recovery use the bootstrap file of a homelab checkout.
3. Soak for at least 1 day and 1 release of devops-cli.

Check:

- Each Application with a GitHub deployment subscription that synced a homelab revision in the soak has a deployment on a homelab commit. Application `devops` has deployments on devops-cli commits. Argo CD makes a deployment only after a sync, so an Application with no change in the soak has no new deployment. The first command lists the Applications with the subscription. The second gives the count of deployments of one of them.

  ```bash
  kubectl -n argocd get applications -o json \
    | jq -r '.items[] | select(.metadata.annotations["notifications.argoproj.io/subscribe.on-deployed.github"] != null) | .metadata.name'
  uv run devops gh api 'repos/dan-petty/homelab/deployments?environment=<application>&per_page=1' --jq 'length'
  ```

- At the release, the value of `spec.source.kustomize.images` on Application `devops` changes. Image Updater still writes the digest.
- Shared check 9 gives 0 and 0.

Revert: Remove the check, its test and the Renovate rule with a devops-cli pull request.

## Step 13: prune on, leaves first

Who: an agent. A person merges each pull request, and the owner accepts the objects to prune.

Since dan-petty/homelab#552 (2026-11-27, owner decision), the Applications prune with no confirmation: no Application sets `Prune=confirm`, and `make k8s-parity` of homelab refuses a data object without the sync options `Prune=false,Delete=false`. The steps below record how the prune was first turned on.

Each Application that gets prune also gets the sync option `Prune=confirm`: a sync that has an object to prune waits for an approval, and so does a deletion of the Application ([Argo CD sync options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/#resource-pruning-requires-confirmation)). Without it, an infra update that homelab Renovate merges deletes each object that its render drops, with no review. The ConfigMaps of a `configMapGenerator` with a hashed name set the annotation `argocd.argoproj.io/sync-options: Prune=true`, so a rollout waits for nothing.

1. Post the objects to prune on #5134, with what each was checked against. The owner accepts the list.
2. Homelab pull request A turns prune on in each child Application of `cluster`.
3. After pull request A is synced, compare the objects of each waiting sync with the accepted list. Approve the sync only when they are equal (homelab `k8s/README.md`, Prune Approval). Until then, the Application takes no other automated sync.
4. After the approved syncs and their checks pass, homelab pull request B turns prune on in `cluster` and `bootstrap`. One pull request cannot make this order sure.

Check, before the merge of pull request A:

- Shared check 5 gives exit code 0 for each Application of the copy, or the diff holds only objects that are marked for prune.
- Shared check 3 equals the list that the owner accepted.
- Shared check 6 gives no `Pruned` result. A sync with prune off records `PruneSkipped`.
- Shared check 8 prints only the names of the Applications that an ApplicationSet owns.

Check, before the merge of pull request B:

- Each Application of the copy has no waiting sync.
- Shared check 3 gives only chart hooks. Argo CD marks a hook with the delete policy `before-hook-creation` for prune, and never prunes it.
- Shared check 5 gives exit code 0 for each Application of the copy.
- Shared check 8 prints only the names of the Applications that an ApplicationSet owns.

Revert: `git revert` of the homelab pull request. A revert does not bring back an object that a prune deleted.

## Step 14: the live patches into the homelab files

Who: an agent. A person merges the pull request.

1. In one homelab pull request, copy the live patch list of each of `devops`, `ingress` and `mattermost` into `spec.source.kustomize.patches` of its homelab file. Copy each list as it is. Write it with `jq` to a file in `<temp-dir>`, and never to the output. YAML accepts the JSON form of the list.

   ```bash
   kubectl -n argocd get application <application> -o json | jq '.spec.source.kustomize.patches' > <temp-dir>/<application>-patches.json
   ```

2. In the same pull request, narrow the `devops` entry of `ignoreDifferences` in `k8s/argocd/bootstrap/cluster.yaml` to `/spec/source/kustomize/images`. Remove the `ingress` and `mattermost` entries.
3. Delete the files in `<temp-dir>`.

The render does not change. So no Application loses its sync status, and no agent patches a live object.

Check:

- Each Application of the copy is Synced, and shared check 5 gives exit code 0 for each.
- The live patch list of each of the three Applications equals the list in its homelab file. The command prints only the exit code of `cmp`, which must be 0.

  ```bash
  cmp -s <(kubectl -n argocd get application <application> -o json | jq -S '.spec.source.kustomize.patches') \
         <(kubectl create --dry-run=client -f <homelab-checkout>/k8s/argocd/apps/<application>.yaml -o json | jq -S '.spec.source.kustomize.patches'); echo "<application> $?"
  ```

- Shared check 4 shows `images` on `devops`. Image Updater still writes it.
- Shared check 9 gives 0 and 0.
- No host goes into devops-cli or into a public comment.

Revert: `git revert` of the homelab pull request. The live patches stay, because the field manager `kubectl-patch` also owns them.

## Step 15: delete the deploy-time override path

Who: an agent. A person merges the pull request.

In one devops-cli pull request, delete the override path of #1290: the constants `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS` and `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK`, the override functions, `src/devops_cli/k8s/argocd_overrides.py`, the gate modules `tests/gate/k8s_checks/argocd_overrides.py` and `tests/gate/k8s_checks/host_overrides.py`, their tests, and the section Homelab Values at Deploy Time of `k8s/README.md`. `devops k8s deploy-stack` then writes no override. Close #1291 as superseded.

Check:

- `git grep -n CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS -- src tests` finds nothing.
- The result of `uv run devops k8s deploy-stack --stack all --dry-run` has no `argocd_overrides` entry. The stacks `infra`, `devops`, `gitea` and `chat` wrote the overrides, so the check reads all stacks.
- `uv run devops ci` passes.

Revert: `git revert` of the devops-cli pull request.

## Step 16: environment checks in homelab CI

Who: an agent. A person merges the pull request (#5296).

Homelab CI runs the environment checks that #5131 lists. The checks are advisory: they report on each pull request and never block a merge or an apply.

Check: Homelab CI runs each check of the #5131 list, and each check passes on the copy.

Revert: `git revert` of the homelab pull request.

## Step 17: delete the environment files from devops-cli

Who: an agent. A person merges the pull request.

Start this step only when these items are true:

- 7 days passed after step 11 with no revert.
- The fixture pull request of #5131 is merged.
- Step 16 is merged.

On 2026-11-26, the owner waived the first item, the 7 days, and started step 17 (#7290). The revert of the switch is no longer possible.

In one devops-cli pull request, delete the environment files of the path list, the overlay `k8s/overlays/homelab/devops`, the environment managers of Renovate, the environment tests, gate modules and fixtures, and the freeze check of step 12: its module `tests/gate/k8s_checks/environment_freeze.py`, its test `tests/invariants/test_environment_freeze_check.py`, the package rule of `.github/renovate.json` that turns off the environment paths, and the text on the check and the rule in `k8s/README.md`, `docs/TESTING.md` and `docs/SDLC.md`. Scope `.github/workflows/image-pins.yml` to `k8s/devops/**`, and keep it. Change each OpenSpec spec that names a deleted path.

Check:

- Shared check 7 prints only `k8s/devops` of Application `devops` and `k8s/devops/monitoring/prometheus-rules-values.yaml` of Application `prometheus`, so no live source names a deleted path.
- `git grep` finds no file of the path list.
- `uv run devops ci` passes.
- Each Application of the copy stays Synced.

Revert: `git revert` of the devops-cli pull request. After this step, the revert of the switch is not possible.

## Revert of the switch

The revert is no longer possible. It applied the bootstrap file of a devops-cli checkout, and step 17 (#7290) deleted that file and each other environment file from devops-cli. The owner waived the 7 day condition of step 17 on 2026-11-26. To undo a change of the environment, revert the pull request of dan-petty/homelab.
