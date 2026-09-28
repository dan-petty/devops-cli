# Task 425: Outward-Facing Capability & Upstream Maturity Survey

**Issue**: [#425](https://github.com/dan-petty/devops-cli/issues/425)
**Status**: Backlog
**Milestone**: `v0.3.0`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

Every work generator here looks inward. `devops ci`, the review pipeline, the scanners and the roadmap reconciler all answer "what is wrong with what exists" or "what did we say we would build". None can observe that a capability is behind comparable tooling, or that one of the thirty pinned runtime dependencies is no longer maintained. `uv tree --outdated` reports version freshness, which is not the same question: a package can be current and abandoned, and the last release of an archived project is always the newest one.

#### Key Deliverables:
- Context & Rationale*: Every work generator here looks inward. `devops ci`, the review pipeline, the scanners and the roadmap reconciler all answer "what is wrong with what exists" or "what did we say we would build". None can observe that a capability is behind comparable tooling, or that one of the thirty pinned runtime dependencies is no longer maintained. `uv tree --outdated` reports version freshness, which is not the same question: a package can be current and abandoned, and the last release of an archived project is always the newest one.
- Deliverable*: A survey that scores upstream maintenance from mechanical signals — last commit, release cadence, archival status, licence — for every pinned dependency, and compares this project's capabilities against comparable tools, emitting the differences as roadmap items.
- Constraint*: A survey is a work generator, and one that guesses manufactures a backlog out of its own ignorance. A capability claimed for a comparable project must carry a citation, and a feature nobody has assessed must record as unknown rather than absent, so that silence can never become scheduled work.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
