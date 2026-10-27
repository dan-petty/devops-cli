# Spec Delta

## ADDED Requirements

### Requirement: The worktree of the current directory stays
`prune` SHALL keep the worktree that holds the current directory, also under `--force`, report it as refused with the reason "current directory", and read no pull request for it.

#### Scenario: Prune from inside a merged worktree
- **WHEN** the current directory is inside a clean worktree whose tip heads a merged pull request, and the user runs `prune --confirm`
- **THEN** the worktree is kept and reported as the current directory
- **AND** GitHub receives no request for its tip

#### Scenario: Forced prune from inside a worktree
- **WHEN** the current directory is inside a worktree and the user runs `prune --force --confirm`
- **THEN** that worktree is kept and the other worktrees are removed

#### Scenario: Prune from another directory
- **WHEN** the same merged worktree exists and the current directory is outside it
- **THEN** `prune --confirm` removes it

### Requirement: A removable worktree reports its size
For each worktree that `prune` removes or would remove, the report SHALL give the size of its directory in bytes as `size_bytes`, and the table SHALL show the size beside the worktree and the total in its last line. A worktree whose directory is missing SHALL have no size.

#### Scenario: Preview
- **WHEN** the user runs `prune` and a worktree of 1 MB would be removed
- **THEN** the line of that worktree and the last line give the size

#### Scenario: JSON
- **WHEN** the user runs `prune --confirm --json` and a worktree is removed
- **THEN** its item has `size_bytes` as the number of bytes of the directory before the removal

#### Scenario: Missing directory
- **WHEN** the directory of a worktree is gone and the user runs `prune --json`
- **THEN** its item has a null `size_bytes`
