# Task 436: Semantic Validator Deprecation & Structural Positional Oracles

**Issue**: [#436](https://github.com/dan-petty/devops-cli/issues/436)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Audits AI review schemas and validators to strip keyword-matching assertions in favor of strict structural schema boundaries and positional enumeration.

#### Key Deliverables:
- Context & Rationale*: Audits AI review schemas and validators to strip keyword-matching assertions in favor of strict structural schema boundaries and positional enumeration.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
