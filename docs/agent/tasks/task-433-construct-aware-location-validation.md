# Task 433: Construct-Aware Location Validation

**Issue**: [#433](https://github.com/dan-petty/devops-cli/issues/433)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`_check_line_boundaries` invalidates a finding only when its line number exceeds the file length. A location that is in-bounds but points at unrelated code passes untouched, so a finding can describe a real defect while sending the reader — or an auto-fix stage — to the wrong construct.

This deliverable implements construct-aware finding location validation in the review pipeline:
1. Verifies that a finding's cited line span actually contains the construct (function, class, call, decorator, assignment, symbol, or literal) named by the finding using Python AST inspection and lexical verification.
2. On mismatch, attempts relocation by AST symbol search and text matching, updating `Finding.location` to the relocated span and recording the previous location in `Finding.relocated_from`.
3. Invalidates the finding with `status="INVALIDATED"` only when the cited construct is absent from the file entirely.

#### Key Deliverables Completed:
- [x] Added `relocated_from: str | None = None` field to `Finding` model in `devops_cli.ai.review_schema` and preserved it during finding merges.
- [x] Implemented `devops_cli.ai.review.construct_validator` with `AstConstruct`, `collect_ast_constructs`, `extract_finding_construct_candidates`, and `validate_construct_location`.
- [x] Integrated `validate_construct_location` into `_deterministic_pre_verification` immediately following code file boundary checks.
- [x] Maintained single-responsibility decomposition to enforce cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ project-wide.
- [x] Comprehensive unit and integration test suite with structural tuple equality assertions (`tests/test_construct_aware_location.py`).
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Evidence

- `tests/test_construct_aware_location.py`: 12 passed in 26s.
- `tests/test_review_verification.py`: 84 passed in 35s.
- `tests/test_review_pipeline.py`: 28 passed in 44s.
- `tests/test_agent_task_files.py`: 217 passed in 25s.
- `tests/test_architectural_invariants.py`: 13 passed in 33s.
- `devops scan complexity`: 100% compliance across `construct_validator.py`.
