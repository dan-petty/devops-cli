# Proposal

## Why

Issue #1008: the review report is rendered inside the review orchestrator.

- `ReviewPipelineOrchestrator` in `src/devops_cli/ai/review/pipeline.py` holds 30 `_build_*`, `_render_*` and `_format_*` methods and `_select_console_findings`, about 900 of its 4,412 lines, and 20 module-level render helpers and tables.
- The executive summary is in a second place, `src/devops_cli/ai/review/stages/reporting.py`, and severity is counted in both places.
- The report reads 15 orchestrator attributes, and it opens files: it loads the review history for the category baseline and the knowledge base for reference drift.
- Tests reach the rendering through 50 calls of private methods and 5 patches of `pipeline.print_table`, in 14 test files.

A change to what the report says thus touches the orchestrator, and a test of the report needs an orchestrator.

## What Changes

- New module `src/devops_cli/review/report.py`. It renders review.md (`render_markdown`) and the terminal view (`render_console`) from one frozen `ReportInput`. It reads no orchestrator attribute and opens no file.
- `generate_consolidated_report` builds the `ReportInput` once and calls the two renderers. The orchestrator keeps collection, deduplication, group analysis and persistence. It now also reads the review history for the category baseline and the knowledge-base drift, and passes them in. It also computes the executive summary's analyzer line and each analyzer's notes from its scan.
- `format_category_baseline_markdown` takes the review history to compare against, not a directory. `historical_category_metrics` computes the metrics of a history that is already loaded.
- The executive summary moves from `ai/review/stages/reporting.py` into the module, and `ai/review/stages/` is deleted. The console summary and the executive summary count severities through one function.
- The pipeline alias `format_markdown_fix` is deleted. The report module's `format_markdown_fix` replaces it.
- The tests call the module's public functions. No test calls a private render method or patches `pipeline.print_table`.
- The text of review.md and of the terminal view does not change. A syrupy snapshot of one session, recorded before the move, holds it.
- No requirement changes: the refactor keeps every output that a consumer observes, so the change has no spec delta (`skip_specs: true`).
- This change fits one pull request.

## Impact

- `src/devops_cli/review/report.py` (new), `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/ai/review/category_metrics.py`, `src/devops_cli/ai/review/__init__.py`.
- Deleted: `src/devops_cli/ai/review/stages/__init__.py`, `src/devops_cli/ai/review/stages/reporting.py`.
- `tests/review/test_report.py` (new) and its snapshot; the tests that called the private render methods; `tests/test_category_metrics.py`.
- `ARCHITECTURE.md`, which names `ai/review/stages/`.

## Feasibility

Checked on origin/main d156ce7e (2026-10-28).

- The rendering is still in the orchestrator: `pipeline.py:3407-4303` (report methods), `:1576-1763` (render helpers and tables), `:1787` (`_status_rows`), and `format_markdown_fix` at the end of the file.
- The item waited on #1151's PR 2 (refreshed plan, 2026-10-17). #1151 is closed as completed, and so are #771 (session store) and #1148 (correlation table), which the plan named for coordination. #1025, which the plan named for single-owner tables, is closed as not planned. So no item blocks this one, and the `status/blocked` label it had before the board-to-labels migration no longer applies.
- `SavedFinding.severity` is validated to CRITICAL, HIGH, MEDIUM, LOW or INFO (`review_schema.py`, `_normalize_severity`), so one count serves the console breakdown and the executive summary with the same result.
- The knowledge-base drift that the report lists when no group analysis ran depends on the knowledge base and `tools.lock` (13 entries on this checkout), so the snapshot sets a group-analysis report and a unit test covers the drift section.

## Existing Tool Considered

- Rich renders the terminal tables and panels, and the module keeps calling it through `devops_cli.output`.
- syrupy holds the snapshot of the rendered text, as `docs/TESTING.md` asks for an output whose whole text is the contract.
- No library renders this report from these models, so the module stays code of this project. The change moves code and builds none. It deletes the orchestrator's 30 render methods, the 20 module-level render helpers, `ai/review/stages/` and the duplicate severity count.
