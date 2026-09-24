# Task 530: Remove the Review Stage Modules the Pipeline Never Calls

**Issue**: [#530](https://github.com/dan-petty/devops-cli/issues/530)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/refactor`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

`src/devops_cli/ai/review/stages/` exported seven `run_*_stage` functions, of which the
orchestrated pipeline called only `run_adversarial_debate_stage`; from `stages/reporting.py` it
used only `synthesize_report_executive_summary`. The other six duplicated the pipeline's logic
and had drifted from it: `static_scan.py` still printed "Static analyzers completed (0 finding(s)
detected)" and never called Trivy (#516). Tests imported them, which kept them looking alive.

### Key Deliverables Completed:

- [x] **Removed**: `pre_analysis.py`, `static_scan.py`, `persona_review.py`, `verification.py`
  and `reranking.py`, and `run_reporting_stage` from `reporting.py`. `stages` now exports
  the adversarial debate and the report's executive summary, the parts the pipeline uses.
- [x] **Guards moved onto the pipeline**, which lacked them:
  - The orchestrator refuses a session directory with a `..` component, or outside the reviews,
    working or temporary directory, before writing to it. `run_reporting_stage` checked this.
  - `_resolve_file_path` resolves only to files inside the review target or its repository.
    A path outside both, absolute or through `..`, falls back to a missing in-target path, as
    `_resolve_target_path` required. It used to return any existing absolute path.
- [x] **Automated Tests & Quality Gates**:
  - Tests of the removed functions are gone; `tests/test_review_stages.py` keeps the adversarial
    debate.
  - `tests/test_subsystem_containment_and_redaction.py`: the session directory and file path
    containment tests now exercise the pipeline.
  - The duplicate executive-summary test through `run_reporting_stage` is removed; the
    pipeline's own report tests cover it.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
