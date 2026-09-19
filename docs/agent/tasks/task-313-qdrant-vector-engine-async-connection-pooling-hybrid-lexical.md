# Task 313: Qdrant Vector Engine Async Connection Pooling, Hybrid Lexical-Dense Search & Payload Quantization Research

**Issue**: [#313](https://github.com/dan-petty/devops-cli/issues/313)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

RAG knowledge base search uses basic synchronous vector inserts and pure dense cosine similarity, which can miss exact keyword symbol matches and consumes unnecessary workstation RAM.

#### Key Deliverables:
- Context & Rationale*: RAG knowledge base search uses basic synchronous vector inserts and pure dense cosine similarity, which can miss exact keyword symbol matches and consumes unnecessary workstation RAM.
- Deep Integration & Functional Extension*: Asynchronous Qdrant client connection pooling; hybrid search combining dense neural vector embeddings with sparse BM25 lexical indices; memory-mapped on-disk scalar/product payload quantization; background collection snapshotting and hot-reload during repository re-indexing.
- Code Optimization & Performance Acceleration*: Slash vector retrieval latency by 60%+ through async batched queries; reduce vector index memory footprint by up to 75% via scalar quantization; eliminate blocking during repository re-indexing.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/ai/rag/` to decouple embedding generation, vector storage, and query filtering into distinct pipeline stages; replace procedural file chunking loops with functional generator pipelines; remove legacy file staging.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
