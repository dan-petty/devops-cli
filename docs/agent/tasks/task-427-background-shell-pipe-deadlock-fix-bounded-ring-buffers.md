# Task 427: Background Shell Pipe Deadlock Fix & Bounded Ring Buffers

**Issue**: [#427](https://github.com/dan-petty/devops-cli/issues/427)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Eliminates subprocess pipe deadlocks by adding daemon reader threads draining `stdout`/`stderr` into bounded ring buffers (`collections.deque(maxlen=1000)`), fulfilling the output contract for long-running commands.

#### Key Deliverables:
- Context & Rationale*: Eliminates subprocess pipe deadlocks by adding daemon reader threads draining `stdout`/`stderr` into bounded ring buffers (`collections.deque(maxlen=1000)`), fulfilling the output contract for long-running commands.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
