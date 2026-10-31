# Change: Test PR Edit REST Fallback and PR Update All Over Edge Fakes

## Why

Two code paths in `devops pr` have no test coverage over edge fakes:
1. `_fallback_patch_pr`: when `gh pr edit` fails, `devops pr edit` uses the GitHub REST API to set the title, body, base and milestone. Existing tests mock `devops_cli.commands.pr.run_gh` and omit milestone checks and error handling when a patch fails.
2. `devops pr update --all`: the dry-run request plan (`_plan_update_all_prs`) and batch update execution over candidate pull requests (`_fetch_open_prs`, `_process_candidate_pr_row`, `_update_all_prs`) lack end-to-end CLI tests exercising the command over edge fakes without internal monkeypatching.

## Feasibility

Confirmed against the real system:
- `src/devops_cli/commands/pr.py:766-809`: `_fallback_patch_pr` executes REST `PATCH` commands on `repos/{owner}/{repo}/pulls/{number}` and `repos/{owner}/{repo}/issues/{number}` (for milestone). When updated to return an error string upon failure, `edit_pr` reports the failure cleanly with `print_error` and exits with the command returncode.
- `src/devops_cli/commands/pr.py:858-866`: `edit_pr` catches `gh pr edit` failure, invokes `_fallback_patch_pr`, and exits on failure.
- `src/devops_cli/commands/pr.py:1724-1768`: `_update_all_prs` runs dry-run request rendering when `--dry-run` is passed, or fetches open pull requests via `_fetch_open_prs` and processes each candidate with `_process_candidate_pr_row`.
- `tests/support/fakes/process.py`: `process_fake` intercepts `gh` commands executed via `run_gh` and `run_subprocess`, allowing assertions on dispatched CLI arguments and return values without starting real processes.
- `tests/support/cli.py`: provides the `cli` test fixture to run commands through `devops_cli.main.app`.

## What Changes

1. In `src/devops_cli/commands/pr.py`:
   - Update `_fallback_patch_pr` to return `tuple[bool, str]`, returning the failure message if a pull request or milestone `PATCH` fails.
   - In `edit_pr`, when `_fallback_patch_pr` fails, print the error with `print_error` before exiting.
2. In `tests/commands/test_pr_update.py`:
   - Add CLI test for `devops pr edit` REST fallback: verify that when `gh pr edit` fails, `devops pr edit` sends `PATCH` requests for title, body, base, and milestone.
   - Add CLI test asserting that when milestone `PATCH` fails, `devops pr edit` fails with exit code 1 and outputs the error message.
   - Add CLI test for `devops pr update --all --dry-run` with and without `--dispatch-ci`, asserting the exact planned request list and verifying zero external process calls are executed.
   - Add CLI test for `devops pr update --all` over multiple pull requests: verifying that it updates active pull requests oldest first, skips drafts, filters non-matching authors via gh args, and reports the empty notice when no pull requests exist.
   - Remove internal mocks of `devops_cli` symbols in favor of `process_fake` and the `cli` fixture.
