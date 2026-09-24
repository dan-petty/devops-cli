# Task 481: Embeddings Through the LLM Gateway, With Embedding Model Evaluation

**Issue**: [#481](https://github.com/dan-petty/devops-cli/issues/481)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

The embedding task still calls one Ollama node directly (`embeddinggemma:300m`), while the gateway now serves embeddings from every Ollama node (`devops-embedding` is bge-m3, and `ollama/*` passes any model through). Retrieval quality has never been compared on this repository.

#### Key Deliverables:
- Context & Rationale*: The embedding task still calls one Ollama node directly (`embeddinggemma:300m`), while the gateway now serves embeddings from every Ollama node (`devops-embedding` is bge-m3, and `ollama/*` passes any model through). Retrieval quality has never been compared on this repository.
- Deliverable*: Point the embedding task at the gateway. Compare bge-m3, embeddinggemma and nomic-embed-text on retrieval over the indexed repository (`devops ai rag`, and the `devops ai benchmark` embedding runner): recall at k on a small labelled query set, indexing time and vector size. Re-index with the best model.
- Constraint*: Changing the model means re-indexing Qdrant, since vector sizes differ (768 and 1024).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
