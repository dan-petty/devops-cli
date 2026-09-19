# Task 320: Pydantic AI Structured Workflows, Prompt Caching & Client-Side Token Governance Research

**Issue**: [#320](https://github.com/dan-petty/devops-cli/issues/320)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/ai`, `priority/p0-critical`

---

## 1. Description & Objectives

AI inference routing and agent execution rely on bespoke HTTP callers, manual function call parsers, and custom retry loops that are prone to schema divergence and latency spikes.

#### Key Deliverables:
- Context & Rationale*: AI inference routing and agent execution rely on bespoke HTTP callers, manual function call parsers, and custom retry loops that are prone to schema divergence and latency spikes.
- Deep Integration & Functional Extension*: Native PydanticAI Agent workflows with dependency injection and typed tool definitions; prompt caching optimizations for Anthropic/OpenAI; client-side token-bucket rate governance; dynamic fallback cascades across LiteLLM, Portkey, LightLLM, and Ollama.
- Code Optimization & Performance Acceleration*: Reduce prompt token billing and processing latency by up to 80% through prompt caching; eliminate JSON schema parsing failures via Pydantic v2 runtime validation; optimize streaming time-to-first-token.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/ai/agent.py`, `controller.py`, and `gateway.py` to eliminate custom function calling parsers and fragile manual retry loops; adopt standardized PydanticAI streaming agents with typed tool registries.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
