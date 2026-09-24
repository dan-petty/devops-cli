# Task 477: LLM Gateway Tuning Cost From Real Traffic and No-Load Capacity Estimates

**Issue**: [#477](https://github.com/dan-petty/devops-cli/issues/477)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

The tuner measures cost with a probe on a synthetic prompt, and measuring capacity takes a sweep of about eight minutes that loads every backend. vLLM's lifetime counters cannot stand in for real traffic, because they include every benchmark request, the tuner's own included.

#### Key Deliverables:
- Context & Rationale*: The tuner measures cost with a probe on a synthetic prompt, and measuring capacity takes a sweep of about eight minutes that loads every backend. vLLM's lifetime counters cannot stand in for real traffic, because they include every benchmark request, the tuner's own included.
- Deliverable*: Take cost (tokens per review request, per backend) from the spend ledger's recorded serving backend. Persist measurements, and add `--estimate`: capacity for a new or changed deployment, scaled by GPU memory bandwidth from a measured deployment running the same model and engine, without sending load.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
