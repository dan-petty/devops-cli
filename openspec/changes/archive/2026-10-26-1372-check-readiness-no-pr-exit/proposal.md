# Proposal

## Why

Issue #1372: Running `uv run devops pr check-readiness` with no number on a branch without an open pull request exits with a traceback.
The command calls `resolve_branch_pr_number` when no pull request number is supplied.
When no open pull request exists for the branch, `resolve_branch_pr_number` raises `GitHubOperationError`.
The `devops pr` command app does not configure `exit_on=GitHubOperationError`.
The exception escapes unhandled and prints a Rich traceback.
A missing pull request is an expected condition before opening a pull request.
The command must exit 1 with a one-line error message and no traceback.

## What Changes

- Configure `exit_on=GitHubOperationError` on `app` and `threads_app` in `src/devops_cli/commands/pr.py`.
- Remove redundant manual error handling in `_resolve_monitor_pr_number` so `monitor` also uses the exit seam.
- Add an offline test in `tests/test_pr_cmd.py` verifying that `check-readiness` exits 1 without a traceback when no pull request exists.
- Add an offline test in `tests/test_pr_cmd.py` verifying that `monitor` exits 1 without a traceback when no pull request exists.
- This change alters no behavior that a consumer observes outside restoring the intended clean error reporting for `pr` commands.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/pr.py`.
- Tests: `tests/test_pr_cmd.py`.

## Feasibility

- Premise confirmed at commit 6cf8ff0c and current `origin/main`.
- Command execution `uv run devops pr check-readiness` on branch `implement_issue_thirteen_seventy_two` reproduced the traceback:
  `GitHubOperationError: No open pull request found for branch 'implement_issue_thirteen_seventy_two'.`
- `OTelTyper` in `src/devops_cli/core/cli.py` supports the `exit_on` parameter.
- When `exit_on` is specified, `OTelTyper.command` wraps execution with `exit_on_error(self._exit_on)`.
- `exit_on_error` catches `GitHubOperationError`, calls `print_error(exc.message, safe=True)` and raises `typer.Exit(exc.exit_code)`.
- `src/devops_cli/commands/gh.py` already uses `exit_on=GitHubOperationError` for all its apps.
- Applying `exit_on=GitHubOperationError` to `app` in `src/devops_cli/commands/pr.py` catches `GitHubOperationError` cleanly.

## Existing Tool Considered

`OTelTyper` and `exit_on_error` in `src/devops_cli/core/cli.py` provide the domain error exit seam.
`src/devops_cli/commands/gh.py` already uses this pattern.
No external tool or library is required.
The change deletes the manual `try...except GitHubOperationError` block in `_resolve_monitor_pr_number`.
