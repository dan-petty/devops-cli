# Task: Bandit Runs on Reviews of More Than 50 Python Files, and a Failed Analyzer Says Why (#1009)

**Issue**: [#1009](https://github.com/dan-petty/devops-cli/issues/1009)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/security, scope/review

## Description
Every branch review of `release/v0.2.25` since session `20261002-163203` reported `! Failed during execution: Bandit`, and the report showed only `| Bandit | failed |`. Bandit 1.9 wraps its file list in `rich.progress.track` when it has more than 50 files (`PROGRESS_THRESHOLD` in `bandit/core/manager.py`) and logs at INFO, which draws a `Working... ━━━━ 100%` bar on stdout ahead of the JSON report. `_parse_json_or_ndjson` could not parse that, so `_handle_non_json_output` returned `failed`, and the exit code 1 that meant "issues found" read as a failure. Its reason quoted only stderr, Bandit's INFO log, and the review kept only each analyzer's state, so nothing said why.

- **Bandit asks for clean output** (`security/bandit.py`). `BanditScanner.build_command` passes `-q` in all three shapes: file list, single file and `-r <directory>`. `-q` sets Bandit's log level to WARN, which suppresses the bar and the INFO log, as the other two Bandit callers (`config/commands.py`, `ai/tools/builtin_tools.py`) already did. The JSON parser still does not skip leading noise, as the issue decided.
- **A non-JSON failure says so** (`security/base.py`). When a scanner exits non-zero and its stdout is non-empty but not JSON, `_non_json_failure_reason` gives `Scanner exited with code <n>; output was not JSON, starting "<start of stdout>"`, then `; stderr: <stderr>`. Whitespace runs, line breaks included, become one space; the quote is cut to `CONST_SCANNER_STDOUT_EXCERPT_CHARS` (100) and the whole reason to `CONST_SCANNER_FAILURE_REASON_CHARS` (300), each with `…`, so stderr keeps what fits after the quote. Empty stdout keeps the old `Scanner exited with code <n>: <stderr>` reason, and scanners with built-in patterns still fall back as before.
- **The reason reaches the report** (`ai/review/pipeline.py`). `_static_analyzer_reasons` takes the `reason` of each observed `ScanOutcome` whose analyzer's state is `failed`, and `_record_static_analyzers` keeps it in `ReviewPipelineOrchestrator.static_analyzer_reasons`, beside `static_analyzers`, whose state strings the profile, the executive summary and the review JSON read unchanged. `_build_static_analyzers_section` writes `failed: <reason>` in the Result cell, with whitespace folded and `|` escaped as `\|`. The console line from `_static_analyzer_summary` reads `! Failed during execution: Bandit (the report's Static Analyzers table says why)`; no other console output changed (#987 rewrites it).

## Acceptance Criteria
- [x] `BanditScanner.build_command` passes `-q` in all three command shapes. `tests/test_security_bandit.py::test_bandit_asks_for_quiet_output_in_every_command_shape` (red on 38517a8: `(False, False, False)`). No existing test pinned the exact argv. Run for real against Bandit 1.9.4 over 61 small files: the built command exits 1 with stdout starting `{\n  "errors": []`, and `BanditScanner().scan` returns `ran` with the B602 finding for both the file list and the directory; the same command without `-q` prints `Working... ━━━━━━━━ 100% 0:00:00` first.
- [x] `tests/test_security_bandit.py::test_bandit_reports_its_findings_over_more_than_fifty_files`, for a file list and a directory, drives `BanditScanner.scan` over 51 files in `tmp_path` through `_fake_bandit_1_9`, which prefixes the bar without `-q` past 50 files and exits 1 when it reports a result. The scan returns `ran`, no reason and the HIGH B602 finding, which real Bandit reports at the `-ll` level the scanner passes (a LOW issue would be dropped and the exit would be 0). Red on 38517a8: `('failed', 'Scanner exited with code 1: [main]\tINFO\tprofile include tests: None', [])` for both shapes.
- [x] A non-zero exit with non-JSON stdout fails with a reason that says the output was not JSON and quotes its start. `tests/test_consolidation_security_scanner_base.py::test_a_failed_scan_says_its_output_was_not_json_and_quotes_it` pins the whole reason (red: `Scanner exited with code 1: [main]\tINFO\tprofile include tests: None`), and `test_a_failed_scan_quotes_a_bounded_start_of_its_output` pins the bounds: 300 characters, a 100-character quote, and stderr cut to fit (red: no quote).
- [x] A failed analyzer's reason reaches the Static Analyzers table with pipes escaped, and the console line names the analyzer and points to the report. `tests/test_review_static_analyzers.py::test_the_report_says_why_an_analyzer_failed_and_the_console_points_there` pins the row `| Bandit | failed: Scanner exited with code 1; output was not JSON, starting "a \| b" next |` and the console line (red: `| Bandit | failed |`).
- [x] The new tests run no real scanner and no network: `run_subprocess` is patched with a fake or a `MagicMock`. Each call takes 0.01 s or less (`--durations=0`).
- [x] `changelog.d/1009.md` records the fix under `### Fixed`; `CHANGELOG.md` is not edited.
- [x] `ruff check`, `ruff format --check` and `mypy --strict` are clean on the touched modules, `uv run devops docs check` passes, and the full suite passes (`uv run pytest -p no:cacheprovider -q -n 6 tests`).
- Pending a person: `uv run devops ci` on this branch; it is this PR's own check, which readiness reads.
- Pending a person: `uv run devops ai review branch --persona devsecops release/v0.2.25` reports Bandit as ran.

## Measurements
The new tests, run with `uv run pytest -p no:cacheprovider -q -n 0 --durations=0` on this branch.

| Test | Call |
| :--- | ---: |
| `test_bandit_reports_its_findings_over_more_than_fifty_files` (file list, directory) | 0.01 s each |
| `test_the_report_says_why_an_analyzer_failed_and_the_console_points_there` | 0.01 s |
| `test_a_failed_scan_says_its_output_was_not_json_and_quotes_it` | 0.01 s |
| `test_a_failed_scan_quotes_a_bounded_start_of_its_output` | 0.01 s |
| `test_bandit_asks_for_quiet_output_in_every_command_shape` | < 0.01 s |
