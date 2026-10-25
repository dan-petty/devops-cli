# Design

## Context

`src/devops_cli/commands/argo.py`, `src/devops_cli/argo/fleet.py`, and `src/devops_cli/argo/gitops.py` interface with Argo CD REST API for sync operations. `src/devops_cli/argo/crd.py` and `rollouts.py` handle Rollout CRD manipulations via in-process Kubernetes API calls. `src/devops_cli/commands/k8s/stack_lifecycle.py` guards stack teardown against modifying Argo CD-managed infrastructure. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Provide a single reusable request-body builder for all Argo CD application sync callers.
- Ensure all sync options (`prune`, `force`, `appNamespace`) reach the upstream Argo CD server in accordance with `ApplicationSyncRequest` schema.
- Direct Rollout `promote` and `abort` control-plane mutations to the `/status` subresource.
- Clear `spec.paused` during rollout promotion when set.
- Ensure rollout mutation errors propagate to `_mutate_rollout` and trigger `abort_failed` gate actions.
- Use `ArgoCRDService` to inspect the `cluster` Application custom resource during teardown, failing closed on non-404 API errors.

**Non-Goals:**
- Refactoring workflow or analysis run CRD operations.
- Modifying rollout restart behavior, which correctly targets `spec.restartAt`.

## Decisions

### 1. Centralized sync payload construction
Create `src/devops_cli/argo/sync.py` exposing `build_sync_request_body(*, prune: bool = False, force: bool = False, app_namespace: str | None = None) -> dict[str, Any]`.
- *Rationale*: Guarantees consistent schema compliance for `devops argo cd apps sync`, multi-cluster fleet sync, and gitops drift triggers.
- *Rejected Alternative*: Update inline dictionary literals in all three callers. *Evidence*: Inline dict literals drifted and duplicated the dropped options bug across three separate modules (#1433).

### 2. Status subresource patching for Rollout control plane
Add `patch_resource_status` method to `ArgoCRDService` delegating to `CustomObjectsApi.patch_namespaced_custom_object_status`.
- *Rationale*: Custom Resource Definitions with subresources ignore `.status` modifications submitted via the main endpoint.
- *Rejected Alternative*: Retain `patch_resource` and send `status` in the body. *Evidence*: Kubernetes apiserver strips `.status` on the main endpoint when status subresource is active.

### 3. Conditional clearing of `spec.paused` during rollout promotion
In `ArgoCRDService.promote_rollout`, read the rollout manifest. If `(rollout.get("spec") or {}).get("paused")` is true, patch `spec.paused = False` via `patch_resource` before patching the status subresource.
- *Rationale*: Matches `kubectl argo rollouts promote` behavior where manual pauses stored in `spec.paused` must be cleared alongside canary pause conditions in `status`.
- *Rejected Alternative*: Unconditionally patch `spec.paused: False` on every promotion. *Evidence*: Emits unnecessary patch requests on canary-paused rollouts that never touched `spec.paused`.

### 4. Fail-closed Argo CD management verification in stack lifecycle
Replace subprocess `kubectl -n argocd get application cluster` with `ArgoCRDService.get_resource(CONST_ARGO_PLURAL_APPLICATIONS, "cluster", namespace="argocd")`. Return `False` only on `ArgoResourceNotFoundError` (HTTP 404). Any other `ArgoError` stops teardown and prints the failure reason.
- *Rationale*: Eliminates fragile shell parsing and ensures unauthorized access, rate limits, or apiserver outages fail closed rather than destroying GitOps-managed resources.
- *Rejected Alternative*: Retain subprocess invocation and check for specific stderr text. *Evidence*: Subprocess return codes collapse network errors, RBAC denials, and missing objects into generic exit codes.

## Risks / Trade-offs

- [Risk] Temporary Kubernetes apiserver unreachability prevents stack teardown. → Mitigation: Failing closed prevents catastrophic destruction of resources managed by GitOps. The error message clearly states why teardown was refused.
