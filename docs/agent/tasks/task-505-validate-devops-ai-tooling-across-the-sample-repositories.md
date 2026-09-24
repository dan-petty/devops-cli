# Task 505: Validate devops ai Tooling Across the Sample Repositories

**Issue**: [#505](https://github.com/dan-petty/devops-cli/issues/505)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Nothing shows whether AST parsing, repomaps, analysis and reviews work on projects that are not Python: which parser runs, whether pages and labels are right, and whether the reviewer finds defects in each language.

#### Key Deliverables:
- One command runs the tooling over the fetched samples and saves a JSON report per category: files parsed, symbols found and the parser used; repomap and analysis output; and a scored review of the category's synthetic defect corpus. The first full run is recorded, and every failure becomes an issue.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
