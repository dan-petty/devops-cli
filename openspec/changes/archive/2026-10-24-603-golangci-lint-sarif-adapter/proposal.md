# Proposal

## Why

Issue #603: The review static analysis stage and the security registry do not support Go files. Files ending in `.go` receive only generic scanner checks (such as Semgrep default rules) instead of language-specific static inspection. We integrate `golangci-lint` with SARIF output conversion to provide Go linting across review and scan workflows.

## What Changes

- Add `GolangciLintScanner` to `src/devops_cli/security/golangci_lint.py` and register it in `src/devops_cli/security/registry.py`.
- Configure `GolangciLintScanner` to emit SARIF and convert results into `Finding` models using `from_sarif` and `to_finding`.
- Set default linters to `errcheck`, `govet` (with `lostcancel`), and `staticcheck`, with `contextcheck` as opt-in.
- Add `BIN_GOLANGCI_LINT` to `src/devops_cli/config/commands.py` and export it in `src/devops_cli/config/__init__.py`.
- Pin `golangci-lint` v1.64.6 with multi-platform archive digests in `src/devops_cli/tools_lock/tools.lock`.
- Add `go` kind and `golangci-lint` entry to `_STATIC_ANALYZERS` in `src/devops_cli/ai/review/pipeline.py`.
- Add Go file classification in `_classify_scanner_files` and a `.go` branch in `_run_static_scanners` that runs once per nearest `go.mod` root and filters findings to reviewed files via `_match_static_findings_to_files`.
- Populate `go.mod` in `_write_base_revision_lockfiles` for base revision scanning.
- Missing `golangci-lint` binary, missing `go` compiler on PATH, or package-load/typecheck failures record appropriate non-zero analyzer states (`not installed` or `failed`) rather than zero findings.

This change adds observable Go static analysis to `devops review` and `devops scan report`, which carries a spec delta (`review-stages`).

This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-stages`: Add requirements for Go file static analysis with `golangci-lint`.

## Impact

- `src/devops_cli/config/commands.py`: Declare `BIN_GOLANGCI_LINT`.
- `src/devops_cli/config/constants.py`: Add `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG`.
- `src/devops_cli/tools_lock/tools.lock`: Add `[binary.golangci-lint]` entry.
- `src/devops_cli/security/golangci_lint.py`: Implement `GolangciLintScanner`.
- `src/devops_cli/security/registry.py`: Register `GolangciLintScanner`.
- `src/devops_cli/ai/review/pipeline.py`: Add `go` bucket, `golangci-lint` analyzer row, and module-level Go scanning.
- Tests in `tests/test_golangci_lint_scanner.py` and `tests/test_tools_lock.py`.

## Feasibility

I confirmed the premise against the real system:

- Checked `src/devops_cli/ai/review/pipeline.py`: `_STATIC_ANALYZERS` contains 7 scanners with no Go entry; `ScannerFileBuckets` lacks Go classification.
- Checked `src/devops_cli/security/registry.py`: 13 default scanners are registered with no Go scanner.
- Checked `src/devops_cli/security/sarif.py` and `src/devops_cli/security/normalization.py`: `from_sarif` and `to_finding` parse SARIF documents into normalized `Finding` objects.
- Upstream GitHub releases for `golangci/golangci-lint` confirm version v1.64.6 publishes verified checksums for linux-amd64, linux-arm64, darwin-amd64, and darwin-arm64.
- `golangci-lint run --out-format sarif` outputs standard SARIF JSON compatible with `from_sarif`.

## Existing Tool Considered

We adopt `golangci-lint`, an open-source and standard Go linter aggregator. Using `golangci-lint` avoids developing and maintaining custom AST parsing and lint rules for Go in DevOps CLI. Custom heuristics such as the vibes leak sentinel are not ported. No existing internal Go linting code is deleted because none existed.
