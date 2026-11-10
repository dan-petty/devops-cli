# Tasks

## 1. Tests First (TDD)

Reads: `tests/security/test_security_gitleaks.py`, `tests/security/test_review_tool_runs.py`. Changes: `tests/security/test_security_gitleaks.py`, `tests/security/test_review_tool_runs.py`.

- [x] 1.1 Update `test_run_gitleaks_scan_list_target_runs_binary_on_every_file` to `test_run_gitleaks_scan_list_target_runs_binary_once` in `tests/security/test_security_gitleaks.py`, asserting Gitleaks runs once for a list target and maps finding locations back to original files.
  - Verification: `$ uv run devops ci test tests/security/test_security_gitleaks.py` fails on base
- [x] 1.2 Add `test_review_starts_gitleaks_once_for_n_files` in `tests/security/test_security_gitleaks.py` using `tool_executor_fake` to assert that scanning N files executes Gitleaks once and finding locations contain reviewed file paths.
  - Verification: `$ uv run devops ci test tests/security/test_security_gitleaks.py` fails on base

## 2. Implementation

Reads: `src/devops_cli/security/gitleaks.py`, `src/devops_cli/security/tool_executor.py`, `src/devops_cli/ai/review/pipeline.py`. Changes: `src/devops_cli/security/gitleaks.py`, `src/devops_cli/security/tool_executor.py`, `src/devops_cli/ai/review/pipeline.py`.

- [x] 2.1 Update `src/devops_cli/security/tool_executor.py` so `_placeholders` maps `base` directory to `CONST_TOOL_TARGETS_PLACEHOLDER` when `request.cwd` is set.
  - Verification: `$ uv run devops ci test tests/security/test_review_tool_runs.py`
- [x] 2.2 Implement `isolated_targets`, `build_command`, and `parse_output` in `GitleaksScanner` (`src/devops_cli/security/gitleaks.py`). For list targets, run once over the scratch directory and map finding paths back to original reviewed files.
  - Verification: `$ uv run devops ci test tests/security/test_security_gitleaks.py`
- [x] 2.3 Update `run_gitleaks_scan` to accept `tree: Path | None = None` and pass it to `GitleaksScanner.scan`. Update `_scan_secrets` and `_call_scanner_helper` in `src/devops_cli/ai/review/pipeline.py` to pass `tree=tree`.
  - Verification: `$ uv run devops ci test tests/security/test_security_gitleaks.py tests/ai/review/test_pipeline.py`
- [x] 2.4 Update tests in `tests/security/test_review_tool_runs.py` that expected multiple Gitleaks runs from a single list target call.
  - Verification: `$ uv run devops ci test tests/security/test_review_tool_runs.py`

## 3. Performance Measurement and Verification

- [x] 3.1 Measure the static review stage on `src/devops_cli/security` to confirm execution time reduction.
  - Verification: `PATH="/home/vscode/.local/bin:$PATH" .venv/bin/devops review path src/devops_cli/security --static-scan-only`
- [x] 3.2 Run full CI gate checks.
  - Verification: `$ uv run devops ci`
