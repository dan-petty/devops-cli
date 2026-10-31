# Design: Test PR Edit REST Fallback and PR Update All Over Edge Fakes

## Context

`devops pr edit` and `devops pr update --all` contain branches for REST API fallback and batch processing that lacked test coverage over edge fakes. Testing these paths over `process_fake` ensures no coupling to internals and validates real CLI behavior.

## Changes

### 1. `_fallback_patch_pr` error propagation
`_fallback_patch_pr` will return a tuple `(bool, str)`. When a `PATCH` request fails (for either the pull request fields or the issue milestone), the stderr or stdout of the failed command is returned. `edit_pr` sanitizes and prints this message using `print_error` before exiting with the non-zero status code.

### 2. CLI Tests in `tests/commands/test_pr_update.py`
The tests use `process_fake` to simulate GitHub CLI execution:
- `test_pr_edit_fallback_success`: Simulates `gh pr edit` returning code 1, followed by successful REST `PATCH` calls to `pulls/{number}` and `issues/{number}`. Verifies the sent argument lists for `--title`, `--body`, `--base`, and `--milestone`.
- `test_pr_edit_fallback_milestone_failure`: Simulates `gh pr edit` failure, successful pull request `PATCH`, and failed milestone `PATCH`. Asserts non-zero exit code and presence of the error message in command output.
- `test_pr_update_all_dry_run_plan`: Runs `devops pr update --all --dry-run` both with and without `--dispatch-ci`. Asserts that the rendered plan matches `plan_update_all_prs` and that `process_fake.calls` is empty.
- `test_pr_update_all_batch_execution`: Simulates `gh pr list --state open --author @me ...` returning multiple pull requests (older, newer, and draft). Asserts that pull requests are processed in oldest-first order, that drafts are skipped, and that the summary table reflects these states.
- `test_pr_update_all_empty`: Simulates `gh pr list` returning an empty list, asserting output contains "No open pull requests found to update."
