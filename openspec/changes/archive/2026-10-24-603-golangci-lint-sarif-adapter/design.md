# Design

## Context

See proposal.md - Why. DevOps CLI review pipeline dispatches static analyzers by file suffix in `_run_static_scanners`. Go files currently bypass language-specific analysis. `golangci-lint` provides multi-linter static analysis with native SARIF output.

## Goals / Non-Goals

**Goals:**
- Provide `GolangciLintScanner` in the security scanner registry with default linters (`errcheck`, `govet` with `lostcancel`, `staticcheck`) and optional `contextcheck`.
- Parse `golangci-lint` SARIF output with existing `from_sarif` and `to_finding` converters.
- Execute `golangci-lint` once per nearest `go.mod` module root.
- Filter module-level findings to reviewed files using `_match_static_findings_to_files`.
- Support base-revision scanning by ensuring `go.mod` files are copied alongside Go files.
- Accurately record `not installed` when the binary is absent and `failed` when `go` is missing or package loading fails.
- Pin `golangci-lint` v1.64.6 in `tools.lock`.

**Non-Goals:**
- Porting vibes custom goroutine leak sentinel or `cpp_lifetime_sentinel.py`.
- Adding Go persona additions or review prompt benchmarking (deferred to follow-up).
- Rerouting the review pipeline through the security registry.

## Decisions

### Decision 1: Use `golangci-lint` SARIF output with existing SARIF ingestion
- **Rationale**: `golangci-lint` supports `--out-format sarif` natively. Converting through `from_sarif` and `to_finding` avoids custom output parsing.
- **Rejected alternative**: Parsing `golangci-lint` JSON or plain-text output. Rejected because SARIF standardizes rule IDs, file locations, and descriptions across security scanners.

### Decision 2: Run per nearest `go.mod` module root
- **Rationale**: Go tools require package context from `go.mod` and cannot compile isolated single files without their package definitions.
- **Rejected alternative**: Running `golangci-lint` per file. Rejected because Go linters fail when individual files are invoked without module context.

### Decision 3: Filter findings via `_match_static_findings_to_files`
- **Rationale**: Running across the Go module produces findings for files outside the review scope. `_match_static_findings_to_files` restricts results to reviewed files.
- **Rejected alternative**: Unconditionally accepting all module findings. Rejected because it would flood branch and pull request reviews with legacy findings.

### Decision 4: Reject custom goroutine leak heuristics
- **Rationale**: Vibes classifier gave false confidence (clean on leaked goroutines) and is uncalibrated.
- **Rejected alternative**: Porting `go_leak_sentinel.py`. Rejected because upstream documentation and survey recommend `uber-go/goleak` and standard Go analyzers instead of ad-hoc regex classifiers.

## Risks / Trade-offs

- [Go toolchain required on host for module typechecking] → Detect missing `go` binary and report analyzer state as `failed` with descriptive reason instead of reporting zero findings.
- [External dependencies required during linting] → If modules cannot resolve, `golangci-lint` exits non-zero and marks the scanner outcome as `failed`.
