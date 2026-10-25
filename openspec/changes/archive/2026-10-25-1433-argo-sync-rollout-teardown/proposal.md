# Proposal

## Why

DevOps CLI drops sync options in three Argo CD sync callers (#1433). Argo Rollout promote and abort calls target the main resource instead of the status subresource, and teardown's Argo CD check fails open on API errors.

This change fits one pull request.

## What Changes

- Construct Argo CD application sync bodies with top-level `prune` and `strategy.apply.force` across all three sync paths (`devops argo cd apps sync`, fleet sync, and gitops trigger).
- Include `appNamespace` in the sync request body builder where callers specify it.
- Route Rollout `promote_rollout` and `abort_rollout` mutations through `patch_namespaced_custom_object_status`.
- Clear `spec.paused` in `promote_rollout` when `spec.paused` is set.
- Report failure in `_mutate_rollout` when a patch is rejected, causing `evaluate_rollout_gate` to report `abort_failed`.
- Inspect cluster Argo CD management status in `_is_cluster_argo_managed` through `ArgoCRDService`.
- Allow teardown when the `cluster` Application returns 404 (Not Found).
- Refuse teardown with an error message when `cluster` Application lookup encounters non-404 API errors (403, 500, timeout).

## Capabilities

### New Capabilities
- `argo-sync-rollouts-teardown`: Argo CD application sync payload construction, Rollout status subresource control-plane mutations, and fail-closed Argo CD management checks.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/argo/sync.py`: New module providing shared `build_sync_request_body`.
- `src/devops_cli/commands/argo.py`: Use shared sync payload builder.
- `src/devops_cli/argo/fleet.py`: Use shared sync payload builder.
- `src/devops_cli/argo/gitops.py`: Use shared sync payload builder.
- `src/devops_cli/argo/crd.py`: Add `patch_resource_status` and update `promote_rollout` and `abort_rollout`.
- `src/devops_cli/commands/k8s/stack_lifecycle.py`: Update `_is_cluster_argo_managed` and `teardown` error handling.
- `tests/`: Add and update tests in `test_argo.py`, `test_argo_fleet.py`, `test_argo_gitops.py`, `test_argo_crd.py`, and `test_k8s.py`.

## Feasibility

The premise was verified against upstream documentation and codebase source:
- Argo CD REST API `ApplicationSyncRequest` schema declares top-level `prune` (`boolean`), `strategy.apply.force` (`SyncStrategyApply`), and `appNamespace` (`string`). It has no top-level `sync` property.
- `src/devops_cli/commands/argo.py:268`, `src/devops_cli/argo/fleet.py:57`, and `src/devops_cli/argo/gitops.py:310` send `{"sync": {"prune": prune, "force": force}}`, which Argo CD drops.
- Kubernetes Custom Resource Definitions with a `/status` subresource ignore status fields sent to the main resource endpoint. `src/devops_cli/argo/crd.py:273,281` call `patch_namespaced_custom_object` rather than `patch_namespaced_custom_object_status`.
- `kubectl argo rollouts promote` clears `spec.paused` when paused manually and updates the status subresource.
- `src/devops_cli/commands/k8s/stack_lifecycle.py:615` executed `kubectl -n argocd get application cluster` with `check=False` and returned `False` on any non-zero exit code.

## Existing Tool Considered

Argo CD HTTP API and Kubernetes CustomObjectsApi are the upstream systems. Building custom body structures or shell-based kubectl checks causes dropped options and fail-open behavior. Replaced internal code includes manual `{"sync": ...}` payload constructions and subprocess `kubectl` queries.
