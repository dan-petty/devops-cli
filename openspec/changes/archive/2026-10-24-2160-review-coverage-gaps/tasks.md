# Tasks

## 1. A review states each file that a stage cannot read as a coverage gap

- [x] 1.1 Write tests in `tests/ai/review/test_coverage_gaps.py` for a file that pre-analysis, admission and the threat-intelligence lookup cannot read, each of which checks the row of the report's table of skipped and errored files, and for a Python file too deep for the `ast` module, which gets metadata and no row. See them fail on the base code with `uv run devops ci test tests/ai/review/test_coverage_gaps.py`
- [x] 1.2 Write the cache test in `tests/ai/review/test_pre_analysis_scope.py` for a cached time with no time zone and a time that does not parse, and verify with `uv run devops ci test tests/ai/review/test_pre_analysis_scope.py`
- [x] 1.3 In `src/devops_cli/ai/review/pipeline.py`, catch only `OSError` in pre-analysis, admission and the threat-intelligence lookup and record each file as a coverage gap; read a cited file through `_read_cited_file` only, and delete `_file_content` and `_read_content`; catch only `OSError` and `ValueError` in the cache check; delete the handlers around `find_repo_root`, `list_repo_files` and the preparation of a path. Verify with `uv run devops ci test tests/ai/review/test_coverage_gaps.py tests/ai/review/test_pre_analysis_scope.py tests/ai/review/test_pipeline.py tests/test_review_pipeline.py tests/test_review_worktree_regression.py`
- [x] 1.4 Catch `RecursionError` as well as `SyntaxError` in `_analyze_python_ast` (`src/devops_cli/ai/analyze/scanner.py`), and verify with `uv run devops ci test tests/ai/review/test_coverage_gaps.py tests/test_ai_analyze_outlines.py tests/test_analyze.py`
- [x] 1.5 Change the executive summary of a review with coverage gaps in `src/devops_cli/ai/review/stages/reporting.py`, and verify with `uv run devops ci test tests/test_review_report_summary.py`
- [x] 1.6 Lower the swallowed-failures ceiling of `src/devops_cli/ai/review/pipeline.py` with `uv run python -m tests.test_swallowed_failures_ratchet --lower`, and verify with `uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py`
- [x] 1.7 Say what the table of skipped and errored files holds in `docs/SELF_IMPROVEMENT.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
