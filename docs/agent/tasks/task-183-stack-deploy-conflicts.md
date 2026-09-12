# Task 183: Resolve Helm Stack Deploy SSA Conflicts, Loki Validation, and PodSecurity Failures

**Issue**: [#183](https://github.com/dan-petty/devops-cli/issues/183)
**PR**: [#182](https://github.com/dan-petty/devops-cli/pull/182)
**Status**: In Review
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Architectural Objectives

Resolve the 5 deployment errors encountered during `devops k8s deploy-stack --stack all`:
1. **ArgoCD, Kube-Prometheus, and Qdrant SSA Field Conflicts**:
   - Helm v4 Server-Side Apply fails when resources were previously touched by `kubectl-set` or `kubectl-patch`.
   - Remediate by passing `--force-conflicts` in `helm upgrade --install` invocations in `stack_lifecycle.py`.
2. **Loki Chart Template Validation Failure**:
   - Chart `grafana/loki` requires `read.replicas: 0`, `write.replicas: 0`, and `backend.replicas: 0` when `deploymentMode: SingleBinary` is configured.
3. **Fluent-Bit DaemonSet Admission Block**:
   - Namespace `logging` was set to `pod-security.kubernetes.io/enforce: baseline`, which rejects hostPath volumes required by Fluent-Bit to tail `/var/log`.
   - Update namespace `logging` to `privileged` standard (consistent with `monitoring` and `llm`).
4. **Fluent-Bit Invalid Output Plugin**:
   - Fluent-Bit v5 deprecated and removed `grafana-loki` in favor of core `Name loki`.
   - Update `fluent-bit-values.yaml` to use `Name loki`.
5. **Qdrant InitContainer Ownership Error**:
   - The default `ensure-dir-ownership` container attempts `chown` as unprivileged user 1000.
   - Disable via `updateVolumeFsOwnership: false` since `podSecurityContext.fsGroup: 1000` already ensures proper group ownership.

---

## 2. Implementation Checklist

- [x] Ground issue [#183](https://github.com/dan-petty/devops-cli/issues/183) in GitHub tracking and sync project view
- [x] Author dedicated task tracking file `docs/agent/tasks/task-183-stack-deploy-conflicts.md`
- [x] Update `src/devops_cli/commands/k8s/stack_lifecycle.py` to pass `--force-conflicts` on Helm upgrades
- [x] Update `k8s/namespaces.yaml` namespace `logging` PodSecurity standard to `privileged`
- [x] Update `k8s/logging/loki-values.yaml` with `read.replicas: 0`, `write.replicas: 0`, `backend.replicas: 0`
- [x] Update `k8s/logging/fluent-bit-values.yaml` to use output plugin `Name loki`
- [x] Update `k8s/llm/values-qdrant.yaml` to set `updateVolumeFsOwnership: false`
- [x] Add unit test in `tests/test_k8s.py` verifying `--force-conflicts` flag
- [x] Verify template rendering for Loki, Fluent-Bit, and Qdrant
- [x] Verify local quality gates via `uv run pytest` and `devops ci`
- [x] Verify live deployment via `devops k8s deploy-stack --stack all`
