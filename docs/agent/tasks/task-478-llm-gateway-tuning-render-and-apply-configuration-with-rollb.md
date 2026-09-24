# Task 478: LLM Gateway Tuning Render and Apply Configuration With Rollback

**Issue**: [#478](https://github.com/dan-petty/devops-cli/issues/478)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

Recommended weights still have to be copied into the gateway ConfigMap by hand. `max_input_tokens` and the per-replica Ollama entries are maintained by hand as well, and a test only checks that the entries match the replica count.

#### Key Deliverables:
- Context & Rationale*: Recommended weights still have to be copied into the gateway ConfigMap by hand. `max_input_tokens` and the per-replica Ollama entries are maintained by hand as well, and a test only checks that the entries match the replica count.
- Deliverable*: Render a diff of the gateway configuration: weights, `max_input_tokens` derived from each backend's manifest (vLLM `--max-model-len`, `OLLAMA_CONTEXT_LENGTH`), and one entry per Ollama replica. With `--apply`, roll out the gateway, run the sweep again, and roll back if throughput drops.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
