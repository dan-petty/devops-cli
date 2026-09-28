# Task 274: Agentic Information Foraging & Scent Tracker (`devops ai research forage`)

**Issue**: [#274](https://github.com/dan-petty/devops-cli/issues/274)
**Status**: Backlog
**Milestone**: `v0.2.21`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/ai`, `priority/p0-critical`

---

## 1. Description & Objectives

Implements Pirolli & Card's Information Foraging Theory. Rather than executing disjointed keyword grep searches, the agent follows relational "information scent" across codebases and repositories.

#### Key Deliverables:
- Context & Rationale*: Implements Pirolli & Card's Information Foraging Theory. Rather than executing disjointed keyword grep searches, the agent follows relational "information scent" across codebases and repositories.
- Breadcrumb Relational Crawler*: Traverses outbound cues from a starting anchor (error traceback, failing test, or feature keyword) across symbol imports, call hierarchies, git blame history, PR discussions, and markdown references.
- Heuristic Scent Scoring & Backtracking*: Scores edges based on semantic relevance to the inquiry; maintains an explicit traversal ledger that detects circular paths and systematically backtracks when an information trail grows cold.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across all 10 CI quality gates (`uv run devops ci`).
