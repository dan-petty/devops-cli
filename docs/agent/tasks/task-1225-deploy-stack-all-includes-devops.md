# Task: Add DevOps Stack to Deploy-Stack and Include in Stack All (#1225)

**Issue**: [#1225](https://github.com/dan-petty/devops-cli/issues/1225)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Integrate the in-cluster `devops` namespace resources into `devops k8s deploy-stack` as a first-class stack alongside `infra`, `llm`, and `logging`, and include it in `devops k8s deploy-stack --stack all`.

Previously, `k8s/devops/` was treated as an unmanaged/detached directory outside of `deploy-stack`. When deploying cluster updates via `devops k8s deploy-stack --stack all`, `devops-cli-config` ConfigMap and `roadmap-service` workloads were skipped, leading to configuration drift between the repo configuration and the cluster runtime unless manually applied with ad-hoc `devops k8s apply` invocations.

This deliverable:
1. **Registers `devops` stack**: Adds `"devops"` to `VALID_STACKS` and includes it in `_resolve_stacks("all")` in `src/devops_cli/commands/k8s/networking.py` and `src/devops_cli/commands/k8s/stack_lifecycle.py`.
2. **Defines Stack Manifests**: Maps `_MANIFESTS_BY_STACK["devops"]` to all 9 manifests in `k8s/devops/` (`networkpolicy.yaml`, `serviceaccount.yaml`, `configmap.yaml`, `cronjob.yaml`, and the `roadmap-service` resources).
3. **Automated Secret Pushing & Workload Restart**: Updates `_push_stacks_for()` to push `devops` secrets alongside other stacks, and executes `kubectl rollout restart deploy/roadmap-service -n devops` upon deployment so running instances immediately reload updated configurations.
4. **Namespace Pre-Registration**: Adds namespace `devops` to `k8s/namespaces.yaml` with standard pod-security `restricted` labels and ArgoCD Prune=false annotations, ensuring the namespace exists prior to secret pushing during pre-flight bootstrap.
5. **Agent Architectural Invariant**: Updates `AGENTS.md` with the mandatory rule that all in-cluster Kubernetes manifests and services MUST have a managed stack path in `deploy-stack` and be included in `--stack all`.

## Acceptance Criteria
- [x] Add `"devops"` to `VALID_STACKS` across `networking.py` and `stack_lifecycle.py`.
- [x] Include `"devops"` in `_resolve_stacks("all")` so `devops k8s deploy-stack --stack all` deploys and reconciles all `devops` resources.
- [x] Pre-register namespace `devops` in `k8s/namespaces.yaml` with `restricted` pod-security standards.
- [x] Map all 9 manifests in `k8s/devops/` in `_MANIFESTS_BY_STACK["devops"]`.
- [x] Push `devops` secrets and restart `deploy/roadmap-service` during stack deployment.
- [x] Update `AGENTS.md` with the mandatory rule: *Mandatory Comprehensive Kubernetes Stack Deployment (`devops k8s deploy-stack --stack all`)*.
- [x] Add comprehensive unit and regression tests in `tests/test_k8s_devops_stack.py` and `tests/test_k8s.py`.
- [x] Pass pre-push Gated CI validation suite with 100% green status.
- Pending a person: review and merge PR on GitHub.

## Measurements
- New test suite in `tests/test_k8s_devops_stack.py`: 4 passed in ~21s.
- `tests/test_k8s.py`: 47 passed.
- All architectural invariants in `tests/test_architectural_invariants.py`: 77 passed.
