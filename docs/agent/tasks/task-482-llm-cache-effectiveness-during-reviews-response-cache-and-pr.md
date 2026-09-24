# Task 482: LLM Cache Effectiveness During Reviews Response Cache and Prefix Cache

**Issue**: [#482](https://github.com/dan-petty/devops-cli/issues/482)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

Two caches can save review work: devops-cli's LLM response cache (`devops ai cache status`) and vLLM's automatic prefix cache, which can skip reprocessing a persona's static system prompt on every page. Neither is measured during reviews. The tuner showed how much prefix reuse matters: identical prompts made vLLM's prompt processing nearly free.

#### Key Deliverables:
- Context & Rationale*: Two caches can save review work: devops-cli's LLM response cache (`devops ai cache status`) and vLLM's automatic prefix cache, which can skip reprocessing a persona's static system prompt on every page. Neither is measured during reviews. The tuner showed how much prefix reuse matters: identical prompts made vLLM's prompt processing nearly free.
- Deliverable*: Report response-cache hit rates per review run, and vLLM prefix-cache hit rates (`vllm:prefix_cache_hits` over `vllm:prefix_cache_queries`) per backend. Check that persona prompts keep static text ahead of page content so the prefix is shared, and fix any ordering that defeats it.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
