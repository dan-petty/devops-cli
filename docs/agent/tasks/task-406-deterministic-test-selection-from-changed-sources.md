# Task 406: Deterministic Test Selection From Changed Sources

**Issue**: [#406](https://github.com/dan-petty/devops-cli/issues/406)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`devops ci test` already narrows to tests covering the source files it is given, which is what makes the pre-commit hook fast. The pre-push and full runs do not use it, so any change runs the whole suite. Coverage data already records which tests touch which modules.

#### Key Deliverables:
- Context & Rationale*: `devops ci test` already narrows to tests covering the source files it is given, which is what makes the pre-commit hook fast. The pre-push and full runs do not use it, so any change runs the whole suite. Coverage data already records which tests touch which modules.
- Deliverable*: Build the reverse index from coverage output and select the covering tests for a changed set, with an explicit full-suite fallback whenever the index is stale, absent, or the change touches a shared fixture or configuration file.
- Constraint*: Under-selection silently ships an untested change. Selection must be advisory on top of a full run in CI, and only authoritative locally where a full run precedes the push.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
