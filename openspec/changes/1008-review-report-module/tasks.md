# Tasks

## 1. Hold the report's text before the move

- [x] Add a syrupy snapshot of review.md and of the summary and full terminal views of one session that has a section of each kind, through `generate_consolidated_report`
  - Verification: `uv run devops ci test tests/review/test_report.py`

## 2. Render the report from one input

- [x] Add unit tests of the module's public functions: the drift section, the category baseline over a given history, the console finding panel, the finding sections and the verdict distributions
  - Verification: `uv run devops ci test tests/review/test_report.py`
- [x] Move the rendering into `src/devops_cli/review/report.py` with `ReportInput`, `render_markdown` and `render_console`; build the input once in `generate_consolidated_report`; count severities through one function; make `format_category_baseline_markdown` take the history
  - Verification: `uv run devops ci test tests/review/test_report.py tests/test_category_metrics.py`
- [x] Delete the orchestrator's render methods and helpers, `format_markdown_fix` in `pipeline.py`, and `ai/review/stages/`; move the tests that called them onto the module's functions or onto `generate_consolidated_report`
  - Verification: `uv run devops ci test tests/`
- [x] Describe the module in `ARCHITECTURE.md` in place of `ai/review/stages/`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1008-review-report-module`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
