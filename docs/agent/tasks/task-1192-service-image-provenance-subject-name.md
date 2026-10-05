# Task: Provide subject-name for Service Image Build Provenance Attestation in release.yml (#1192)

**Issue**: [#1192](https://github.com/dan-petty/devops-cli/issues/1192)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/ci

## Description
During the `v0.2.26` release workflow execution (`.github/workflows/release.yml`, run 37230134795, job `service-image`), the `Attest Build Provenance` step failed with `Error: subject-name must be provided when using subject-digest`.

`actions/attest-build-provenance@v2` requires `subject-name` when `subject-digest` is provided. The step in `release.yml` provided `subject-digest: ${{ steps.push.outputs.digest }}` but lacked `subject-name`.

This deliverable:
1. **Configures `subject-name`**: Adds `subject-name: ghcr.io/${{ github.repository }}/service` to the `Attest Build Provenance` step in `.github/workflows/release.yml`.
2. **Enforces Invariant via Workflow Contract Tests**: Adds contract tests in `tests/test_workflow_contracts.py` ensuring that every `actions/attest-build-provenance` step in workflow definitions provides `subject-name` when `subject-digest` is specified, along with mutation coverage.

## Acceptance Criteria
- [x] `subject-name: ghcr.io/${{ github.repository }}/service` is added to `Attest Build Provenance` in `.github/workflows/release.yml`.
- [x] `uv run actionlint .github/workflows/release.yml` passes with 0 errors.
- [x] Contract tests in `tests/test_workflow_contracts.py` verify that `actions/attest-build-provenance` steps require both `subject-name` and `subject-digest`.
- [x] Mutation tests verify that removing `subject-name` causes the workflow contract check to fail.
- [x] `uv run devops ci` passes with 100% green status across all quality gates.
- [x] Changelog fragment `changelog.d/1192.md` is present.
- Pending a person: Next release run of `release.yml` executes `Attest Build Provenance` in `service-image` job without `subject-name` failure.

## Deliverables
- [x] `.github/workflows/release.yml` updated with `subject-name`.
- [x] `tests/test_workflow_contracts.py` updated with contract and mutation tests.
- [x] Changelog fragment `changelog.d/1192.md`.
- [x] Task file `docs/agent/tasks/task-1192-service-image-provenance-subject-name.md`.
