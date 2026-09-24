# Task 555: Evaluation History, Comparison and Regression Checks

**Issue**: [#555](https://github.com/dan-petty/devops-cli/issues/555)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Runs are compared by hand: score tables side by side, or JSON diffed in scratch scripts. A result is useful over the life of the tool only if the next run can be set against it.

#### Key Deliverables:
- Context & Rationale*: Runs are compared by hand: score tables side by side, or JSON diffed in scratch scripts. A result is useful over the life of the tool only if the next run can be set against it.
- Deliverable*: Commands to list runs by mechanism and subject, show one, and compare two or a run against the subject's baseline, with each metric's change (recall, prompt tokens, wall time, backend share) beside the change in setup fingerprint; an explicit baseline per subject, and a check that fails a run regressing past a tolerance, to gate releases.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
