# Task 418: In-Flight Work, PR Stagnation & Blocker Radar (`devops gh pm inflight`)

**Issue**: [#418](https://github.com/dan-petty/devops-cli/issues/418)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/github`, `priority/p0-critical`

---

## 1. Description & Objectives

Continuous surveillance of active in-flight work across the repository to eliminate PR starvation, review stagnation, and merge conflict decay.

#### Key Deliverables:
- Context & Rationale*: Continuous surveillance of active in-flight work across the repository to eliminate PR starvation, review stagnation, and merge conflict decay.
- FIFO PR Queue Surveillance*: Enforces strict chronological (oldest to newest / FIFO) PR processing and surfaces older open PRs that are being starved or blocked by newer work.
- Stagnation & Bottleneck Detection*: Flags PRs with unresolved Copilot/peer review threads, failing CI checks, or unassigned reviewers exceeding configurable latency thresholds (e.g. >24h); emits actionable remediation nudges.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
