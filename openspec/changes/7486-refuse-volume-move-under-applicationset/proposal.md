# Proposal: #7486

## Why

`devops k8s volume move` pauses each tracked Argo CD Application by patching `spec.syncPolicy.automated.enabled` to `false` (#7486). When an ApplicationSet owns an Application, the ApplicationSet controller restores `spec` from its template unless `spec.ignoreApplicationDifferences` excludes the paused path. On 2026-11-27, the homelab ApplicationSet `service-workloads` (whose `ignoreApplicationDifferences` listed only `/spec/source/kustomize/images`) reverted the pause on `danielpetty-com` within about 30 s, and a new automated sync started. A move under a reverted pause risks recreating a deleted claim from git (as in `dan-petty/homelab#472`).

## What Changes

- Before changing anything in the cluster, `plan_volume_move` inspects `metadata.ownerReferences` on each Application it would pause.
- When an `argoproj.io/v1alpha1` `ApplicationSet` owns one of those Applications, the plan reads that ApplicationSet's `spec.ignoreApplicationDifferences` and checks whether a JSON pointer applicable to the Application covers `/spec/syncPolicy/automated/enabled` (such as `/spec`, `/spec/syncPolicy`, `/spec/syncPolicy/automated`, or `/spec/syncPolicy/automated/enabled`).
- When no pointer covers that path, the plan raises `VolumeMoveRefusedError` naming the ApplicationSet, the Application, and `/spec/syncPolicy` (`ignoreApplicationDifferences`), and sends no write to the cluster.
- `dry_run_volume_move` lists the conditional `kubectl get applicationset` read in its request plan.
- This change alters observable `devops k8s volume move` refusal and dry-run behavior, so it carries a spec delta on `local-path-volume-placement`. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: refuse a volume move when an owning ApplicationSet does not ignore `/spec/syncPolicy/automated/enabled` in `spec.ignoreApplicationDifferences`.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md`

## Feasibility

- Confirmed against the homelab incident reported in #7486: ApplicationSet `service-workloads` held only `/spec/source/kustomize/images` in `spec.ignoreApplicationDifferences`, causing `danielpetty-com` to lose its `spec.syncPolicy.automated.enabled: false` patch within 30 s.
- Confirmed against `src/devops_cli/k8s/volume_move.py`: `_pause_order` already reads `kubectl get applications -n argocd -o json`, whose items carry `metadata.ownerReferences`, and `_pause_args` patches `{"spec": {"syncPolicy": {"automated": {"enabled": enabled}}}}`.

## Existing Tool Considered

`argoproj/argo-cd` (Apache-2.0, maintained, in-use) provides `ApplicationSet` `metadata.ownerReferences` and `spec.ignoreApplicationDifferences` via Kubernetes CRDs (`kubectl get applicationset`), but provides no pre-move guard that verifies a pause survives ApplicationSet reconciliation. This change adds the pre-check and refusal in `src/devops_cli/k8s/volume_move.py` and the refusal message in `src/devops_cli/lang/en/messages.py` (estimated cost: ~8,000 tokens and 2 hours to build, ~1,000 tokens per later fix; no new dependency). No existing internal code is deleted.

## Dependencies

None.
