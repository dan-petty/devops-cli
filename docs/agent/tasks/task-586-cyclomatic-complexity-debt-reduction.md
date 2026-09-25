# Task 586: Cyclomatic Complexity Debt Reduction

**Issue**: [#586](https://github.com/dan-petty/devops-cli/issues/586)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

AGENTS.md states complexity $\le 10$ as a project-wide invariant validated continuously. It is not: 240 functions in `src/` breach it and no gate checks it. The invariant is aspirational, and stating it as enforced is worse than stating it as a target, because reviewers and agents trust it.

#### Key Deliverables:
- Context & Rationale*: AGENTS.md states complexity $\le 10$ as a project-wide invariant validated continuously. It is not: 240 functions in `src/` breach it and no gate checks it. The invariant is aspirational, and stating it as enforced is worse than stating it as a target, because reviewers and agents trust it.
- Deliverable*: either bring the 240 down and turn on `C901`, or record a ratcheted baseline so new breaches fail while existing ones are worked off. Until one of those exists, the claim in AGENTS.md should be softened to match what is actually checked.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
