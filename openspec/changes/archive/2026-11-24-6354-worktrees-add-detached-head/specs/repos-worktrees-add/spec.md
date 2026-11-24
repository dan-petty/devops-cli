## ADDED Requirements

### Requirement: Create path keeps the clone branch
The `devops repos worktrees add` command SHALL leave the clone on its original branch after it creates a worktree.

#### Scenario: Successful create keeps HEAD
- **WHEN** A test runs `devops repos worktrees add` on a temporary clone with a local bare origin and a stubbed claim, and the command exits 0
- **THEN** The test asserts that `git -C <clone> symbolic-ref --short -q HEAD` returns the original branch

### Requirement: Take-over path keeps the clone branch
The `devops repos worktrees add` command SHALL leave the clone on its original branch after it takes over a pushed branch.

#### Scenario: Successful take-over keeps HEAD
- **WHEN** A test runs `devops repos worktrees add` on a temporary clone with a local bare origin and an App-authored branch, and the command exits 0
- **THEN** The test asserts that `git -C <clone> symbolic-ref --short -q HEAD` returns the original branch

### Requirement: Reclaim keeps the clone branch
The reclaim of merged worktrees SHALL leave the clone on its original branch.

#### Scenario: Reclaim keeps HEAD
- **WHEN** A test calls `reclaim_merged_worktrees` with a test double for `prune_worktrees` that detaches HEAD and returns an empty report
- **THEN** The test asserts that `git -C <clone> symbolic-ref --short -q HEAD` returns the original branch

### Requirement: Restore failure is a typed error
The command MUST raise `GitOperationError` when it cannot restore the original branch.

#### Scenario: Failed restore reports a typed error
- **WHEN** A test calls `add_worktree` with a test double that detaches HEAD and a restore helper that fails
- **THEN** The test asserts that `GitOperationError` is raised and its message names the original branch
