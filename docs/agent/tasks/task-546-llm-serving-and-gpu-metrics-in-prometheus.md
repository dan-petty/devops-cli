# Task 546: LLM Serving and GPU Metrics in Prometheus

**Issue**: [#546](https://github.com/dan-petty/devops-cli/issues/546)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

Prometheus scrapes no `vllm:*`, `litellm_*` or GPU metric, so each backend's load, queue and latency cannot be seen or kept; #545's imbalance was found by exec-ing `nvidia-smi` in each pod. The shipped `llm-stack.json` dashboard queries generic `http_requests_total` names nothing exposes, so it is empty.

#### Key Deliverables:
- Context & Rationale*: Prometheus scrapes no `vllm:*`, `litellm_*` or GPU metric, so each backend's load, queue and latency cannot be seen or kept; #545's imbalance was found by exec-ing `nvidia-smi` in each pod. The shipped `llm-stack.json` dashboard queries generic `http_requests_total` names nothing exposes, so it is empty.
- Deliverable*: ServiceMonitors for both vLLM servers' `/metrics`; the gateway's open-source Prometheus callback (per-deployment requests, failures, latency, in-flight calls, covering the Ollama nodes); NVIDIA's DCGM exporter on the GPU nodes (Maxwell and newer GeForce and Quadro, Kepler and newer datacenter GPUs; some features unavailable on non-datacenter GPUs); `llm-stack.json` rebuilt on these metrics; a command reporting the pool's busy share and queue over a window (from #557).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
