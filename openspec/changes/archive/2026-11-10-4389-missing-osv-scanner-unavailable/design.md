# Design: missing osv-scanner records unavailable instead of failed

## Context

`BaseSecurityScanner` provides `_evaluate_preflight()`, which inspects `_check_binary()` and produces a `ScanOutcome("unavailable", [], "Binary '<name>' not found on PATH")` when a required executable is absent.

`OsvScanner` overrides `scan()` to resolve lockfiles and detect coverage gaps. Because `OsvScanner.scan()` previously bypassed `_check_binary()`, any environment without `osv-scanner` suffered a subprocess launch failure (exit code 127). The scanner mapped this execution error to status `failed`, which propagated to SARIF orchestrator metadata as `executionSuccessful: false`.

## Design Decisions

- **Preflight check**: Insert `if not self._check_binary():` inside `OsvScanner.scan()` after lockfile resolution. If lockfiles exist but `osv-scanner` is missing, return `ScanOutcome("unavailable", [], f"Binary '{self.binary_name}' not found on PATH")`.
- **SARIF outcome**: Status `unavailable` maps to SARIF level `warning` instead of `error`. Because no outcome is `failed`, `_orchestrator_invocation` sets `executionSuccessful: true`.

## Rejected Alternatives

- **Install osv-scanner in all CI workflows**: Rejected. Not all environments or runners require vulnerability scanning of lockfiles during fast checks. Missing tools must cleanly report `unavailable` rather than crashing the orchestrator.
- **Always set executionSuccessful to True in SARIF**: Rejected. A genuine execution failure from a configured and installed scanner should continue to report `executionSuccessful: false`. The defect was false failure reporting for missing executables.
