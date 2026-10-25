# Tasks

## 1. Argo CD sync request payload construction

- [x] 1.1 Add failing unit tests verifying that application sync, fleet sync, and gitops sync send top-level prune and strategy.apply.force without a sync key (`uv run devops ci test tests/test_argo.py tests/test_argo_fleet.py tests/test_argo_gitops.py`).
- [x] 1.2 Implement `build_sync_request_body` in `src/devops_cli/argo/sync.py` and update `commands/argo.py`, `argo/fleet.py`, and `argo/gitops.py` to use it (`uv run devops ci test tests/test_argo.py tests/test_argo_fleet.py tests/test_argo_gitops.py`).
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 2. Rollout status subresource patching and failure handling

- [x] 2.1 Add failing unit tests asserting that promote and abort patch the status subresource, that promote clears spec.paused when set, and that refused mutations return failure and report abort_failed in rollout gates (`uv run devops ci test tests/test_argo_crd.py tests/test_argo_fleet.py`).
- [x] 2.2 Add `patch_resource_status` to `ArgoCRDService`, update `promote_rollout` and `abort_rollout` to target the status subresource, clear `spec.paused` when set, and ensure refused mutations propagate to `_mutate_rollout` (`uv run devops ci test tests/test_argo_crd.py tests/test_argo_fleet.py`).
- [x] 2.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 3. Fail-closed Argo CD management checks in stack lifecycle

- [x] 3.1 Add failing unit tests asserting that `_is_cluster_argo_managed` uses `ArgoCRDService`, returns False on 404, and that 403, 500, or timeout stops teardown with an error message displaying the reason (`uv run devops ci test tests/test_k8s.py`).
- [x] 3.2 Update `_is_cluster_argo_managed` to inspect the `cluster` Application via `ArgoCRDService` and update `teardown_stack` in `stack_lifecycle.py` to refuse teardown on non-404 API errors (`uv run devops ci test tests/test_k8s.py`).
- [x] 3.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
