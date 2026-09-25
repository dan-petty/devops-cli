# Task 434: False-Positive Rate Tracking Across Runs

**Issue**: [#434](https://github.com/dan-petty/devops-cli/issues/434)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Track per-category false-positive rates across review runs and surface them in review reports and CLI statistics. Enables prompt engineers and developers to measure the impact of prompt and verifier adjustments against historical baselines rather than intuition.

### Key Deliverables Completed:

- [x] **Schema Category Tracking** (`src/devops_cli/ai/review_schema.py`):
  - Added optional `category: str | None` field with flexible alias choices (`category`, `type`, `classification`, `defect_class`) to `Finding`.
  - Updated finding merge consolidation (`_merge_two_findings`) to preserve finding category classification.
- [x] **Category Metrics Analytics Engine** (`src/devops_cli/ai/review/category_metrics.py`):
  - `CategoryMetric`: dataclass capturing category, total findings, invalidated count, verified count, unverified count, mitigated count, and calculated false-positive rate percentage.
  - `resolve_finding_category`: resolves explicit finding categories with fallback to semantic hallucination category inference (`_infer_hallucination_category`).
  - `compute_category_metrics`: aggregates finding status breakdowns and computes percentage false-positive rates segmented by category.
  - `collect_historical_category_metrics`: safely aggregates historical findings and calculates multi-session baselines across saved review session directories in Valkey/local data storage.
  - `format_category_baseline_markdown`: formats Markdown table comparing session category false-positive rates against the historical cross-run baseline.
  - Re-exported all category metrics models and functions in `src/devops_cli/ai/review/__init__.py`.
- [x] **CLI Review Stats Enhancement** (`src/devops_cli/commands/review.py`):
  - Decomposed `review_stats` procedural loop into single-responsibility helpers (`_tally_single_session_findings`, `_load_sessions_data`, `_render_status_breakdown_table`, `_render_persona_stats_table`, `_render_category_stats_table`), reducing cyclomatic complexity from $M = 15$ to $M \le 4$.
  - Added `Category False Positive Rate (Invalidated)` breakdown table to `devops review stats`.
- [x] **Review Pipeline Report Integration** (`src/devops_cli/ai/review/pipeline.py`):
  - Integrated `## Category Verification & False-Positive Baseline` section into consolidated Markdown reports (`review.md`).
  - Added overall session `False Positive Rate` metric to console summary table (`_render_console_summary_table`).
- [x] **Automated Tests & Quality Gates** (`tests/test_category_metrics.py`, `tests/test_review.py`):
  - Unit tests covering explicit and inferred category resolution, empty and mixed metric computation, historical aggregation across sessions, Markdown table generation, and pipeline summary integration with structural tuple equality assertions.
  - Verified `Category False Positive Rate (Invalidated)` table rendering in `tests/test_review.py`.
  - Enforced complexity $M \le 10$ and depth $\le 5$ project-wide.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
