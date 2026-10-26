# Design

## Context

See proposal.md - Why.
`src/devops_cli/git/operations.py` contains `fetch_all` and `pull_tracking`.
Both functions currently catch `GitCommandError` and execute `pass`.
`src/devops_cli/commands/repos.py` and `src/devops_cli/commands/branches.py` call these operations.
Both command suites print errors to the console but exit with return code 0 when operations fail.

## Goals / Non-Goals

**Goals:**
- Raise typed `GitOperationError` on `fetch_all` and `pull_tracking` failures.
- Populate `operation`, `repository`, and `remote` in exception details and message.
- Sanitize git standard error with `mask_secrets`.
- Ensure `repos sync` and `branches sync` continue processing all workspace repositories.
- Exit non-zero (exit code 1) from `repos sync` and `branches sync` when any repository fails.

**Non-Goals:**
- Change interactive command prompt behavior.
- Add automatic git merge conflict resolution.
- Modify repository cloning or branch creation workflows.

## Decisions

### Decision 1: Shape `GitOperationError` to match #900 and #1114 conventions
- *Rationale*: Precedent from `create_branch` (#900) and `clone_repo` (#1114) sanitizes git stderr with `mask_secrets` and attaches structured operation details. Raising `GitOperationError(f"fetch failed for '{repo_dir}' remote '{remote.name}': {reason}", operation="fetch", details={"repository": str(repo_dir)[:CONST_MAX_ERROR_DETAIL_LENGTH], "remote": str(remote.name)[:CONST_MAX_ERROR_DETAIL_LENGTH]})` satisfies both the message naming requirement and structured details.
- *Alternatives considered*: Raise raw `gitlib.GitCommandError`. Rejected because `devops-cli` requires strongly typed domain exceptions inheriting from `DevOpsCLIError`.
- *Alternatives considered*: Only populate `details` without repository and remote in the message string. Rejected because CLI loggers and command error handlers print exception string representations.

### Decision 2: Record failures per repository and exit non-zero after completion
- *Rationale*: Workspace commands must process all configured repositories so partial connectivity failures do not prevent updating other healthy repositories. A boolean flag tracks whether any repository encountered a failure during iteration. If the flag is set, the command raises `typer.Exit(1)` after iteration finishes.
- *Alternatives considered*: Exit immediately on the first failure (`fail-fast`). Rejected because users need all independent repository updates completed in one command run.
- *Alternatives considered*: Return zero exit code and only print warnings. Rejected by issue acceptance criteria and repository fail-closed invariants.

## Risks / Trade-offs

- [Scripts expecting exit code 0 when remotes are offline will fail] → Intentional behavior. Callers must handle non-zero exit codes when repositories fail to synchronize.
- [Long running sync across many broken repositories] → Iteration continues sequentially. Tests verify individual phases remain under 1 second using local bare repositories.
