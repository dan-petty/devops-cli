# Task 640: ReviewProfile Verdict Distributions Schema Rejects Float Citation Rates

**Issue**: [#640](https://github.com/dan-petty/devops-cli/issues/640)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

During branch reviews (`devops ai review branch`), session completion crashed at `_write_review_profile` / `profiler.build()` with:
```
ValidationError: 1 validation error for ReviewProfile
verdict_distributions.citation_rates.unknown
  Input should be a valid integer, got a number with a fractional part [type=int_from_float, input_value=0.61, input_type=float]
```

### Root Cause
`compute_verdict_distributions` (introduced to compute per-adjudicator citation rates) populates `"citation_rates": dict[str, float]`.
However, `ReviewProfile.verdict_distributions` in `src/devops_cli/ai/review/profile.py` was typed as `dict[str, dict[str, int]]`. When Pydantic validates `ReviewProfile`, float values in `citation_rates` (such as `0.61`) fail validation because Pydantic expects `int`.

### Key Deliverables Completed:
- [x] **Permit Float Rates in ReviewProfile and ReviewProfiler** (`src/devops_cli/ai/review/profile.py`):
  - Updated `ReviewProfile.verdict_distributions` type annotation to `dict[str, dict[str, int | float]]`.
  - Updated `ReviewProfiler._verdict_distributions` and `ReviewProfiler.set_findings(..., verdict_distributions=...)` annotations to `dict[str, dict[str, int | float]]`.
- [x] **Comprehensive Test Coverage & Architectural Invariant Gates** (`tests/test_verdict_polarity.py`):
  - Updated `test_review_profile_verdict_distributions` to include `citation_rates` with float rates.
  - Verified serialization (`model_dump_json`), file persistence (`profile.write`), and deserialization (`ReviewProfile.load`).
  - Consolidated linear assertions into structural tuple equality checks.
  - 100% compliance across Gated CI validation suite (`uv run devops ci`).
