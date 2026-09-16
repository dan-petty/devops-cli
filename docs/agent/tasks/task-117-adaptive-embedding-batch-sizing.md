# Task 117: Adaptive Embedding Batch Sizing Circuit Breaker and Timeout Fallback

**Issue**: [#117](https://github.com/dan-petty/devops-cli/issues/117)
**PR**: [#223](https://github.com/dan-petty/devops-cli/pull/223)
**Status**: In Review
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/ai`

---

## 1. Description & Objectives

Distributed OpenTelemetry traces indicate `ai.rag.ollama_embed_batch` repeatedly encounters 15.0s `ReadTimeout: timed out` exceptions (75s+ total latency) during dense repository indexing, stalling RAG operations on overloaded local Ollama nodes.

#### Key Deliverables:
1. **Dynamic Batch Partitioning & Circuit Breaker ([`src/devops_cli/ai/rag/embeddings.py`](file:///workspaces/devops-cli/src/devops_cli/ai/rag/embeddings.py))**:
   - Introduce dynamic batch partitioning that adapts batch size dynamically (halving from 32 down to 16, 8, 4, 2, 1 on latency degradation or timeout).
   - If a batch fails or times out across candidate nodes, split into smaller sub-batches and retry.
   - Fall back to single-chunk requests when larger batches fail.
2. **Exponential Backoff with Jitter on Transient Timeouts**:
   - Implement bounded exponential backoff with jitter on `httpx2.TimeoutException` / `ReadTimeout` / `ConnectTimeout` to alleviate node pressure.
3. **Pre-Flight Valkey SHA-256 Chunk Cache Checks**:
   - Check Valkey L2 cache before dispatching embeddings remotely.
   - Cache freshly computed vectors to Valkey L2 with configured TTL.
   - Graceful fallback when Valkey is offline or unconfigured.
4. **Submodule Unit Tests ([`tests/test_rag_embeddings.py`](file:///workspaces/devops-cli/tests/test_rag_embeddings.py))**:
   - Unit tests for dynamic batch size halving on timeouts/latency.
   - Unit tests for sub-batch splitting and single-chunk fallback.
   - Unit tests for Valkey L2 pre-flight cache hit and store.
   - Unit tests for exponential backoff retry.
5. **Quality & Architectural Invariant Gates**:
   - Enforce cyclomatic complexity $\le 10$ and nesting depth $\le 5$ across all functions.
   - 100% passing across all 10 CI quality gates (`uv run devops ci`).
