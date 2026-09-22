# Task 407: Settings Load Caching

**Issue**: [#407](https://github.com/dan-petty/devops-cli/issues/407)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/config`, `priority/p2-medium`

---

## 1. Description & Objectives

`load_settings()` re-reads and re-parses the configuration files on every call at a measured 10.8 ms, and it is consulted across the whole codebase — including inside per-request paths. A narrow cache keyed on the configuration file's modification time was added to the Kubernetes context resolver in v0.2.22; the general case remains.

#### Key Deliverables:
- Context & Rationale*: `load_settings()` re-reads and re-parses the configuration files on every call at a measured 10.8 ms, and it is consulted across the whole codebase — including inside per-request paths. A narrow cache keyed on the configuration file's modification time was added to the Kubernetes context resolver in v0.2.22; the general case remains.
- Constraint*: Settings are mutable at runtime and a captured snapshot has already caused one stale-configuration defect in this project. Any cache must invalidate on the file that supplied the values rather than live for the process lifetime.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
