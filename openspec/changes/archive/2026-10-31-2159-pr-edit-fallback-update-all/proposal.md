# Change: CLI Tests for PR Edit REST Fallback and PR Update All

## Problem
Two execution paths in `devops pr` have no test coverage at the edge:
1. `_fallback_patch_pr`: When `gh pr edit` fails (for example on rate limits), `devops pr edit` falls back to REST `PATCH` calls for title, body, base, and milestone. No test verifies these requests or confirms that a failed milestone update fails the command.
2. `devops pr update --all`: The request plan for dry-run execution (`--dry-run` and `--dispatch-ci`) and the execution loop over open pull requests (sorting oldest first, skipping drafts, ignoring other authors, and printing empty state messages) lack dedicated CLI tests using standard test doubles.

## Proposed Change
Add CLI tests in `tests/commands/test_pr_update.py` and `tests/commands/test_pr_cmd.py` using the shared `cli` fixture and `process_fake`:
1. Verify `devops pr edit` triggers `_fallback_patch_pr` when `gh pr edit` fails, sending correct `PATCH` calls for title, body, base, and milestone. Test that a milestone `PATCH` failure causes command failure.
2. Verify `devops pr update --all --dry-run` generates the expected planned requests as a complete list, both with and without `--dispatch-ci`, making zero actual API mutations.
3. Verify `devops pr update --all` processes candidate pull requests oldest first, skips draft pull requests, and prints the expected message when no pull requests exist.
4. Ensure all tests avoid patching internal `devops_cli` symbols.

## Feasibility
Confirmed against `src/devops_cli/commands/pr.py` and `src/devops_cli/github/branch_update.py`:
- `_fallback_patch_pr` issues `gh api --method PATCH repos/{owner}/{repo}/pulls/{number}` followed by `gh api --method PATCH repos/{owner}/{repo}/issues/{number}` for milestone. Both subprocess calls route through `run_gh`, which `process_fake` intercepts cleanly.
- `_plan_update_all_prs` outputs deterministic `PlannedRequest` sequences verified by dry-run rendering.
- `_fetch_open_prs` invokes `gh pr list --state open --author @me`, and `sort_prs_oldest_first` orders the results.
- The `cli` fixture and `process_fake` are fully supported by `tests.support.bootstrap`.

## Existing Tool Considered
The project's built-in `process_fake` and `cli` fixtures cover subprocess interception and CLI execution testing without patching internal symbols or requiring third-party mocking libraries.
