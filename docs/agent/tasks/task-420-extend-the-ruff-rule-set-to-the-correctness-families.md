# Task 420: Extend the Ruff Rule Set to the Correctness Families

**Issue**: [#420](https://github.com/dan-petty/devops-cli/issues/420)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`[tool.ruff.lint] select` is `["E", "F", "I", "N", "W", "UP"]` — style, imports, naming and modernization. The families that catch defects rather than preferences are absent. Measured against the current tree, enabling `B`, `SIM`, `RUF`, `BLE` and `ASYNC` reports 23 duplicate `__all__` entries, 39 exceptions re-raised without `from`, 6 `zip()` calls that truncate silently on length mismatch, and 6 mutable class attributes shared across instances in `src/` alone. None of these are hard to detect; nothing is detecting them.

#### Key Deliverables:
- Context & Rationale*: `[tool.ruff.lint] select` is `["E", "F", "I", "N", "W", "UP"]` — style, imports, naming and modernization. The families that catch defects rather than preferences are absent. Measured against the current tree, enabling `B`, `SIM`, `RUF`, `BLE` and `ASYNC` reports 23 duplicate `__all__` entries, 39 exceptions re-raised without `from`, 6 `zip()` calls that truncate silently on length mismatch, and 6 mutable class attributes shared across instances in `src/` alone. None of these are hard to detect; nothing is detecting them.
- Deliverable*: Adopt the correctness families in `pyproject.toml`, repair what is mechanical, and where a rule genuinely does not fit this codebase, disable it in configuration with the reason recorded. Silence from an unselected rule and silence from a deliberately disabled one look identical in the terminal and are opposites in fact.
- Constraint*: `ruff check --fix` must not be trusted blind. An unused-import pass will delete re-exports that no module in the file uses but consumers import, which is a failure that surfaces as an unrelated test module ceasing to collect. Apply fixes in one batch, then run the full gate set — lint, types and tests together.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
