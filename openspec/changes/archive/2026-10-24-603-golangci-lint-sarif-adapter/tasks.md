# Tasks

## 1. Locked tool configuration and binary definitions

- [x] 1.1 Write tests verifying `golangci-lint` entry in `tools.lock` and `BIN_GOLANGCI_LINT` definition (`uv run devops ci test tests/test_tools_lock.py`).
- [x] 1.2 Add `[binary.golangci-lint]` to `src/devops_cli/tools_lock/tools.lock`, `BIN_GOLANGCI_LINT` to `src/devops_cli/config/commands.py`, and `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG` to `src/devops_cli/config/constants.py` (`uv run devops ci test tests/test_tools_lock.py`).
- [x] 1.3 Sync documentation with `uv run devops docs generate --sync-readme`.

## 2. GolangciLintScanner implementation and registry registration

- [x] 2.1 Write failing unit tests for `GolangciLintScanner` covering command building, default linters ordering, SARIF output parsing with `from_sarif`/`to_finding`, missing binary handling, and missing `go` handling (`uv run devops ci test tests/test_golangci_lint_scanner.py`).
- [x] 2.2 Implement `GolangciLintScanner` in `src/devops_cli/security/golangci_lint.py` and register it in `src/devops_cli/security/registry.py` (`uv run devops ci test tests/test_golangci_lint_scanner.py`).
- [x] 2.3 Sync documentation with `uv run devops docs generate --sync-readme`.

## 3. Review pipeline Go static analysis dispatch and base scan

- [x] 3.1 Write failing integration tests for review static analysis on Go files verifying module-level execution, finding filtering to reviewed files, `go.mod` base-scan preservation, and analyzer state recording (`uv run devops ci test tests/test_review_pipeline_go.py`).
- [x] 3.2 Add `go` kind to `_STATIC_ANALYZERS`, Go file classification to `_classify_scanner_files`, `.go` branch in `_run_static_scanners` with `_match_static_findings_to_files`, and `go.mod` base scan preservation in `src/devops_cli/ai/review/pipeline.py` (`uv run devops ci test tests/test_review_pipeline_go.py`).
- [x] 3.3 Sync documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Follow-up issue: Model-in-the-Loop Prompt Benchmarking and goroutine defect template for Go persona recommendations.
- Follow-up issue: clang-tidy integration with compile_commands.json.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
