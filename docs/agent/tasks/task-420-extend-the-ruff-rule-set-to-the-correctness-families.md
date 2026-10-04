# Task 420: Extend the Ruff Rule Set to the Correctness Families

**Issue**: [#420](https://github.com/dan-petty/devops-cli/issues/420)
**Status**: Done
**Milestone**: `v0.2.26`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`[tool.ruff.lint] select` was `["E", "F", "I", "N", "W", "UP"]` — style, imports, naming and modernization. The families that catch defects rather than preferences were absent. Enabling `B`, `SIM`, `RUF`, and `ASYNC` surfaced 146 violations across `src/` and `tests/`, including duplicate `__all__` entries, exceptions re-raised without `from`, `zip()` calls that truncate silently on length mismatch, mutable class attributes shared across instances, and background tasks created without holding references.

This deliverable adopts whole correctness families (`B`, `RUF`, `ASYNC`) alongside targeted correctness rules (`SIM115`, `PT011`, `PT015`, `PT017`, `PGH003`) in `pyproject.toml`, fixes all 146 violations cleanly across `src/` and `tests/` with zero blanket or file-level suppressions, pins suppression lint rules and mypy configuration in architectural invariants, lowers the C901 suppression ceiling from 66 to 65, records cold-cache lint execution timings, and documents the rule configuration in the knowledge base and changelog fragment.

#### Key Deliverables:
- Adopt correctness families: Enable `B`, `RUF`, and `ASYNC` whole families, single codes `SIM115`, `PT011`, `PT015`, `PT017`, `PGH003`, alongside existing `C901`, `PGH004`, and `RUF100`.
- Drop redundant codes: Remove `B017`, `RUF022`, `RUF043`, `RUF068` as they are subsumed by family selections.
- Explicit ignore documentation: Document one-line justifications for `E501`, `N818`, `B009`, `B010`, `RUF005`, and `ASYNC109`.
- Typography & type check configuration: Add `allowed-confusables = ["–", "×", "ℹ"]` to Ruff and `enable_error_code = ["ignore-without-code"]` to `[tool.mypy]`.
- Complete defect remediation: Fix all 146 rule violations without blanket or file-level suppressions, adding exactly one inline `# noqa: SIM115` at `src/devops_cli/github/rate_limiter.py:218`.
- Invariant enforcement: Pin `CONST_SUPPRESSION_LINT_RULES` in `src/devops_cli/config/constants.py` and enforce with `test_suppression_lint_rules_enforced` and `test_mypy_ignore_without_code_enabled` in `tests/test_architectural_invariants.py`.
- Lower C901 ceiling: Decompose Tarjan SCC algorithm in `tests/test_architectural_invariants.py` and lower `DEFAULT_C901_SUPPRESSION_CEILING` from 66 to 65.
- Update knowledge base: Update `src/devops_cli/ai/knowledge_base/devops_cli/libraries/ruff_mypy_pytest.md`.
- Performance benchmarking: Measure 3 cold-cache runs of `uv run ruff check --no-cache .` (Run 1: 1.32s, Run 2: 1.04s, Run 3: 1.25s, mean: 1.20s real time).
- Changelog fragment: Create `changelog.d/420.md`.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Acceptance Criteria Checklist

- [x] **Criterion 1 (Configuration & Family Selection)**: Whole families `B`, `RUF`, and `ASYNC` selected; individual codes `SIM115`, `PT011`, `PT015`, `PT017`, `PGH003` selected; superseded codes `B017`, `RUF022`, `RUF043`, `RUF068` dropped; `allowed-confusables` configured; `ignore-without-code` enabled in `[tool.mypy]`.
- [x] **Criterion 2 (Explicit Ignore Reasons)**: Each ignore rule (`E501`, `N818`, `B009`, `B010`, `RUF005`, `ASYNC109`) carries an inline house-style justification comment.
- [x] **Criterion 3 (Zero Blanket Waivers & Single Inline Suppression)**: Zero file-level `# ruff: noqa` or `# flake8: noqa` exemptions; zero blanket waivers in `per-file-ignores`; exactly one inline `# noqa: SIM115` at `src/devops_cli/github/rate_limiter.py:218`.
- [x] **Criterion 4 (Clean Violation Remediation)**: All 146 reported violations fixed across `src/` and `tests/` (`SIM115`, `RUF001`, `RUF006`, `RUF007`, `RUF010`, `RUF012`, `RUF015`, `RUF019`, `RUF023`, `RUF034`, `RUF046`, `RUF059`, `B006`, `B007`, `B008`, `B023`, `B904`, `B905`, `B911`, `PT011`).
- [x] **Criterion 5 (Architectural Invariants & Suppression Pinning)**: `CONST_SUPPRESSION_LINT_RULES` declared in `constants.py`; `test_suppression_lint_rules_enforced` and `test_mypy_ignore_without_code_enabled` added and passing in `tests/test_architectural_invariants.py`.
- [x] **Criterion 6 (Lowered C901 Suppression Ceiling)**: Tarjan SCC helper decomposed into `_TarjanState`, `DEFAULT_C901_SUPPRESSION_CEILING` lowered from 66 to 65 in `defaults.py`, passing `test_c901_suppressions_stay_under_the_ceiling`.
- [x] **Criterion 7 (Knowledge Base Documentation)**: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/ruff_mypy_pytest.md` updated with expanded rule family list and explanation.
- [x] **Criterion 8 (Performance Measurement)**: 3 runs of `uv run ruff check --no-cache .` measured (Run 1: 1.32s, Run 2: 1.04s, Run 3: 1.25s, average: ~1.20s real time, cold-cache execution across 518 source files).
- [x] **Criterion 9 (Changelog Fragment)**: `changelog.d/420.md` created matching house style under `### Added`; zero edits to `CHANGELOG.md` or `docs/ROADMAP.md`.
- [x] **Criterion 10 (Gated CI Quality Gate)**: 100% passing across Gated CI validation suite (`uv run devops ci`).
