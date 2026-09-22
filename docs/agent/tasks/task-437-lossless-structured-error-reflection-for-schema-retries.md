# Task 437: Lossless Structured Error Reflection for Schema Retries

**Issue**: [#437](https://github.com/dan-petty/devops-cli/issues/437)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Enhances Pydantic schema validation error feedback by preserving up to 5 field paths with type violations and prescriptive fix hints, enabling single-turn model self-correction.

#### Key Deliverables:
- Context & Rationale*: Enhances Pydantic schema validation error feedback by preserving up to 5 field paths with type violations and prescriptive fix hints, enabling single-turn model self-correction.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
