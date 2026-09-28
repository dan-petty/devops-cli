# Task 690: AI Constellation Topology, RAG Health & Review Findings Studio (`tab-ai`)

**Issue**: [#690](https://github.com/dan-petty/devops-cli/issues/690)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Deep inspection of local and distributed AI inference tiers and knowledge bases.

#### Key Deliverables:
- Context & Rationale*: Deep inspection of local and distributed AI inference tiers and knowledge bases.
- Ollama Constellation Topology*: Node health matrix, active model weights, GPU VRAM allocation gauges, and failover circuit breaker status.
- RAG Vector Tier Health*: Qdrant collection size, indexed document count, semantic drift score, and Valkey L2 embedding cache hit ratio sparkline.
- Review Findings Studio*: Interactive hierarchical tree of AI code review findings with severity badges, collapsible rationale scratchpads, file diff snippet previews, and one-key finding status transitions (`MITIGATED`, `INVALIDATED`).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
