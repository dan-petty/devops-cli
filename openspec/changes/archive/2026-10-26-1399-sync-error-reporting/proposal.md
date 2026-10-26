# Proposal

## Why

Issue #1399: `fetch_all` and `pull_tracking` in `src/devops_cli/git/operations.py` catch `GitCommandError` and silently pass.
Because of this defect, `devops repos sync` and `devops branches sync` print success when a fetch or pull operation fails.
Users then work on stale clones without receiving a failure notification.

## What Changes

- `fetch_all` catches `gitlib.GitCommandError` and raises `GitOperationError` naming the repository, remote, and git's masked reason.
- `pull_tracking` catches `gitlib.GitCommandError` and raises `GitOperationError` naming the repository, remote, and git's masked reason.
- Neither function swallows `gitlib.GitCommandError`.
- `devops repos sync` reports each failed repository with git's reason, finishes all remaining repositories, and exits non-zero if any repository failed.
- `devops branches sync` reports each failed repository with git's reason, finishes all remaining repositories, and exits non-zero if any repository failed.
- This change alters observable CLI failure reporting and exit codes when git operations fail.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `git-sync`: `fetch_all`, `pull_tracking`, `devops repos sync`, and `devops branches sync` fail closed and report git errors.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/git/operations.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/commands/branches.py`.
- Tests: `tests/test_git_operations.py`, `tests/test_repos.py`, `tests/test_branches.py`.
- Documentation: CLI command documentation.

## Feasibility

- Premise confirmed at commit `fc30f122` (`origin/main`).
- `src/devops_cli/git/operations.py:159-166` catches `gitlib.GitCommandError` and executes `pass`.
- `src/devops_cli/git/operations.py:169-178` catches `(gitlib.GitCommandError, IndexError)` and executes `pass`.
- `src/devops_cli/commands/branches.py:46-54` catches `(OSError, ValueError)` and returns exit code 0 on failure.
- `src/devops_cli/commands/repos.py:370-380` catches `Exception` and returns exit code 0 on failure.
- `src/devops_cli/security/sanitizer.py:269` provides `mask_secrets` to sanitize git output.
- `src/devops_cli/exceptions/git.py:28` provides `GitOperationError`.

## Existing Tool Considered

GitPython (`git`) and OpenSSH provide standard git operations.
`devops_cli.git.operations` wraps these tools to manage multi-repository workspaces.
No new third-party dependency is required.
Internal error suppression blocks (`except gitlib.GitCommandError: pass`) are replaced with fail-closed error propagation.
