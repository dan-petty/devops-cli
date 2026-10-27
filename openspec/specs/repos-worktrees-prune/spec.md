# repos-worktrees-prune Specification

## Purpose
Defines which git worktrees `devops repos worktrees prune` removes, refuses and reports as failed, and how its preview, dry-run and confirm modes behave, so that prune never removes a worktree that is in use.

## Requirements

### Requirement: A merged pull request makes a worktree removable
The system SHALL treat a worktree as removable only when GitHub reports a merged pull request whose head commit is the tip of the worktree, and SHALL keep every other worktree, whatever refs contain its tip.

#### Scenario: Squash-merged branch
- **WHEN** the tip of a clean, unlocked worktree is the head of a merged pull request
- **THEN** `prune --confirm` removes the worktree and reports it as removed

#### Scenario: New worktree
- **WHEN** a worktree has no commit of its own and no pull request has its tip as head
- **THEN** `prune --confirm` keeps the worktree and reports that no merged pull request has this commit as its head

#### Scenario: Pushed branch with an open pull request
- **WHEN** the branch of a worktree is pushed and its pull request is open
- **THEN** `prune --confirm` keeps the worktree

#### Scenario: New commit after the merge
- **WHEN** a worktree has a commit that is not the head of the merged pull request
- **THEN** `prune --confirm` keeps the worktree

#### Scenario: Commit that GitHub does not know
- **WHEN** GitHub answers HTTP 422 for the tip of a worktree
- **THEN** `prune --confirm` keeps the worktree and does not fail

### Requirement: Local state protects a worktree
The system SHALL keep the main worktree, a locked worktree, a worktree with uncommitted paths and a worktree whose dirty state is unknown, and SHALL NOT read GitHub for them.

#### Scenario: Locked worktree
- **WHEN** a worktree is locked
- **THEN** `prune --confirm` keeps it and reports the lock reason

#### Scenario: Dirty state unknown
- **WHEN** `git status` fails in a worktree
- **THEN** `worktrees status` shows its dirty count as unknown and `prune --confirm` keeps it

### Requirement: Remove only on confirm
The system SHALL remove a worktree only when `--confirm` is given. Without it, `prune` SHALL read GitHub, list the worktrees that it would remove and the ones it keeps, and change nothing. `--dry-run` SHALL make no external request and SHALL print the requests that the run would make. `--dry-run` with `--confirm` SHALL be refused.

#### Scenario: Preview
- **WHEN** the user runs `devops repos worktrees prune` with a removable worktree
- **THEN** the output says the worktree would be removed and the directory still exists

#### Scenario: Dry run
- **WHEN** the user runs `devops repos worktrees prune --dry-run`
- **THEN** GitHub receives no request and the output lists the request for each worktree that needs one

#### Scenario: Dry run with confirm
- **WHEN** the user runs `devops repos worktrees prune --dry-run --confirm`
- **THEN** the command exits 1 and removes nothing

### Requirement: A failed removal is reported
The system SHALL report a worktree as failed, with the message of git, when `git worktree remove` fails, SHALL keep its directory, and SHALL exit 1.

#### Scenario: Forced removal of a locked worktree
- **WHEN** the user runs `devops repos worktrees prune --force --confirm` and a worktree is locked
- **THEN** the output reports the worktree as failed, its directory still exists and the command exits 1
