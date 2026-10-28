# Spec Delta

## MODIFIED Requirements

### Requirement: A run reclaims the worktrees of merged work first
`devops repos worktrees add` SHALL remove each worktree that `devops repos worktrees prune --confirm` removes before it checks who holds the issue, and SHALL name each removed worktree with the size of its directory. The JSON report SHALL list them in `reclaimed`. A worktree that a run in parallel already removed is not a failed reclaim: the run SHALL report it as removed and say nothing of a failed reclaim. `--no-reclaim` SHALL skip the step and read no pull request.

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

#### Scenario: A run in parallel removes a worktree first
- **WHEN** a run in parallel removes a merged worktree before `add` removes it, so `git worktree remove` of it fails
- **THEN** `add` reports the worktree as removed, creates the new worktree, and says nothing of a failed reclaim
