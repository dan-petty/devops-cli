# Task 142: High-Throughput LLM Gateway & Distributed Model Router

**Issue**: [#142](https://github.com/dan-petty/devops-cli/issues/142)
**PR**: TBD
**Status**: Ready
**Milestone**: `v0.2.18`
**Priority**: `priority/p0-critical`
**Scope**: `scope/ai`

---

## 1. Description & Architectural Objectives

Design, deploy, and integrate a centralized, high-performance OpenAI-compatible routing proxy (LiteLLM Proxy / AI Gateway) and distributed inference mesh fronting heterogeneous Ollama nodes and dedicated vLLM server instances.

### Core Capabilities & Components
1. **Unified LLM Gateway (`k8s/llm/gateway/`, `devops ai gateway`)**:
   - In-cluster proxy in `llm` namespace exposing `http://llm-gateway.llm.svc.cluster.local:4000/v1`.
   - Least-latency, least-busy routing with health-driven failover and dynamic circuit breaking.
   - Virtual model aliases (`devops-chat`, `devops-coder`, `devops-reasoning`, `devops-embedding`).
   - Valkey distributed rate limiting and Squid egress proxying for outbound model pulls.
2. **vLLM Continuous Batching & Tensor-Parallel Serving (`k8s/llm/vllm/`)**:
   - Multi-GPU Tensor Parallelism ($TP=2$) on `condor` dual RTX 3090 (48GB VRAM) for 70B models (`llama-3.3-70b-instruct`, `qwen2.5-coder-32b`).
   - PagedAttention and continuous batching for 5-10x throughput over Ollama during multi-file reviews.
3. **Context-Window & VRAM-Aware Dynamic Router (`devops_cli.ai.router.gateway`)**:
   - Prompt context token inspection: $\le 16\text{k}$ to fast single-GPU nodes, $\ge 32\text{k}-64\text{k}$ to multi-GPU vLLM.
4. **FastMCP Gateway Tools & Telemetry**:
   - FastMCP tools (`ai_gateway_status`, `ai_gateway_routes`, `ai_gateway_failover`, `ai_vllm_scale`) and GPU resource.
   - OpenTelemetry W3C trace propagation and Prometheus metrics.

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#142) under milestone `v0.2.18`.
- [x] Integrate roadmap specification into `docs/ROADMAP.md`.
- [ ] Author Kubernetes / Helm manifests for LiteLLM Gateway (`k8s/llm/gateway/`).
- [ ] Author Kubernetes manifests for vLLM Tensor Parallelism on `condor` (`k8s/llm/vllm/`).
- [ ] Implement client routing integration and fallback in `src/devops_cli/ai/client/`.
- [ ] Author FastMCP tools and cluster GPU resource in `src/devops_cli/mcp/`.
- [ ] Add unit and integration tests with $\ge 90\%$ code coverage.
- [ ] Run full CI quality gate suite (`devops ci`).
