# Task: Fail Closed on Review Thread Read Errors in PR Readiness (#797)

**Issue**: [#797](https://github.com/dan-petty/devops-cli/issues/797)
**Feasibility**: Verified against `src/devops_cli/commands/pr.py:1822-1830` and `src/devops_cli/commands/ai_runs.py:448-451,693-700`; confirmed `list_pr_review_threads` failures previously warned and continued with `unresolved = []`.

## Summary

- Updated `_evaluate_pr_blockers` in `src/devops_cli/commands/pr.py` so a `GitHubOperationError` raised while reading review threads appends a readiness blocker naming the error instead of warning and treating the PR as having zero unresolved threads.
- Added unit tests covering failed review-thread reads in `devops pr check-readiness` and verifying `devops ai runs check` exits `1` on an empty metric comparison and on an ambiguous run-ID prefix.

## Acceptance Criteria

- [x] A thread read that raises makes `pr check-readiness` exit `1` with a blocker naming the error (`tests/test_pr_cmd.py::TestPrCommands::test_check_readiness_fails_closed_when_review_threads_cannot_be_read`).
- [x] `ai runs check` exits `1` on an empty comparison and on an ambiguous prefix (`tests/test_run_comparison.py::test_cli_runs_check_fails_on_empty_comparison_and_ambiguous_prefix`).
