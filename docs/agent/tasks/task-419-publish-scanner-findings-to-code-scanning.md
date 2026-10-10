# Task 419: Publish Scanner Findings to Code Scanning

**Issue**: [#419](https://github.com/dan-petty/devops-cli/issues/419)
**Feasibility**: Verified that `devops scan report --sarif .data/scan.sarif` produces valid SARIF 2.1.0 with per-scanner runs and stable fingerprints, and github/codeql-action/upload-sarif publishes under /devops-scan category with security-events: write permission.
**Status**: Done
**Milestone**: `v0.2.33`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

`devops scan` already normalizes Trivy, Gitleaks, Semgrep, Checkov and Kubeconform output and writes SARIF 2.1.0 (`src/devops_cli/security/sarif.py:write_sarif`, called from `commands/scan.py`). This work adds the publication step: uploading the scan SARIF from CI under its own category (`/devops-scan`) so each scanner's alerts are attributed, de-duplicated across runs, and visible on pull requests.

## 2. Key Changes
- **CI Workflow** (`.github/workflows/ci.yml`): Added `security-events: write` permission to the `static` job, an unconditional `Security Scan` step running `uv run devops scan report --sarif .data/scan.sarif`, and an unconditional `Upload Security Scan SARIF` step using `github/codeql-action/upload-sarif` under category `/devops-scan`.
- **Workflow Parity** (`tests/test_ci.py`): Allowlisted `Security Scan` step in `_validate_ci_workflow_parity` and added `test_ci_workflow_publishes_scanner_sarif_to_code_scanning` to verify permissions, category, and unconditional execution.
- **Changelog**: Added changelog fragment `changelog.d/419.md`.
- **Amended 2026-10-10 (owner decision)**: The upload's Bandit results are what `devops ci security` fails on. Before, the upload scanned `tests/` and ignored `# nosec` markers while the gate scanned `src/` alone, so the release pull request showed Bandit alerts the gate never ran. Both now read `.bandit`, which names `src` and `tests`, at medium severity and above, honouring the tree's `# nosec` markers, and the tests' Medium and High findings are fixed. `devops scan report` reads a tree's `.bandit` only when it names its targets, and passes `-r` as the gate does; any other tree is scanned whole, ignoring `# nosec`, as before. `tests/test_security_bandit.py::test_the_scan_report_runs_bandit_on_this_repository_as_the_gate_does` holds them together.

## 3. Acceptance Criteria
- [x] **Category parameter**: The CI workflow uploads SARIF with category `/devops-scan` distinct from CodeQL categories, with `security-events: write` permission.
- [x] **Unconditional upload**: Upload step runs unconditionally (`if: always()`), resolving alerts when zero findings remain.
- [x] **Fingerprint stability**: Finding fingerprints exclude line numbers, preserving stability across code shifts.
- [x] **Scanner attribution**: SARIF document attributes findings to respective driver tools across runs.
- [x] **Workflow tests**: Verified through `test_ci_workflow_publishes_scanner_sarif_to_code_scanning` and `test_ci_workflow_parity_with_check_table`.
- Pending a person: `uv run devops ci` on the delivering tree, which the orchestrating session runs.
