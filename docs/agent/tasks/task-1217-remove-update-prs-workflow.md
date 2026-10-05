# Task: Remove Update PRs Workflow (#1217)

**Issue**: [#1217](https://github.com/dan-petty/devops-cli/issues/1217)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/ci

## Description
Removes the automated `update-prs.yml` GitHub Actions workflow that automatically merged base branches (`main`, `release/**`) into open pull requests on every push event. This automation caused excessive CI runs, required repeated manual workflow approvals, and interrupted active PR development. Merge conflicts and target-branch build failures will be handled manually when integrating.

## Acceptance Criteria
- [x] `.github/workflows/update-prs.yml` is removed.
- [x] GitHub Actions workflow is disabled immediately in repository settings.
- [x] `ACTIONS_WRITE_ALLOWLIST` in `tests/test_architectural_invariants.py` updated to empty set.
- [x] `tests/test_workflow_contracts.py` updated to assert `update-prs.yml` is absent and test expression isolation across remaining workflows.
- [x] All local quality gates in `uv run devops ci` pass with 100% green status.
- [x] Changelog fragment `changelog.d/1217.md` present.
- [x] Task file `docs/agent/tasks/task-1217-remove-update-prs-workflow.md` present.

## Deliverables
- [x] `.github/workflows/update-prs.yml` (removed)
- [x] `tests/test_architectural_invariants.py`
- [x] `tests/test_workflow_contracts.py`
- [x] `changelog.d/1217.md`
- [x] `docs/agent/tasks/task-1217-remove-update-prs-workflow.md`
