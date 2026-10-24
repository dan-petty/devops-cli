# Proposal

## Why

Issue #2160: at b170358e, `src/devops_cli/ai/review/pipeline.py` has eight `except Exception` handlers that hide a failure that changes what a review checks. The review does not tell the user about these failures:

- A file that pre-analysis cannot read gets no metadata. A Python file whose expression is too deep for the `ast` module also gets no metadata: the parse raises `RecursionError`, and the handler hides it.
- A scanner finding in a file that admission cannot read is rejected as `path-not-in-commit`.
- A file that the threat-intelligence lookup cannot read has no network references.

The handlers log these failures at debug level, or not at all. Two copies of one file read exist: `_file_content` in `_admit_scanner_findings` and `_read_content` in `_admit_advisory_finding`.

## What Changes

- Pre-analysis catches only `OSError` from the read of a file. It records the file as a coverage gap with the reason `Pre-analysis: <error>`.
- `_analyze_python_ast` (`src/devops_cli/ai/analyze/scanner.py`) treats a `RecursionError` of `ast.parse` as it treats a `SyntaxError`: the symbols come from the text of the file. `extract_python_source_symbols` in `src/devops_cli/ai/analyze/symbols.py` already does this. So pre-analysis gives metadata for such a file, and the narrower handler does not stop the review.
- Admission reads a cited file through one function, `_read_cited_file`, which replaces `_file_content` and `_read_content`. The function catches only `OSError`, and records the file as a coverage gap with the reason `Admission: <error>`.
- The threat-intelligence lookup catches only `OSError` from the read of a file. It records the file as a coverage gap with the reason `Threat intelligence: <error>`.
- The check of cached metadata catches only `OSError` and `ValueError`. A cached time with no time zone is a cache miss. The check compares the file time as a number, so the comparison cannot raise. A cache miss changes nothing that the user relies on: the file is analyzed again, and that analysis reports a file that it cannot read.
- `_collect_paths_to_analyze` has no handler. After the cache check catches its own errors, nothing in its loop raises.
- The constructor calls `find_repo_root`, and `_collect_scanner_commit_files` calls `list_repo_files`, with no handler. Neither function raises for a path that the file system accepts (see Feasibility).
- The coverage gaps go into `errored_files`, which the report shows in its table of skipped and errored files. When a stage records a second gap of a file, the second reason follows the first.
- The executive summary of the report says that a stage could not read or build the files with errors. It no longer gives an AI provider as the example cause: no AI call writes `errored_files`.
- The swallowed-failures ceiling of `src/devops_cli/ai/review/pipeline.py` goes from 19 to 9.
- `docs/SELF_IMPROVEMENT.md` says what the table of skipped and errored files holds.
- The report is observable, so the change has a spec delta: the new capability `review-coverage-gaps`.
- These handlers stay, because other open issues own them: lines 1809, 1862 and 2437 (#1907), lines 852 and 863 (#1429), line 200 (#1165). The `NonCallableMock` check in `_is_scannable_manifest` stays for #1328.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `review-coverage-gaps`: a review states each file that one of its stages could not read as a coverage gap, with the stage and the reason.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/pipeline.py`: `_try_reuse_cached_analysis_meta`, `_collect_scanner_commit_files`, `_read_cited_file` (new), `_admit_scanner_findings`, `_execute_pre_analysis_batch`, `_collect_paths_to_analyze`, `_read_failure` (new), `_record_coverage_gap` (new), `_collect_base_revision_fingerprints`, and the orchestrator's constructor, `run_pre_analysis_refresh`, `_run_static_scanners`, `_run_review_evidence`, `_fetch_threat_intel`, `_admit_advisory_finding` and `_assemble_single_file_payload`.
- `src/devops_cli/ai/review/stages/reporting.py`: the executive summary of a review with coverage gaps.
- `src/devops_cli/ai/analyze/scanner.py`: `_analyze_python_ast` catches `RecursionError` as well as `SyntaxError`.
- `docs/SELF_IMPROVEMENT.md`: the table of skipped and errored files.
- `tests/ai/review/test_coverage_gaps.py` (new) and `tests/ai/review/test_pre_analysis_scope.py`: the new tests.
- `tests/ai/review/test_pipeline.py`, `tests/test_review_pipeline.py` and `tests/test_review_worktree_regression.py`: the calls of the changed private functions.
- `tests/fixtures/swallowed_failures_ceilings.json`: the lower ceiling.

## Feasibility

- Code at base 22e5a166, where the eight handlers are at the lines that the issue gives for b170358e (274, 404, 558, 887, 922, 2082, 2563 and 2640): `uv run ruff check --select BLE001,S110,S112 src/devops_cli/ai/review/pipeline.py` gives 19 sites, and `tests/fixtures/swallowed_failures_ceilings.json` holds 19.
- A read-only probe on Python 3.14.7, in a temporary directory: `Path.read_text` of a file with mode 000 raises `PermissionError`, whose `strerror` is `Permission denied`, and `Path.is_file()` of that file is true. So a file passes the `is_file` checks of the pipeline and its read still fails.
- The same probe: `analyze_single_file` (with no AI client) and `extract_network_references` raised nothing for content that does not parse as Python, JSON, YAML or Go. `analyze_single_file` raised `RecursionError` ("Stack overflow during compilation") from `ast.parse` in `_analyze_python_ast` for a Python file of 50,000 or more chained `+ a` terms, about 100 KB. Its fallback for a `SyntaxError` covers this case too, so the fix is in `_analyze_python_ast`. After that fix, only the read can fail in those handlers, and `OSError` is the error to catch.
- The same probe: `find_repo_root` and `list_repo_files` (`src/devops_cli/core/repo.py`) raised nothing for a symbolic link loop or for a directory with no permissions. `list_repo_files` catches its own git and ignore-rule errors, and on Python 3.14 `Path.exists`, `Path.is_file` and `Path.rglob` give false or skip the entry. Both functions raise `ValueError` only for a path with a NUL character. For such a target, the constructor at base also raises `ValueError`, from `reviewed_tree` some lines later. So the handler at line 2082 changed nothing that a user sees, and the handler at line 404 caught nothing.
- The issue asks for a test where `list_repo_files` fails and a test where `find_repo_root` fails. Such a test must patch a `devops_cli` name, which docs/TESTING.md forbids, so this change has no such test. The two handlers are dead code, and docs/TESTING.md says to delete dead code.
- The four tests in `tests/ai/review/test_coverage_gaps.py` failed on the base code and pass after the change. For the three files that a stage cannot read, the report had no table of skipped and errored files. For the deep Python file, pre-analysis gave no metadata. The cache test in `tests/ai/review/test_pre_analysis_scope.py` passes on both: it keeps the narrower handler of the cache check from raising.

## Existing Tool Considered

The Python standard library covers the need: `OSError` and its `strerror`, and `functools.partial`. The report already has a table for coverage gaps (`errored_files`), so the change adds no new field and no new tool. The fallback for source that `ast` cannot parse already exists in `_analyze_python_ast`. The change deletes `_file_content`, `_read_content` and the handlers at lines 274, 404, 558, 887, 922, 2082, 2563 and 2640 of the base.
