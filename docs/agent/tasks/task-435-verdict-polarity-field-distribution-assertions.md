# Task 435: Verdict Polarity & Field Distribution Assertions

**Issue**: [#435](https://github.com/dan-petty/devops-cli/issues/435)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Two review-quality failures were invisible to the review schema:
1. **Polarity**: A finding asserting a status field was "always set to ERROR" where the exported value was OK — a real defect with inverted meaning and wrong severity, which verification passed at high confidence because nothing compared observed against expected.
2. **Distribution**: `reportable` was `true` for all 286 findings including the 7 never verified; a verdict field that never comes back false is a column, not a filter.

### Key Deliverables Completed:

- [x] **Schema Verdict Polarity & Distribution Computation** (`src/devops_cli/ai/review_schema.py`):
  - Added `observed_value: str | None` and `expected_value: str | None` fields to `Finding` with aliases (`observed`, `actual_value`, `actual`, `expected`).
  - Added `@field_validator("_clean_polarity_value")` and `@model_validator("_validate_polarity")` requiring both fields when either is provided and rejecting identical values (`observed_value == expected_value`).
  - Updated finding merge consolidation (`_merge_two_findings`) to preserve polarity fields.
  - Implemented and exported `compute_verdict_distributions(findings)` and `is_field_discriminating(counts)`.
- [x] **Deterministic Pre-Verification & Verdict Polarity Invalidation** (`src/devops_cli/ai/review/verification.py`):
  - Added `_check_verdict_polarity_hallucination` invalidating candidate findings where `observed_value == expected_value` as contradictory hallucinations.
  - Integrated into `_deterministic_pre_verification` early invalidation checks.
  - Updated `_apply_single_finding_verification` to handle `observed_value`/`expected_value` in LLM verdicts and invalidate matching values.
- [x] **Pipeline Integration & Self-Test Verification** (`src/devops_cli/ai/review/pipeline.py`):
  - Updated payload generation and verification (`_verify_single_file_payload`) to carry `observed_value` and `expected_value`.
  - Added `_format_verdict_distributions` and updated `_render_console_summary_table` to include verdict distribution rows and flag non-discriminating fields (`NON-DISCRIMINATING`).
  - Added `_build_verdict_distributions_section` and wired it into `_build_consolidated_markdown_report`.
  - Updated `generate_consolidated_report` to pass `candidate_findings=candidates.findings` so verdict distributions and false-positive rates reflect all evaluated findings.
  - Implemented `run_pipeline_self_test(target_dir)` asserting that an engineered contradictory finding is systematically invalidated and withdrawn by the pipeline.
  - Re-exported `compute_verdict_distributions`, `is_field_discriminating`, and `run_pipeline_self_test` in `src/devops_cli/ai/review/__init__.py`.
- [x] **Review Profile Tracking & Runner Recording** (`src/devops_cli/ai/review/profile.py`, `src/devops_cli/ai/review/runner.py`):
  - Added `verdict_distributions: dict[str, dict[str, int]]` to `ReviewProfile`.
  - Updated `ReviewProfiler.set_findings` and `build` to store verdict distributions in `profile.json`.
  - Updated `_record_profile_findings` in `runner.py` to calculate and record verdict distributions via `compute_verdict_distributions(findings)`.
- [x] **Review Task Prompts & Instruction Alignment** (`src/devops_cli/ai/tasks/review_output_instruction.md`, `src/devops_cli/ai/tasks/review.md`):
  - Documented `observed_value` and `expected_value` in JSON schema output instructions and code review protocol.
  - Added strict rule invalidating contradictory findings where `observed_value == expected_value`.
- [x] **Automated Tests & Quality Gates** (`tests/test_verdict_polarity.py`):
  - Comprehensive unit and integration test coverage with structural tuple equality assertions.
  - Enforced cyclomatic complexity $M \le 10$ and maximum nesting depth $\le 5$.
  - 100% passing across Gated CI validation suite (`uv run devops ci`).
