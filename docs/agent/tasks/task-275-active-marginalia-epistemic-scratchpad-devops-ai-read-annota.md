# Task 275: Active Marginalia & Epistemic Scratchpad (`devops ai read annotate`)

**Issue**: [#275](https://github.com/dan-petty/devops-cli/issues/275)
**Status**: Backlog
**Milestone**: `v0.2.21`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Emulates human active reading ("reading with a pencil"). Provides a persistent, file-anchored note and hypothesis tier (`.data/marginalia/<file_hash>.jsonl`).

#### Key Deliverables:
- Context & Rationale*: Emulates human active reading ("reading with a pencil"). Provides a persistent, file-anchored note and hypothesis tier (`.data/marginalia/<file_hash>.jsonl`).
- Structured Marginalia Schema*: Records typed annotations attached to file paths, AST nodes, or line ranges: `[ASSUMPTION]`, `[HYPOTHESIS]`, `[CONTRADICTION]`, `[QUESTION]`, `[TODO]`.
- Context Injection*: Automatically surfaces relevant prior marginalia into subsequent inspection passes, ensuring the agent remembers prior observations across turns and sessions without redundant re-reading.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across all 10 CI quality gates (`uv run devops ci`).
