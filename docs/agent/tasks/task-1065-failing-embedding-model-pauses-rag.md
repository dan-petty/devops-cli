# Task: Failing Embedding Model Pauses RAG Lookups and Embedders Gain Model-Specific Configurations (#1065)

**Issue**: [#1065](https://github.com/dan-petty/devops-cli/issues/1065)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description

A transient embedding model failure (e.g. 5xx status, connection timeout, rate limit 429) previously stopped RAG lookups for the rest of the CLI run identically to an unserved or missing model. Furthermore, lookup requests while unserved queued sequentially under a lock rather than coordinating a probe, embedding cache keys did not differentiate between models and task prompts, `qwen3-embedding` dimension was not pinned to 1024, package manager lockfiles were unnecessarily parsed and indexed, oversized chunk line windows could exceed model context boundaries, and indexer batch failures raised unhandled errors without naming the batch files or preserving earlier batches for resume.

This deliverable resolves all acceptance criteria for #1065:
- **Circuit Breaker on Transient Errors**: Permanent errors (400 or 404 naming unserved/unknown models) stop RAG for the run with one warning. Transient errors (timeouts, connection resets, 408, 429, 5xx) skip only the failing lookup. After 3 consecutive transient failures, a circuit breaker opens for 60 seconds (`CONST_RAG_CIRCUIT_BREAKER_PAUSE_SECONDS`). While open, lookups immediately return `None` without dispatching requests.
- **Probe Coordination (`_ProbeCoordinator`)**: Instead of serializing all concurrent lookups under `_PROBE_LOCK`, lookups that arrive while no lookup has succeeded wait on a single probe lookup. If the probe succeeds, waiters run concurrently; if the probe fails, waiters skip immediately.
- **Prompted Cache Keys**: L1 and Valkey L2 cache keys hash the text after the prompt prefix is applied (`f"{model}\x00{sent_text}"`), ensuring queries and documents, or multiple prompts on identical text, map to distinct cache entries.
- **Per-Model Prompts**: `bge-m3` uses no prompt prefix. `qwen3-embedding*` queries receive `CONST_QWEN3_EMBEDDING_QUERY_PREFIX` (`Instruct: Given a code search query, retrieve relevant code or documentation\nQuery:`) and documents receive none. `nomic*` uses `search_query: ` / `search_document: `, `e5*` uses `query: ` / `passage: `, and other models use none.
- **Pinned Known Dimensions**: `CONST_KNOWN_EMBEDDING_DIMENSIONS["qwen3-embedding"] = 1024`.
- **RAG Settings Read**: `SemanticRetriever` defaults are read from `st.ai.rag.top_k` and `st.ai.rag.score_threshold` compared with `is None`, honoring threshold `0.0`. CLI chat inherits `top_k` from settings.
- **Lockfile Skipping**: `WorkspaceIndexer` skips `uv.lock`, other `*.lock` files, `package-lock.json`, `pnpm-lock.yaml`, and `go.sum`.
- **Bounded Chunk Tokens**: All returned chunks are bounded to `CONST_RAG_MAX_CHUNK_TOKENS` (8,192 tokens). Longer line windows are split into sub-windows.
- **Batch Failure Naming and Incremental Resume**: A failing batch in `_upsert_chunks` raises `EmbeddingsError` with exit code 1 naming the batch's first and last file, while earlier batches remain persisted in cache so `devops ai rag index` resumes without re-indexing.
- **Documentation & Messages**: Added `MESSAGES.rag.paused`, updated docstrings in `investigator.py`, and updated task documentation in `rag_context_indexing.md`.

## Acceptance Criteria
- [x] Permanent errors stop RAG; transient ones pause it (circuit breaker after 3 failures pauses for 60 s; `EmbeddingsError` records `is_transient`).
- [x] No failed lookup waits its turn (concurrent lookups wait on single probe outcome, finishing in < 1 s with $\le 2$ requests).
- [x] Tests with stub embedder and patched clock verify pause, resume, and 429 transient behavior.
- [x] Cache keys hash prompted text; same text under two prompts yields two cache misses.
- [x] Per-model prompt prefixes for `bge-m3`, `qwen3-embedding`, `nomic`, `e5`, and others verified with parametrized tests.
- [x] `CONST_KNOWN_EMBEDDING_DIMENSIONS["qwen3-embedding"]` is pinned to 1024.
- [x] `ai.rag` settings for `top_k` and `score_threshold` are read and reach Qdrant search.
- [x] Lockfiles (`uv.lock`, `*.lock`, `package-lock.json`, `pnpm-lock.yaml`, `go.sum`) are skipped by indexer.
- [x] No chunk sent to embedder exceeds 8,192 tokens; 4,000-line synthetic file chunking verified.
- [x] Failed batch ends index with exit 1 naming first and last file; earlier batches stay cached for resume.
- [x] `MESSAGES.rag.paused` added, docstrings and knowledge base updated.
- [x] Offline tests with stub embedders run without gateway/network and each under 1 s.
- [x] `changelog.d/1065.md` records the fix under `### Fixed`.
- [x] `uv run devops ci` passes.
- Pending a person: (after #1064) restart the Ollama pod while a multi-file review runs to verify pause and resume live.
