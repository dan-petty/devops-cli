# Task: The Fail-to-Pass Check Runs Only on Pull Requests into a Release Branch (#1721)

**Issue**: [#1721](https://github.com/dan-petty/devops-cli/issues/1721)
**Scope**: scope/ci, scope/release
**Feasibility**: The v0.2.37 release pull request (#1720, `release/v0.2.37` into `main`, head f7aef65) failed its Fail-to-Pass Check in run 39425010929: the replay lays the release's `tests/` over main's `src/`, the release's `tests/support/bootstrap.py` imports `defines_fixture_or_hook`, which main's `src/devops_cli/core/test_selection.py` does not have, and pytest stopped with an INTERNALERROR, which since #1669 (#1718) fails the check for any pull request. `.github/workflows/fail-to-pass.yml` ran on pull requests into `main` and `release/**`. Item pull requests target the release branch; the only pull requests into `main` are release pull requests, whose items each passed the check against the release branch.

## Description

- `.github/workflows/fail-to-pass.yml` triggers on pull requests into `release/**` only, so the check does not run on the release pull request into main, where it can only fail or prove nothing. Nothing is added to the tool or the release pull request.
- `tests/test_workflow_contracts.py::test_workflow_contract_fail_to_pass` pins the trigger, and task-844's record of it is updated.

## Acceptance Criteria

- [x] Tests first: the workflow contract expects `branches: ["release/**"]`; it failed on the base with `['main', 'release/**'] != ['release/**']`.
- [x] `uv run devops ci` passes (pre-push hook).
- Pending a person: #1720 shows no Fail-to-Pass Check on its next head.

## Deliverables

- [x] `.github/workflows/fail-to-pass.yml`, `tests/test_workflow_contracts.py` and `docs/agent/tasks/task-844-fail-to-pass.md`.
- [x] `changelog.d/1721.md` and this task file.
