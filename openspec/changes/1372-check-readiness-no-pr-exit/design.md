# Design

## Context

`devops pr check-readiness` validates pull request merge readiness.
When the user does not pass a pull request number, the command resolves the pull request from the current git branch.
If no pull request exists for the branch, `resolve_branch_pr_number` raises `GitHubOperationError`.
In `src/devops_cli/commands/pr.py`, `app = new_typer(...)` does not declare `exit_on=GitHubOperationError`.
The exception bubbles up out of the Typer command wrapper and outputs a full traceback.
In contrast, `src/devops_cli/commands/gh.py` declares `exit_on=GitHubOperationError` on its Typer applications.
`_resolve_monitor_pr_number` in `src/devops_cli/commands/pr.py` used a manual try-except block to catch `GitHubOperationError` and exit.

## Goals

- Report `GitHubOperationError` in `devops pr check-readiness` as a clean one-line error with exit code 1.
- Ensure no traceback is displayed to the user when a branch has no open pull request.
- Unify `pr` commands under the standard `exit_on=GitHubOperationError` seam provided by `OTelTyper`.
- Remove redundant manual exception catching in `_resolve_monitor_pr_number`.

## Decisions

1. Pass `exit_on=GitHubOperationError` to `new_typer` when creating `app` and `threads_app` in `src/devops_cli/commands/pr.py`.
   This routes any unhandled `GitHubOperationError` in `pr` commands through `exit_on_error`.
   `exit_on_error` prints `exc.message` with `print_error` and exits with `exc.exit_code` (1).

2. Simplify `_resolve_monitor_pr_number` by removing the manual `try...except GitHubOperationError` block.
   Because `app` handles `GitHubOperationError` through `exit_on`, `monitor` uses the same seam as `check-readiness`.

## Rejected Alternatives

- Catching `GitHubOperationError` inside `_resolve_readiness_target`:
  Rejected because manual error handling duplicates logic across commands. Issue #1006 targets consolidating exception exits into the command seam.
- Catching `GitHubOperationError` inside `resolve_branch_pr_number`:
  Rejected because `resolve_branch_pr_number` is a domain function used by multiple callers that expect an exception on failure.
