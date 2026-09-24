# Task 513: Verification Discards Real Findings on Substring Triggers and Malformed Verdicts

**Issue**: [#513](https://github.com/dan-petty/devops-cli/issues/513)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

From the #509 audit. Deterministic checks fire on substrings: "sse" in "processed", "if none of the roles", a bare "syntax". A verdict with `invalidated_criteria_matched` beats `verified: true`, uncertainty hides the finding, and verdicts can bind to the wrong finding.

#### Key Deliverables:
- Each trigger matches only its claim, and uncertain or malformed verdicts leave the finding unverified and reported. Verdicts bind by title and location together. The verifier prompt's project-specific assumptions move to #515.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
