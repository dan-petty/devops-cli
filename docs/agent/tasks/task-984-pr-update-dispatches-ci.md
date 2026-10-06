# Task: PR Update Dispatches CI Workflow (#984)

**Issue**: [#984](https://github.com/dan-petty/devops-cli/issues/984)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/ci

## Description
When `devops pr update` updates pull requests with base branch changes, CI workflows do not automatically trigger for GitHub Actions pull requests updated by actions tokens. Issue #984 adds a `--dispatch-ci` flag to `devops pr update` that polls the PR head commit SHA until it updates, and then triggers `ci.yml` via GitHub Actions workflow dispatch.

Furthermore, following the principle of least privilege, `actions: write` permission is strictly isolated: only `update-pull-requests` in `.github/workflows/update-prs.yml` holds `actions: write` permission, and architectural invariants verify that no other workflow carries this permission.

This deliverable:
1. **Adds `--dispatch-ci` flag**: Adds the `--dispatch-ci` option to `devops pr update` and `devops pr update --all`.
2. **Polls Head Branch SHA**: Bounded polling up to `DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS` (6) times at `DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS` (5.0s) intervals until the head SHA updates.
3. **Dispatches `ci.yml`**: Uses GitHub REST API (`repos/{owner}/{repo}/actions/workflows/ci.yml/dispatches`) with `ref: head_ref`.
4. **Handles Forks & Invariants**: Excludes forks with an informative skip message and exit code 0; fails with exit code 1 if head SHA does not change or dispatch fails.
5. **Dry-Run Planning**: Implements dry-run request planning with `PlannedRequest` and `render_request_plan` without external network calls.
6. **Workflow & Architectural Invariants**: Adds `actions: write` to `update-prs.yml`, adds `--dispatch-ci` to all 4 update invocations in `update-prs.yml`, and adds strict architectural allowlist invariants in `tests/test_architectural_invariants.py`.

## Acceptance Criteria
- [x] `--dispatch-ci` flag added to `devops pr update` CLI options and help text.
- [x] PR update polls head commit SHA up to configured attempts before dispatching `ci.yml`.
- [x] Fork head branches are excluded with informative message and exit code 0.
- [x] Dry-run renders request plan without making remote GitHub requests.
- [x] All 4 update commands in `.github/workflows/update-prs.yml` include `--dispatch-ci`.
- [x] `update-prs.yml` holds `actions: write` permission for `update-pull-requests`.
- [x] Architectural invariant enforces that only `update-prs.yml` holds `actions: write` and `ci.yml` admits `workflow_dispatch`.
- [x] Unit and workflow contract tests pass with 100% test coverage.
- [x] Changelog fragment `changelog.d/984.md` is present.
- [x] `uv run devops ci` passes with 100% green status across all quality gates.
- Pending a person: Merged workflow execution in `.github/workflows/update-prs.yml` triggers `ci.yml` on updated pull requests.

## Deliverables
- [x] `src/devops_cli/commands/pr.py` updated with `--dispatch-ci` and dry-run request planning.
- [x] `src/devops_cli/config/constants.py` updated with `CONST_CI_WORKFLOW_FILE`.
- [x] `src/devops_cli/config/defaults.py` updated with poll attempts and interval defaults.
- [x] `src/devops_cli/lang/en/help.py` and `messages.py` updated with user-facing messages.
- [x] `.github/workflows/update-prs.yml` updated with `actions: write` and `--dispatch-ci`.
- [x] `tests/test_architectural_invariants.py` updated with actions write permission invariant.
- [x] `tests/test_workflow_contracts.py` updated with workflow permission contract tests.
- [x] `tests/test_pr_update.py` updated with tests for `--dispatch-ci`, polling, and dry-run planning.
- [x] `changelog.d/984.md` changelog fragment.
- [x] Task file `docs/agent/tasks/task-984-pr-update-dispatches-ci.md`.
