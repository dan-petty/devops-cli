# Proposal: #6684

## Why
Self-hosted Renovate in `k8s/devops/renovate/` serves each repository of the owner. Per ADR 0032, it is not a devops-cli product template. Only homelab runs it, so it becomes a homelab instance with no infra template (dan-petty/homelab#95). Moving it out of the product removes cluster-specific workload manifests and gate checks from the product code.

## What Changes
- Remove `k8s/devops/renovate/` and its kustomization entry in `k8s/devops/kustomization.yaml`.
- Remove the 4 renovate manifest paths from `PRODUCT_MANIFESTS_BY_STACK["devops"]` in `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Delete `src/devops_cli/k8s/renovate_token.py` and `tests/k8s/test_renovate_token.py`.
- Delete gate check `tests/gate/k8s_checks/renovate.py` and helper `tests/support/renovate.py`.
- Move cluster secret row test from `tests/invariants/test_k8s_renovate.py` to `tests/k8s/test_cluster_secrets.py` and remove `tests/invariants/test_k8s_renovate.py`.
- Update `tests/gate/k8s_checks/devops_runtime.py` and `tests/gate/k8s_checks/telemetry_resource.py`.
- Update `docs/CLUSTER.md` and `docs/TESTING.md`.
- Remove Trivy KSV-0109 ignore entry from `.trivyignore.yaml`.
- Post comments on open issues naming `dan-petty/homelab#95`.

## Capabilities
- Eliminates the self-hosted Renovate workload from the devops-cli product base.
- Preserves the `devops/renovate` Secret row and `renovate.*` settings for the init container.

## Impact
- Product manifests no longer contain the Renovate CronJob, ConfigMap, PVC, and NetworkPolicy.
- dan-petty/homelab#95 adopts the workload and live PVC cache claim.

## Feasibility
Confirmed against repository code and tests: manifests, checks, and invariant tests match the removal plan.

## Existing Tool Considered
The alternatives check in the issue body records not-applicable for a refactor with no search and Tool: none found. The change removes code and manifests; it builds no new tool.
