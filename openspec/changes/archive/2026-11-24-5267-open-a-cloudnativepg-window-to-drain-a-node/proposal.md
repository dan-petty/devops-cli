# Proposal: #5267

## Why
`devops infra apply` (#5125) drains each disruptive host with no `--force`, so a PodDisruptionBudget applies. A CloudNativePG cluster with 1 instance has a primary PodDisruptionBudget that allows 0 disruptions. On homelab, the control-plane node runs two such clusters (`llm-gateway-db` in `llm`, `mattermost-db` in `mattermost`). The drain check (`kubectl drain --dry-run=server`) of that node stops the apply with `error when evicting pods/"llm-gateway-db-1" -n "llm": global timeout reached`. To drain the node safely, the apply must open a maintenance window on each single-instance CloudNativePG cluster whose primary runs on that node before the drain check, and close the window after the uncordon.

## What Changes
- Before the drain check of a disruptive host, `devops infra apply` queries the CloudNativePG clusters (`kubectl get clusters.postgresql.cnpg.io -A -o json`).
- For each cluster with 1 instance whose primary pod runs on the node, when agent access is `full` and the plan is disruptive on that node, the apply opens a maintenance window: `spec.nodeMaintenanceWindow: {inProgress: true, reusePVC: true}` via `kubectl patch`.
- Clusters with 2 or more instances get no maintenance window.
- When repo agent access is below `full`, no window is opened.
- Before opening a maintenance window, the apply reads the tracking Application of each cluster (`argocd.argoproj.io/tracking-id`). When the field `nodeMaintenanceWindow` is present in git in the cluster manifest, or when the Application has `selfHeal: true` and lacks an `ignoreDifferences` entry for `/spec/nodeMaintenanceWindow`, the apply refuses the host and names the remediation step.
- The apply names the windowed clusters in the report and the audit record of the host as down during the window.
- After the uncordon, the apply closes each window (`inProgress: false`) and waits until each cluster reports `Cluster in healthy state` with its primary Ready, bounded by `infra.node_ready_timeout_seconds`. A cluster that does not become healthy stops the host.
- `--dry-run` lists the reads and patches of the CloudNativePG maintenance window and starts no processes.

## Capabilities

### Modified Capabilities
- `infra-apply`: The CloudNativePG maintenance window of a disruptive host

## Impact
- Code: `src/devops_cli/infra/apply.py`, `src/devops_cli/infra/nodes.py`, `src/devops_cli/infra/infra_plans.py`, `src/devops_cli/models/infra.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/errors.py`.
- Tests: `tests/commands/test_infra_apply.py`, `tests/support/infra.py`, `tests/infra/test_nodes.py`.
- Documents: `CONTEXT.md`, `SECURITY.md`, `docs/CLI_REFERENCE.md`.

## Feasibility
- Probes confirmed CloudNativePG operator uses `spec.nodeMaintenanceWindow: {inProgress: bool, reusePVC: bool}` as the supported path to drain a node with single-instance clusters.
- `kubectl patch clusters.postgresql.cnpg.io <name> -n <namespace> --type=merge -p ...` patches the resource without extra dependencies.
- `argocd.argoproj.io/tracking-id` exists on managed resources and is already parsed by `devops-cli`.

## Existing Tool Considered
CloudNativePG `spec.nodeMaintenanceWindow` (the operator's documented path) and the `kubectl cnpg maintenance set --reusePVC` plugin. `devops-cli` calls `kubectl patch` directly so that no plugin binary is required. Bypassing budgets with `--disable-eviction` or editing PodDisruptionBudgets was rejected because it violates operator management and cluster safety. Cost to build: about 1.5M tokens, 3 hours.

## Dependencies
#5125.
