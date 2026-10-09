# Task: CI's Trivy scans run the Trivy version tools.lock pins (#1499)

**Issue**: [#1499](https://github.com/dan-petty/devops-cli/issues/1499)
**Status**: Done
**Milestone**: v0.2.32
**Scope**: type/bug, scope/ci

## Description

- Both `aquasecurity/trivy-action` steps, the Service Image scan in `.github/workflows/ci.yml` and in `.github/workflows/release.yml`, now pass `version: v0.75.0` instead of `v0.70.0`, so CI scans with the Trivy `devops install-tools` installs.
- `tools.lock`'s `[binary.trivy].version` is the single source for Trivy's version: a workflow contract test fails whenever a `trivy-action` step's `version` differs from it, so a lock bump fails CI until the workflows match. The lock's header names the workflows in its bump procedure.

## Acceptance Criteria

- [x] Both `trivy-action` steps pass `version: v0.75.0` (`ci.yml`, `release.yml`).
- [x] `test_every_trivy_scan_runs_the_trivy_tools_lock_pins` in `tests/test_workflow_contracts.py` failed on the unfixed tree with v0.70.0 against 0.75.0, and passes now.
- Pending a person: the Service image scan with Trivy v0.75.0. An item PR into release/v0.2.32 does not run ci.yml's Service Image job (it needs `base_ref == main` or `workflow_dispatch`). Run:
  1. `gh workflow run ci.yml --ref fix/1499-ci-trivy-version-from-tools-lock`
  2. `gh run list --workflow ci.yml --branch fix/1499-ci-trivy-version-from-tools-lock --event workflow_dispatch --limit 1`
  3. `gh run watch <id>`

  In the Service Image job, the "Scan Service Image for Vulnerabilities" step must install Trivy v0.75.0 and pass. Once #1486 has removed the release-PR skip, the v0.2.32 release PR into main runs the same scan by itself.

## Deliverables

- [x] `.github/workflows/ci.yml` and `.github/workflows/release.yml`: the Service Image scan's `trivy-action` step passes `version: v0.75.0`.
- [x] `tests/test_workflow_contracts.py`: `test_every_trivy_scan_runs_the_trivy_tools_lock_pins`.
- [x] `src/devops_cli/tools_lock/tools.lock` header: Trivy's version is also the `version` of every `aquasecurity/trivy-action` step in `.github/workflows/`, and the bump procedure runs `tests/test_workflow_contracts.py`.
- [x] `changelog.d/1499.md` under `### Fixed`.
