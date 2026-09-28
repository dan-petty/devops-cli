# Task 668: GPU Placement, Exporter Privileges and Gateway Routing for the LLM Pool

**Issue**: [#668](https://github.com/dan-petty/devops-cli/issues/668)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

Remediate Kubernetes LLM pool GPU placement, exporter privileges, and gateway routing anomalies discovered during `release/v0.2.23` stabilization:
1. Accept either `nvidia.com/gpu.family` or `nvidia.com/gpu.architecture` in Ollama node affinity to prevent pods remaining stuck in `Pending`.
2. Pin Ollama pods to dedicated GPUs, separate model directories, and apply memory limits to prevent shared VRAM contention and CPU fallback.
3. Remove conflicting `vllm-48gib` profile scaling by setting replicas to 0 and add `enableServiceLinks: false`.
4. Clear `capabilities.add` in `dcgm-exporter` Helm values and pass explicit `dcp-metrics-included.csv` arguments to eliminate superfluous container privileges.
5. In Kubernetes LLM Gateway, remove fixed `max_parallel_requests` caps on `devops-review` model group and adopt `simple-shuffle` routing strategy so tuned capacity weights take effect.

### Key Deliverables Completed:
- [x] **Kubernetes GPU Placement & Affinity**:
  - Updated node affinity selectors to match either `nvidia.com/gpu.family` or `nvidia.com/gpu.architecture`.
  - Scaled conflicting vLLM profiles to 0 replicas with disabled service links.
- [x] **DCGM Exporter Security Hardening**:
  - Cleared `capabilities.add` in `k8s/monitoring/dcgm-exporter-values.yaml` and scoped metrics arguments to drop profiling fields.
- [x] **LLM Gateway Weighted Routing**:
  - Removed parallel request caps and configured `simple-shuffle` routing on `devops-review` model group in `k8s/llm/gateway/configmap.yaml`.
- [x] **Automated Tests & Quality Gates**:
  - Verified gateway configuration and profile manifests in `tests/test_k8s_llm_gateway.py`.
  - 100% passing status across Gated CI quality gates (`uv run devops ci`).
