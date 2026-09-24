# Task 514: Hallucinations Catalog Learns From Unreliable Invalidations and Never Forgets

**Issue**: [#514](https://github.com/dan-petty/devops-cli/issues/514)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

From the #509 audit. The catalog learns from LLM verdicts, weak checks and evaluation replays. It rewrites builtin entries with learned words, and it never expires or lists what it learned. Some categories' ground truth only checks that the file parses.

#### Key Deliverables:
- Learn only from deterministic invalidations with real ground truth, keep builtin entries immutable, list and remove learned entries, and give every invalidating category a ground truth that checks the claim.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
