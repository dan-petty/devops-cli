# Spec Delta

## MODIFIED Requirements

### Requirement: A failed removal is reported
The system SHALL report a worktree as failed, with the message of git, when `git worktree remove` fails, SHALL keep its directory, and SHALL exit 1. A worktree that a run in parallel already removed is not a failed removal: the system SHALL report it as removed and count it as done, and the command SHALL exit 0.

#### Scenario: Forced removal of a locked worktree
- **WHEN** the user runs `devops repos worktrees prune --force --confirm` and a worktree is locked
- **THEN** the output reports the worktree as failed, its directory still exists and the command exits 1

#### Scenario: A run in parallel removes a worktree first
- **WHEN** a run in parallel removes a merged worktree before this run removes it, so `git worktree remove` of it fails
- **THEN** the output reports the worktree as removed, not as a failed removal
