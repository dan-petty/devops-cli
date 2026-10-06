# Task: PR Checks Fail-Closed Reader (#769)

**Issue**: [#769](https://github.com/dan-petty/devops-cli/issues/769)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/github

## Description
Prior to this change, retrieving check runs and commit status contexts for a pull request was written three times across `check_verdict.py`, `pr_monitor.py`, and `commands/pr.py`, with divergent error handling and omission of the combined commit status `state` when more than 30 contexts existed. In addition, when a commit had zero check runs and zero statuses, readiness previously passed rather than blocking until checks were reported.

This deliverable:
1. **Unifies Check & Status Retrieval**: Implements a single, fail-closed shared reader in `src/devops_cli/github/check_verdict.py` (`_fetch_checks_from_rest` and `fetch_pr_check_verdicts`) that fetches check runs and commit statuses together.
2. **Fail-Closed on Unread**: Any API error, empty response, or invalid JSON when reading check runs or commit statuses produces an `unread_reason` and fails closed with exit code 1 across `pr wait`, `pr_monitor`, and `check-readiness`.
3. **Pending Verdict on Zero Checks**: When a head commit has zero check runs and zero statuses (or `gh pr checks` returns an empty list), the shared reader synthesizes a pending verdict with name `'no checks reported'` and exit code 8, blocking merge readiness and waiting in monitor loops.
4. **Handles >30 Commit Contexts via Combined State**: Reads commit status contexts and inspects the aggregate `state` field when `total_count > len(statuses)`. If any context past page 1 failed or is pending, synthesizes `'commit status (combined)'` with the appropriate bucket to block or wait fail-closed across all consumers.
5. **Deduplicates Consumers**: Replaces duplicate retrieval logic in `src/devops_cli/commands/pr.py` and `src/devops_cli/github/pr_monitor.py` with calls to the shared reader while preserving the #707 `BUCKET_CLASSIFIER_MAP` table.

## Acceptance Criteria
- [x] One module (`devops_cli.github.check_verdict`) reads a pull request's checks and returns the fail-closed summary that `pr wait`, the monitor, and readiness consume.
- [x] A scripted read that returns zero runs and zero statuses yields a pending verdict naming 'no checks reported' in `pr wait`, monitor, and readiness alike.
- [x] The shared reader reads commit statuses and uses the combined `state` when total contexts exceed page 1. A scripted test covers a head with more than 30 contexts and one failing context past page 1, blocking in `pr wait`, monitor, and readiness.
- [x] A statuses read that cannot be read blocks and names the reason (`unread_reason`), the same way an unread check-runs read does.
- [x] The #707 classifier table and its parity tests remain unchanged.
- [x] Changelog fragment `changelog.d/769.md` is present.
- [x] `uv run devops ci` passes with 100% green status across all quality gates.

## Deliverables
- [x] `src/devops_cli/github/check_verdict.py` updated with unified check-runs and commit status retrieval, combined state handling, and zero-checks reporting.
- [x] `src/devops_cli/github/pr_monitor.py` updated to consume the unified reader and report unread check failures explicitly.
- [x] `src/devops_cli/commands/pr.py` updated to consume the unified reader in `_failing_check_runs` and eliminate duplicate fetch logic.
- [x] `tests/test_pr_check_verdict.py` updated with acceptance tests for zero checks, >30 combined status contexts, and status read failures.
- [x] `tests/test_github_pr_monitor.py` updated with acceptance tests for zero checks, combined status failure, and unread checks.
- [x] `tests/test_pr_check_runs.py` updated with acceptance tests for `_check_run_blockers` and `_failing_check_runs`.
- [x] `tests/test_pr_cmd.py` updated for table rendering of pending zero checks.
- [x] `changelog.d/769.md` changelog entry.
- [x] Task file `docs/agent/tasks/task-769-pr-checks-fail-closed.md`.
