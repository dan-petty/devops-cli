# Switch Argo CD to the homelab repository

This runbook moves the source of the homelab environment from devops-cli to the private repository dan-petty/homelab. It gives steps 10 to 17 of the plan of #5134 (tracker #5120). Each step gives the work, the check after it and the revert.

Before step 10, these items are done:

- The owner made the repository credential, Secret `repo-homelab` in namespace `argocd`. `argocd repo list --core` shows the homelab repository as Successful.
- The AppProjects `homelab` and `homelab-system` admit `https://github.com/dan-petty/homelab` and keep `https://github.com/dan-petty/devops-cli` (`k8s/argocd/apps/projects.yaml`). Project `homelab` ignores Secret `repo-homelab` as an orphan.
- dan-petty/homelab#23 copied the environment files at devops-cli commit S. Its metadata file gives S, the release vX, the list of environment paths and their checksums.

## Rules for every step

- Public text, such as a pull request or issue comment, holds exit codes, counts and key names only. The live objects hold the real hosts. So never post `argocd app diff` output, Application YAML, a patch list or a host.
- This page names roles, not machines: `<homelab-checkout>` and `<devops-cli-checkout>` are clones of the two repositories, and `<temp-dir>` is a new temporary directory.
- Do not change the name of an Application from S until step 13 is done. 31 of the 34 Applications have the finalizer `resources-finalizer.argocd.argoproj.io`, so a prune of an Application also deletes its objects.
- Do not start a step while `devops k8s volume move` or `devops infra apply` runs.

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

2. **Paused Applications and volume moves.** Both counts must be 0. A volume move pauses an Application with `automated.enabled: false`, and the bootstrap of step 11 sets it to `true` again.

   ```bash
   kubectl -n argocd get applications -o json | jq '[.items[] | select(.spec.syncPolicy.automated.enabled == false)] | length'
   kubectl get pods,pvc -A -l app.kubernetes.io/component=volume-move -o name | wc -l
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
2. Compare the environment paths at S with `origin/main`. Use the path list of the metadata file of the homelab copy.

   ```bash
   git diff --stat <S> origin/main -- <environment-paths>
   git diff --quiet <vX> origin/main -- k8s/devops/dashboards; echo $?
   ```

3. If either command shows a change, sync the copy again with a homelab pull request. Then run the checks of dan-petty/homelab#23 again.
4. Record the baseline in a comment on #5134: shared checks 1, 3 and 4, and the exit counts of check 5.
5. Run shared check 2.

Check: Both diffs are empty. Shared check 2 gives 0 and 0. On 2026-11-13, the baseline had 34 Applications, `requiresPruning` only on `argocd` (3 objects), the keys `images` and `patches` on `devops`, and `patches` on `ingress` and `mattermost`.

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

5. `bootstrap` syncs `cluster` from homelab, and `cluster` applies the 32 child Applications. Wait until `uv run devops argo cd apps status bootstrap` and `uv run devops argo cd apps status cluster` show Synced.

Check:

- Shared check 7 prints only 2 lines: Application `devops` with `k8s/devops`, and Application `prometheus` with its value file `k8s/devops/monitoring/prometheus-rules-values.yaml` after the `$` ref. Every other source names homelab.
- Shared check 1 equals the baseline.
- Shared check 5 gives exit code 0 for all 34 Applications.
- Shared check 6 gives 0.
- Shared check 3 equals the baseline.
- Shared check 4 equals the baseline.
- Shared check 9 gives 0 and 0.

Post the exit codes and counts on #5134. Prune is off in all 34 Applications of the copy, `bootstrap` and `cluster` included. The Applications keep their names, so their tracking IDs do not change: Argo CD makes no orphan and no duplicate.

Revert: [Revert of the switch](#revert-of-the-switch).

## Step 12: freeze and soak

Who: an agent. A person merges the pull request.

1. Open a devops-cli pull request with a temporary CI check. The check refuses a change to an environment path that homelab now holds. The check starts after the switch, not at S, because devops-cli `main` deployed the environment until the switch.
2. In the same pull request, change the GitOps section of `k8s/README.md`: Argo CD reads the environment from homelab, and Bootstrap and Recovery use the bootstrap file of a homelab checkout.
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

Revert: Remove the check with a devops-cli pull request.

## Step 13: prune on, leaves first

Who: an agent. A person merges each pull request.

1. Homelab pull request A turns prune on in the 32 child Applications.
2. After pull request A is synced and its checks pass, homelab pull request B turns prune on in `cluster` and `bootstrap`. One pull request cannot make this order sure.

Check, before each merge:

- Shared check 5 gives exit code 0 for all 34 Applications.
- Shared check 3 equals the baseline.
- Shared check 6 gives 0.
- Shared check 8 prints nothing.

Revert: `git revert` of the homelab pull request.

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

- All 34 Applications are Synced, and shared check 5 gives exit code 0 for each.
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

In one devops-cli pull request, delete the environment files of the path list, the overlay `k8s/overlays/homelab/devops`, the environment managers of Renovate, the environment tests, gate modules and fixtures, and the freeze check of step 12. Scope `.github/workflows/image-pins.yml` to `k8s/devops/**`, and keep it. Change each OpenSpec spec that names a deleted path.

Check:

- Shared check 7 prints only `k8s/devops` of Application `devops` and `k8s/devops/monitoring/prometheus-rules-values.yaml` of Application `prometheus`, so no live source names a deleted path.
- `git grep` finds no file of the path list.
- `uv run devops ci` passes.
- All 34 Applications stay Synced.

Revert: `git revert` of the devops-cli pull request. After this step, the revert of the switch is not possible.

## Revert of the switch

Use this revert from step 11 until step 17.

1. Run shared check 8 with `<devops-cli-checkout>` in place of `<homelab-checkout>`. It must print nothing. If the name sets differ, stop. The devops-cli `bootstrap` and `cluster` have prune on, so a sync deletes each Application that devops-cli does not hold, together with its objects. Make the two sets equal with a pull request first.
2. Apply the bootstrap file of a devops-cli `main` checkout.

   ```bash
   git -C <devops-cli-checkout> fetch origin main
   git -C <devops-cli-checkout> show origin/main:k8s/argocd/bootstrap/bootstrap.yaml > <temp-dir>/bootstrap.yaml
   uv run devops argo cd apps bootstrap-gitops --root-app <temp-dir>/bootstrap.yaml
   ```

Check: Shared checks 1, 3 and 4 equal the baseline, shared check 9 gives 0 and 0, and shared check 5 gives exit code 0 for all 34 Applications. The patches and the digests stay, because the field managers `kubectl-patch` and Image Updater also own them.
