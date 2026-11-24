# Tasks

## 1. CloudNativePG cluster discovery and patch helpers in nodes
Kind: behavior. Reads: `src/devops_cli/infra/nodes.py`, `tests/support/infra.py`, `tests/infra/test_nodes.py`. Changes: `src/devops_cli/infra/nodes.py`, `tests/support/infra.py`, `tests/infra/test_nodes.py`.
Adds: `CNPG_CLUSTERS_ARGS`, `cnpg_patch_args`, `cnpg_clusters`, `cnpg_window_clusters`, `patch_cnpg_window`, `wait_cnpg_healthy`, `check_cnpg_guards`.

- [x] 1.1 Write failing test `test_cnpg_window_clusters_and_guards` in `tests/infra/test_nodes.py`: single-instance clusters on the node are identified; 2-instance clusters are ignored; Argo CD selfHeal without ignoreDifferences returns a refusal; git field presence returns a refusal.
  - Verification: `$ uv run devops ci test tests/infra/test_nodes.py`
- [x] 1.2 Implement CloudNativePG discovery, guard checks, patch methods, and health wait on `Cluster` in `src/devops_cli/infra/nodes.py`. Update `FakeCluster` in `tests/support/infra.py` to support `clusters.postgresql.cnpg.io` get/patch and application checks.
  - Verification: `$ uv run devops ci test tests/infra/test_nodes.py`

## 2. Maintenance window lifecycle in infra apply
Kind: behavior. Reads: `src/devops_cli/infra/apply.py`, `tests/commands/test_infra_apply.py`. Changes: `src/devops_cli/infra/apply.py`, `src/devops_cli/models/infra.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/errors.py`, `tests/commands/test_infra_apply.py`.

- [x] 2.1 Write failing integration tests in `tests/commands/test_infra_apply.py` covering: single-instance cluster gets window before drain check and closes after uncordon; 2-instance cluster gets no window; agent access below full gets no window; unhealthy cluster stops host; Argo CD guard refusal refuses host; audit record names clusters.
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`
- [x] 2.2 Wire CNPG maintenance window into `_drain` and `_settle` in `src/devops_cli/infra/apply.py`. Add message/error strings and audit details.
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`

## 3. Dry-run support for maintenance window
Kind: behavior. Reads: `src/devops_cli/infra/infra_plans.py`, `tests/commands/test_infra_apply.py`. Changes: `src/devops_cli/infra/infra_plans.py`, `tests/commands/test_infra_apply.py`, `tests/commands/__snapshots__/test_infra_apply.ambr`.

- [x] 3.1 Write test in `tests/commands/test_infra_apply.py` asserting dry-run lists CNPG reads and patches without starting processes.
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`
- [x] 3.2 Update `_host_steps` in `src/devops_cli/infra/infra_plans.py` to include PlannedRequests for CNPG discovery and patches. Update snapshot.
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py`

## 4. Documentation
Kind: docs. Reads: `CONTEXT.md`, `SECURITY.md`, `src/devops_cli/infra/apply.py`. Changes: `CONTEXT.md`, `SECURITY.md`, `src/devops_cli/infra/apply.py`.

- [x] 4.1 Update `CONTEXT.md`, `SECURITY.md`, and docstrings in `src/devops_cli/infra/apply.py` to describe CloudNativePG maintenance windows.
  - Verification: `$ uv run devops ci docs`

## Criteria
- Group 1: Node tests verify CNPG discovery, guard checks, patch execution, and health polling.
- Group 2: Apply tests verify window opening before drain check, window closing after uncordon, stopping on unhealthy clusters, and refusal when Argo CD would revert.
- Group 3: Dry-run test verifies that CNPG reads and patches are listed and no process starts.
- Group 4: Documentation updated and docs gate passes.
