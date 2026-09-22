# Task 424: Public Re-Export Surface Consolidation

**Issue**: [#424](https://github.com/dan-petty/devops-cli/issues/424)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

`src/devops_cli/ai/__init__.py` declares 481 names in `__all__` with duplicates among them; `ai/agents/__init__.py` declares 556, `config/__init__.py` 410. Twenty-three duplicate entries and twenty-three unsorted lists are reported across the tree. A re-export list that large is not a public interface — it is the absence of one, and duplicate entries prove nobody can read it end to end.

#### Key Deliverables:
- Context & Rationale*: `src/devops_cli/ai/__init__.py` declares 481 names in `__all__` with duplicates among them; `ai/agents/__init__.py` declares 556, `config/__init__.py` 410. Twenty-three duplicate entries and twenty-three unsorted lists are reported across the tree. A re-export list that large is not a public interface — it is the absence of one, and duplicate entries prove nobody can read it end to end.
- Deliverable*: Establish what each package actually contracts to expose, reduce `__all__` to that, and enforce shape with `RUF022`/`RUF068`.
- Constraint*: Pre-1.0 permits removal without ceremony, but consumers inside this repository still import these names. Migrate internal call sites first and confirm with the full test suite rather than trusting the export list to describe its own users.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
