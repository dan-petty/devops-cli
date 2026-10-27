# Spec Delta

## ADDED Requirements

### Requirement: A run reclaims the worktrees of merged work first
`devops repos worktrees add` SHALL remove each worktree that `devops repos worktrees prune --confirm` removes before it checks who holds the issue, and SHALL name each removed worktree with the size of its directory. The JSON report SHALL list them in `reclaimed`. `--no-reclaim` SHALL skip the step and read no pull request.

#### Scenario: A merged worktree is removed
- **WHEN** a clean, unlocked worktree has a tip that is the head of a merged pull request, and the user runs `add 2345 --type feat --slug next`
- **THEN** the directory of that worktree no longer exists and the output names it with its size
- **AND** the worktree `w-2345` is created

#### Scenario: A merged worktree no longer holds its issue
- **WHEN** the merged worktree has the branch `chore/2344-old`, and the user runs `add 2344 --type chore --slug again`
- **THEN** the old worktree is removed and `w-2344` is created

#### Scenario: Other worktrees stay
- **WHEN** a worktree is dirty, locked, or has a tip that no merged pull request heads
- **THEN** `add` keeps it

#### Scenario: Reclaim skipped
- **WHEN** the user runs `add 2344 --type chore --slug again --no-reclaim` and the merged worktree of issue 2344 exists
- **THEN** the command exits 1 and names that worktree as the holder
- **AND** GitHub receives no request

### Requirement: A failed reclaim does not stop the run
When the pull requests of the worktrees cannot be read, `add` SHALL say why once, remove nothing, and go on to create the worktree. The JSON report SHALL hold the reason in `reclaim_error`.

#### Scenario: GitHub answers an error
- **WHEN** GitHub answers HTTP 500 for the tip of a worktree, and the user runs `add 2345 --type feat --slug next`
- **THEN** the command exits 0, says that the merged worktrees were not reclaimed and why, and creates `w-2345`
- **AND** no worktree is removed

### Requirement: A dry run plans the reclaim
`add --dry-run` SHALL list the GitHub requests that the reclaim would make, SHALL make no request, and SHALL remove nothing.

#### Scenario: Dry run with a worktree to check
- **WHEN** a clean, unlocked worktree exists and the user runs `add 2345 --type feat --slug next --dry-run`
- **THEN** the output lists the request for the pull requests of its tip
- **AND** GitHub receives no request and the worktree still exists
