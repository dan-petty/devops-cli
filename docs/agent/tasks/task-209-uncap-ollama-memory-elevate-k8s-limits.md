# Task 209: Uncap Ollama Memory Limits & Elevate K8s Resource Thresholds

**Issue**: [#209](https://github.com/dan-petty/devops-cli/issues/209)
**PR**: [#210](https://github.com/dan-petty/devops-cli/pull/210)
**Status**: In Review
**Milestone**: `v0.2.18`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Root Cause Analysis

### Background & Observations
During multi-node cluster operations, multiple services experienced OOM terminations, restart spikes, or probe timeouts:
- `llm/ollama`: Terminated with Exit Code 137 on 16GiB worker nodes where a blanket `26Gi` limit allowed the container to exceed host physical RAM (174% overcommit), while artificially capping 64GiB GPU worker nodes.
- `argocd/argocd-repo-server`: Experienced 5 restarts under burst manifest and Helm rendering against a tight 2Gi limit.
- `kube-system/coredns`: Experienced 6 restarts under cluster DNS bursts against a 170Mi limit.
- `logging/fluent-bit`: Experienced 3 restarts on the primary logging node against a 512Mi limit.

### Key Deliverables
1. **Ollama DaemonSet & Helm Values (`k8s/llm/ollama-daemonset.yaml`, `k8s/llm/values-ollama.yaml`)**:
   - Remove static `limits.memory: 26Gi` to permit node-adaptive unconstrained memory scaling across 16GiB to 64GiB nodes.
   - Retain guaranteed baseline requests (`cpu: 3000m`, `memory: 8Gi`).
2. **ArgoCD Repo-Server (`k8s/argocd/values.yaml`)**:
   - Elevate `repoServer` memory limit from 2048Mi to 4096Mi (4Gi) and CPU limit to 4000m.
3. **CoreDNS Manifests & Configuration (`k8s/coredns/values.yaml`, `k8s/coredns/deployment-patch.yaml`, `k8s/coredns/helmchartconfig.yaml`)**:
   - Elevate CoreDNS memory limit from 170Mi to 384Mi to eliminate OOM terminations during cluster DNS bursts.
4. **Fluent Bit (`k8s/logging/fluent-bit-values.yaml`)**:
   - Elevate `fluent-bit` memory limit from 512Mi to 1024Mi (1Gi).
5. **Test Suite Verification (`tests/test_k8s.py`)**:
   - Strict assertions validating unconstrained Ollama memory limits, exact 4096Mi ArgoCD repoServer limits, 1024Mi Fluent Bit limits, and 384Mi CoreDNS values/patch contracts.

---

## 2. Verification & Acceptance Criteria

- [x] All 42 tests in `tests/test_k8s.py` and `tests/test_architectural_invariants.py` pass cleanly.
- [x] Live cluster daemonset and deployments patched with updated resource limits.
- [x] All quality gates pass in `devops ci`.
