# Task 430: Capability-Gated Model Failover & AIMD Batch Recovery

**Issue**: [#430](https://github.com/dan-petty/devops-cli/issues/430)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/ai`, `priority/p0-critical`

---

## 1. Description & Objectives

Replaces capability cliff degradations with strict minimum model tier requirements (reasoning $\ge 30\text{B}$, coding $\ge 7\text{B}$). Implements Additive Increase / Multiplicative Decrease (AIMD) for embedding batch sizing to prevent permanent throughput collapse on transient latency spikes.

#### Key Deliverables:
- [x] **Capability Tier Module (`src/devops_cli/ai/capability.py`)**:
  - `ModelCapabilityTier`: classifications (`reasoning`, `coding`, `chat`, `embedding`).
  - `get_minimum_tier_b`: parameter floor mapping (reasoning $\ge 30\text{B}$, coding $\ge 7\text{B}$).
  - `evaluate_model_capability`: parameter extraction with decimal support (`1.5b` $\to 1$) and designated frontier equivalent (70B) for OpenAI, Anthropic, Gemini, Google.
  - `validate_failover_capability`: raises `CapabilityDegradationError` (`CAPABILITY_DEGRADATION`) on underpowered fallbacks unless bypassed via `--force`.
- [x] **Gateway & Constellation Controller Integration**:
  - `GatewayRouter.trigger_failover`: validates fallback routes against required capability tier, exposing `--force` in CLI and `ai_gateway_failover` FastMCP tool.
  - `AgentConstellationManager.failover`: validates active tasks before state transitions, exposing `--force` in CLI and `ai_failover` FastMCP tool.
- [x] **AIMD Embedding Batch Sizing (`EmbeddingsEngine`)**:
  - Multiplicative decrease factor $\times 0.5$ on latency spikes or timeouts, floored at `DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE`.
  - Additive increase step $+2$ after every 2 consecutive low-latency batches (`DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS`), capped at `_configured_batch_size`.
  - Telemetry: metrics `rag.embedding.batch_size` and `rag.embedding.aimd_action`.
- [x] **Comprehensive Test Verification**:
  - `tests/test_ai_capability.py`: tests parameter extraction, frontier mapping, tier predicates, and rejection/override.
  - `tests/test_rag_aimd.py`: tests AIMD multiplicative decrease, additive increase recovery, ceiling caps, and counter resets.
  - `tests/test_ai_controller.py`: tests constellation failover capability gating with `--force`.
  - `tests/test_ai_gateway.py`: tests gateway failover capability gating with `--force`.
  - All tests enforce McCabe complexity $M \le 10$, nesting depth $\le 5$, and structural tuple equality assertions.
