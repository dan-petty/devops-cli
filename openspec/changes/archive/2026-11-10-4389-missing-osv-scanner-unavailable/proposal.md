# Change: missing osv-scanner records unavailable instead of failed

## Why

Issue #4389: When `osv-scanner` is missing on PATH, `OsvScanner.scan()` runs without preflight binary checks. It executes the missing binary, encounters an exit code of 127, and marks the scan status as `failed`. In SARIF generation, this failure causes the orchestrator run for `devops-cli` to set `executionSuccessful: false` and emit level `error` notifications. GitHub Code Scanning interprets `executionSuccessful: false` as an engine configuration failure and displays an overview configuration error.

## What Changes

- `OsvScanner.scan()` checks binary presence via `self._check_binary()` before command dispatch.
- When `osv-scanner` is not available on PATH, the scanner returns status `unavailable` with no findings.
- The SARIF orchestrator invocation preserves `executionSuccessful: true` when `osv-scanner` is missing.

This change fits in one pull request.

## Feasibility

Verified against the real system:
- Running `devops scan report --sarif .data/scan.sarif` on an environment without `osv-scanner` produced `Scanner 'osv-scanner' failed during execution: Scanner exited with code 127: Executable 'osv-scanner' not found in PATH` and set `executionSuccessful: false` in `.data/scan.sarif`.
- With binary preflight checking added to `OsvScanner.scan()`, running `devops scan report --sarif .data/scan.sarif` outputs `! Scanner 'osv-scanner' was not run (Binary 'osv-scanner' not found on PATH).` and produces `executionSuccessful: true` with warning notifications in `.data/scan.sarif`.

## Existing Tool Considered

All other security scanner adapters in `devops_cli.security` already use `_evaluate_preflight()` or `self._check_binary()` to return `unavailable` when their required binary is absent. `OsvScanner` was the only adapter overriding `scan()` without checking binary presence. No new external tool is needed. No internal code is deleted.
