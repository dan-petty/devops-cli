# Tasks

## 1. Behavior

- [x] 1.1 Update `tests/security/test_golangci_lint_scanner.py` with failing tests for v2 flags, v2 config keys, v2.15.0 SARIF parsing, and live `golangci-lint config verify`
  - Verification: `$ uv run pytest -n 0 tests/security/test_golangci_lint_scanner.py`
- [x] 1.2 Update `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG` (`src/devops_cli/config/constants.py`) and `GolangciLintScanner.build_command` (`src/devops_cli/security/golangci_lint.py`) for v2
  - Verification: `$ uv run pytest -n 0 tests/security/test_golangci_lint_scanner.py tests/security/test_review_pipeline_go.py`

## 2. Verification

- [x] 2.1 Run `devops ci --check --skip test --force` and `devops ci fail-to-pass --base origin/main`, and archive OpenSpec
  - Verification: `$ uv run devops ci --check --skip test --force && uv run devops ci fail-to-pass --base origin/main`
