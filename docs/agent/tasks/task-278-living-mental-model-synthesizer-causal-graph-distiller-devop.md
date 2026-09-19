# Task 278: Living Mental Model Synthesizer & Causal Graph Distiller (`devops ai research model`)

**Issue**: [#278](https://github.com/dan-petty/devops-cli/issues/278)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.21`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Progressively compacts sprawling research observations into a concise, living mental model (`.data/research/mental_model_<topic>.yaml`).

#### Key Deliverables:
- Context & Rationale*: Progressively compacts sprawling research observations into a concise, living mental model (`.data/research/mental_model_<topic>.yaml`).
- Causal & State Machine Modeling*: Distills raw text findings into explicit state transitions, causal DAGs, and invariant rules that serve as working theories during complex refactorings and defect investigations.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across all 10 CI quality gates (`uv run devops ci`).
