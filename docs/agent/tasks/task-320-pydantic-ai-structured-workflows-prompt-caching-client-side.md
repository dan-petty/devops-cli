# Task 320: Pydantic AI Structured Workflows, Prompt Caching & Client-Side Token Governance Research

**Issue**: [#320](https://github.com/dan-petty/devops-cli/issues/320)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/ai`, `priority/p0-critical`

---

## 1. Description & Objectives

AI inference routing and agent execution rely on bespoke HTTP callers, manual function call parsers, and custom retry loops that are prone to schema divergence and latency spikes.

#### Key Deliverables:
- [x] **Context & Rationale**: Addressed bespoke HTTP callers and manual retry loops in AI inference and agent workflows.
- [x] **Deep Integration & Functional Extension**:
  - Native PydanticAI Agent workflows with dependency injection and typed tool definitions via `DevOpsAgentContext` and `execute_structured_workflow` / `execute_structured_workflow_sync` in `src/devops_cli/ai/pydantic_ai_bridge.py`.
  - Prompt caching optimizations for Anthropic / OpenAI via `inject_prompt_cache_points` and `create_cached_user_prompt` using `pydantic_ai.CachePoint`.
  - Client-side token-bucket rate governance via `TokenBucketGovernance` and `TokenBudgetConfig` in `src/devops_cli/ai/governance.py` with automatic calculation of throttling delays and consumption tracking from `RunUsage`.
  - Dynamic fallback cascades across LiteLLM, Portkey, LightLLM, and Ollama via `build_fallback_cascade_model` constructing `pydantic_ai.models.fallback.FallbackModel`, integrated into `GatewayRouter.build_pydantic_cascade_model`.
- [x] **Code Optimization & Performance Acceleration**:
  - Prompt caching reduces prompt token processing latency and billing overhead.
  - Token-bucket rate governor mitigates rate limit failures and smooths bursty LLM traffic.
  - Dynamic fallback cascades guarantee uninterrupted execution across degraded or failing upstream inference endpoints.
- [x] **Refactoring Potential & Legacy Elimination**:
  - Defined `CONST_AI_PROMPT_CACHE_TTL_5M`, `CONST_AI_PROMPT_CACHE_TTL_1H`, `CONST_AI_PROMPT_CACHE_TTLS`, `CONST_AI_CASCADE_PROVIDERS`, `CONST_AI_DEFAULT_CACHE_MARKER_KIND`, `DEFAULT_AI_TOKEN_BUCKET_CAPACITY`, `DEFAULT_AI_TOKEN_BUCKET_REFILL_RATE`, `DEFAULT_AI_PROMPT_CACHE_TTL`, and `DEFAULT_AI_USAGE_REQUEST_LIMIT` in `src/devops_cli/config/constants.py` and `src/devops_cli/config/defaults.py`.
  - Exported `TokenBudgetConfig`, `TokenBucketGovernance`, `inject_prompt_cache_points`, `create_cached_user_prompt`, `build_fallback_cascade_model`, `execute_structured_workflow`, `execute_structured_workflow_sync` in `src/devops_cli/ai/__init__.py`.
- [x] **Testing & Verification**:
  - Authored 10 unit tests with structural tuple equality assertions in `tests/test_pydantic_ai_workflows.py`.
  - Verified prompt cache injection, token bucket consumption, budget configuration to `UsageLimits`, fallback cascade execution, structured workflow execution (sync and async), and gateway cascade builder.
  - Maintained cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Summary

- **Unit Tests**: 10/10 passed in `tests/test_pydantic_ai_workflows.py`; all 53 AI tests passed in test suite.
- **Architectural Invariants**: Complexity check passed ($M \le 10$, nesting depth $\le 5$).
- **Gated CI Quality Gates**: All 10 gates passed locally via `uv run devops ci`.
