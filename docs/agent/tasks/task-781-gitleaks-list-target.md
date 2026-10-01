# Task: Gitleaks Scans Every File of a List Target Again (#781)

**Issue**: [#781](https://github.com/dan-petty/devops-cli/issues/781)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/security

## Description
Gitleaks takes one source per run, and `GitleaksScanner.build_command` always passed only `target_path[0]`, so a list target scanned only its first file when the binary was installed. 5d34541 (#763) did the same to the built-in patterns. The review pipeline passes every reviewed file, so a review scanned only its first file for secrets.

## Acceptance Criteria
- [x] `GitleaksScanner.scan` runs once per file of a list target and merges the outcomes: every finding is kept and the status is the worst any file had.
- [x] `run_gitleaks_scan` passes a list target whole, dropping test files first when `ignore_tests` is set.
- [x] Tests cover a two-file list target with the secret only in the second file, through the binary and through the built-in patterns.

## Deliverables
- [x] `src/devops_cli/security/gitleaks.py`
- [x] `tests/test_security_gitleaks.py`
- [x] `CHANGELOG.md`
- [x] `docs/ROADMAP.md`

## Verification
- `uv run pytest tests/test_security_gitleaks.py`: 10 passed; both new tests failed before the fix.
- `uv run pytest` over the 16 test files that touch Gitleaks or `ScanOutcome`: 242 passed.
