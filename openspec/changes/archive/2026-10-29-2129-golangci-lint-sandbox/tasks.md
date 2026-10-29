# Tasks

## 1. golangci-lint gets the Go toolchain, the module cache and its caches, and no network

- [x] 1.1 Write `test_a_scan_gets_the_go_toolchain_and_the_module_cache_read_only_and_no_network` and `test_a_host_whose_go_env_fails_gives_a_failed_scan` in `tests/test_golangci_lint_scanner.py`, and move `test_golangci_lint_typecheck_failure_records_failed` onto the process fake and `ToolExecutorFake`. Verify that `uv run devops ci test tests/test_golangci_lint_scanner.py` fails on the base: the scanner starts no `go env`, and its request names no Go directory
- [x] 1.2 Add `GoToolchain`, `host_go_toolchain`, and the `data_dirs`, `cache_dirs` and `tool_env` of `GolangciLintScanner` in `src/devops_cli/security/golangci_lint.py`; the hook `tool_env` of `BaseSecurityScanner`, its variables in the request of `_run_tool`, and `tree_cache_dir` in `src/devops_cli/security/base.py`, which the Ruff cache of `src/devops_cli/security/ruff.py` now uses in place of `_ruff_cache_dir`; and the Go constants in `src/devops_cli/config/constants.py`. Verify that `uv run devops ci test tests/test_golangci_lint_scanner.py tests/test_scanner_tool_executor.py` passes, with the Ruff cache test

## 2. A Go module whose modules are not in the module cache is a coverage gap

- [x] 2.1 Write `test_a_module_whose_modules_are_not_in_the_cache_is_a_coverage_gap` in `tests/test_golangci_lint_scanner.py`. Verify that `uv run devops ci test tests/test_golangci_lint_scanner.py` fails on the base: the scan fails
- [x] 2.2 Add the hook `coverage_gap` of `BaseSecurityScanner`, which `_outcome_of` reads before the output of the tool, and `GolangciLintScanner.coverage_gap`. A coverage gap settles its run as a success (#2100). Verify that `uv run devops ci test tests/test_golangci_lint_scanner.py tests/test_scanner_tool_executor.py tests/test_scanner_contract.py` passes

## 3. Documents

- [x] 3.1 Describe the Go toolchain, the module cache, the Go caches and `GOPROXY=off` of golangci-lint in item 7 of `SECURITY.md` and in the module docstring of `src/devops_cli/security/tool_executor.py`. Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: on a host with the Go toolchain, bubblewrap and golangci-lint 1.64.6, run `go mod download` in a small Go module that requires one module and holds one `errcheck` finding, then run `devops review path` on it, and confirm that golangci-lint gives the finding. Then point `GOMODCACHE` at an empty directory, review again, and confirm the coverage gap. The host of this change has no Go toolchain.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
