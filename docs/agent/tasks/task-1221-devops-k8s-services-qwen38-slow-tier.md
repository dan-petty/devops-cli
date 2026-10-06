# Task: Devops K8s Services Use qwen3.8:27b on ollama-48gib-slow (#1221)

**Issue**: [#1221](https://github.com/dan-petty/devops-cli/issues/1221)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Route `devops` namespace Kubernetes services (`roadmap-service` and batch/cronjob workloads) to `devops-background` on `ollama-48gib-slow` serving `qwen3.8:27b`. Previously, `k8s/devops/configmap.yaml` configured `ai.model: devops-chat`, `tasks.analysis.model: devops-review`, and `tasks.chat.model: devops-coder`, directing in-cluster service traffic to the fast and standard interactive inference tiers (`ollama-48gib-fast`, `ollama-64gib-standard`, and `ollama-16gib-fast`), competing with developer review workloads.

This deliverable:
1. **Updates Gateway Background Tier Routing**:
   - Updates `devops-background` in `k8s/llm/gateway/configmap.yaml` to point to `ollama_chat/qwen3.8:27b` on `http://ollama-48gib-slow.llm.svc.cluster.local:11434`.
   - Preserves `ollama-48gib-slow`'s strict concurrency and residency perimeter: exactly two loaded models (`bge-m3:latest` for embeddings and `qwen3.8:27b` for background generation).
2. **Configures Devops Services ConfigMap**:
   - Updates `k8s/devops/configmap.yaml` (`devops-cli-config`) to set `model: devops-background`, `tasks.analysis.model: devops-background`, and `tasks.chat.model: devops-background`.
3. **Synchronizes Workload Profiles and Knowledge Base**:
   - Updates comments in `k8s/llm/profiles/ollama-profiles.yaml` and `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md` to reference `qwen3.8:27b`.
   - Updates `src/devops_cli/k8s/gpu_matrix.py` `get_gateway_routing_entries()` to mirror the gateway `devops-background` model.
   - Updates `k8s/README.md` gateway architecture documentation.
4. **Updates Gateway and Runtime Tests**:
   - Updates `tests/test_k8s_llm_gateway.py` slow-tier assertion to expect `("ollama_chat/qwen3.8:27b", slow, None)`.
   - Updates `tests/test_k8s_devops_runtime.py` to assert that `devops-cli.yaml` configures `devops-background` across default, analysis, and chat tasks.

## Acceptance Criteria
- [x] `k8s/llm/gateway/configmap.yaml` routes `devops-background` to `ollama_chat/qwen3.8:27b` on `http://ollama-48gib-slow.llm.svc.cluster.local:11434`.
- [x] `k8s/devops/configmap.yaml` sets `model`, `tasks.analysis.model`, and `tasks.chat.model` to `devops-background`.
- [x] `k8s/llm/profiles/ollama-profiles.yaml` notes `qwen3.8:27b` and `bge-m3:latest` stay loaded together on `ollama-48gib-slow`.
- [x] `src/devops_cli/k8s/gpu_matrix.py` mirrors the updated gateway routing entry.
- [x] `k8s/README.md` and knowledge base document `qwen3.8:27b` on `ollama-48gib-slow`.
- [x] `tests/test_k8s_llm_gateway.py` and `tests/test_k8s_devops_runtime.py` pass.
- [x] `changelog.d/1221.md` is present.
- [x] `uv run devops ci` passes with 100% green status across all quality gates.
- Pending a person: `kubectl apply -f k8s/llm/gateway/configmap.yaml && kubectl apply -f k8s/devops/configmap.yaml && kubectl -n llm rollout restart deploy/llm-gateway && kubectl -n devops rollout restart deploy/roadmap-service`

## Deliverables
- [x] `k8s/llm/gateway/configmap.yaml`
- [x] `k8s/devops/configmap.yaml`
- [x] `k8s/llm/profiles/ollama-profiles.yaml`
- [x] `k8s/README.md`
- [x] `src/devops_cli/k8s/gpu_matrix.py`
- [x] `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`
- [x] `tests/test_k8s_llm_gateway.py`
- [x] `tests/test_k8s_devops_runtime.py`
- [x] `changelog.d/1221.md`
- [x] `docs/agent/tasks/task-1221-devops-k8s-services-qwen38-slow-tier.md`
