# Proposal: #5072

## Why
`ghcr.io/dan-petty/devtools:1.1.12` (the devcontainer and runner base image) ships `golangci-lint` 2.15.0, which refuses the v1 CLI flags (`--out-format sarif`, `--disable-all`) in `GolangciLintScanner.build_command` and the v1 config keys (`disable-all`, `linters-settings`) in `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG`.

## What Changes
- Update `GolangciLintScanner.build_command` in `src/devops_cli/security/golangci_lint.py` to pass `--output.sarif.path=stdout` and `--default=none` (before `--enable <linter>` flags) instead of `--out-format sarif` and `--disable-all`.
- Update `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG` in `src/devops_cli/config/constants.py` to v2 YAML (`version: "2"`, `linters.default: none`, `linters.settings.govet.enable: [lostcancel]`) without `disable-all`, `linters-settings`, or `linters.enable`.
- Update `tests/security/test_golangci_lint_scanner.py` to assert v2 flags, v2 config shape, v2.15.0 SARIF parsing, and live `golangci-lint config verify -c` verification.

## Capabilities
- `review-golangci-lint`: configure and run `golangci-lint` v2 cleanly with the devtools binary.

## Impact
`GolangciLintScanner` emits valid `golangci-lint` v2 commands and configuration accepted by `golangci-lint` 2.15.0. Live Go scanning waits on `#7091` where `go` is present.

## Feasibility
Confirmed against `golangci-lint --version` (`2.15.0`), `golangci-lint migrate`, `golangci-lint run --help`, `golangci-lint config verify`, `src/devops_cli/security/golangci_lint.py:216-238`, and `src/devops_cli/config/constants.py:691-702`.

## Existing Tool Considered
Uses the existing `golangci/golangci-lint` 2.15.0 binary (`devtools:1.1.12`) directly with `migrate` and `config verify`; adds no new tool or library code.
