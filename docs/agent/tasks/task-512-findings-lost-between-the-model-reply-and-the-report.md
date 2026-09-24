# Task 512: Findings Lost Between the Model Reply and the Report

**Issue**: [#512](https://github.com/dan-petty/devops-cli/issues/512)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

From the #509 audit. Scanner findings are overwritten by persona findings, one malformed field drops a whole reply, and titles sharing half their words merge distinct defects at any line. Real titles can be blanked by sanitizing. A persona can set its own status, and redaction rewrites code (hashing calls, token sources) before any model sees it. Every loss is silent.

#### Key Deliverables:
- Scanner and persona findings reach the report together, a reply keeps every valid finding, distinct defects stay distinct, and redaction masks secret values only. Each case has a test that reproduced the loss first.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
