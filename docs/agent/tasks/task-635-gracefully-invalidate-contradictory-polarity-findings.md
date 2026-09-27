# Task 635: Gracefully Invalidate Contradictory Polarity Findings & Eliminate Escape Sequence Syntax Warnings

**Issue**: [#635](https://github.com/dan-petty/devops-cli/issues/635)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

During branch reviews (`devops ai review branch`), models occasionally generate candidate findings with contradictory polarity assertions where `observed_value == expected_value` (e.g. asserting that a concrete value is wrong when the observed value matches expected) or single-sided polarity assertions where only one counterpart is set. Previously, `Finding._validate_polarity` raised `ValueError`, which caused `ReviewResult.model_validate` in `MultiAgentPipeline` to fail with `ValidationError: Failed to validate pipeline output schema`, entirely discarding the review results of affected files.

Additionally, `_parse_stringified_collection` attempted `ast.literal_eval` before `json.loads`. In JSON (RFC 8259), `\/` is a standard escape for `/`, but passing strings containing `\/` to Python's AST compiler triggers `<unknown>:1: SyntaxWarning: "\/" is an invalid escape sequence`.

### Key Deliverables Completed:
- [x] **Graceful Polarity Invalidation & Orphan Cleanup** (`src/devops_cli/ai/review_schema.py`):
  - Updated `Finding._validate_polarity` to gracefully invalidate findings where `observed_value.strip().lower() == expected_value.strip().lower()`, setting `status="INVALIDATED"`, `reportable=False`, `verified=False`, `verified_by="deterministic:verdict_polarity"`, and setting `invalidation_reason` instead of raising `ValueError`.
  - Handled asymmetric polarity assertions by safely resetting orphan fields (`self.observed_value = None; self.expected_value = None`) so findings can be evaluated on their general merits without failing schema validation.
  - Added defensive `mode="before"` validator on `ReviewResult.findings` to ensure list items are dicts or `Finding` instances.
- [x] **Elimination of SyntaxWarning in Stringified Collection Parsing** (`src/devops_cli/ai/review_schema.py`):
  - Updated `_parse_stringified_collection` to prioritize `json.loads` over `ast.literal_eval`.
  - Introduced `_safe_literal_eval` wrapping `ast.literal_eval` in a warning filter suppressing `SyntaxWarning` for invalid escape sequences in string literals.
- [x] **Comprehensive Test Coverage & Architectural Invariant Gates** (`tests/test_verdict_polarity.py`):
  - Added `test_finding_polarity_graceful_handling` verifying that identical polarity values automatically mark the finding `INVALIDATED` and asymmetric values clear orphan polarity.
  - Added `test_review_result_graceful_polarity_deserialization` validating pipeline schema deserialization across multiple findings without dropping file results.
  - Added `test_parse_stringified_collection_escapes` testing forward-slash escape handling without `SyntaxWarning`.
  - Consolidated linear assertions into structural tuple equality checks.
  - 100% compliance across Gated CI validation suite (`uv run devops ci`).
