# git-sync Specification

## Purpose
Provides fail-closed remote synchronization for git repositories in the workspace, reporting network, authentication, and branch divergence errors.

## Requirements

### Requirement: Fail closed on remote fetch and pull errors
The system SHALL raise a `GitOperationError` naming the repository, remote, and git's reason when a fetch or pull fails. Neither fetch nor pull operations shall swallow `GitCommandError`.

#### Scenario: Remote refuses fetch
- **WHEN** a git fetch operation encounters an unreachable or forbidden remote
- **THEN** the system raises `GitOperationError` with the repository path, remote name, and sanitized error reason

#### Scenario: Branch cannot fast-forward on pull
- **WHEN** a git pull operation encounters a divergent tracking branch that cannot fast-forward
- **THEN** the system raises `GitOperationError` with the repository path, remote name, and sanitized error reason

### Requirement: Workspace synchronization error reporting and non-zero exit
The `devops repos sync` and `devops branches sync` commands SHALL report each failed repository with git's reason, finish processing all remaining workspace repositories, and exit non-zero when any repository fails.

#### Scenario: One repository fails during repos sync
- **WHEN** one workspace repository encounters a fetch failure during `devops repos sync`
- **THEN** the command prints the failure reason for that repository, synchronizes the remaining repositories, and exits with code 1

#### Scenario: One repository fails during branches sync
- **WHEN** one workspace repository encounters a pull failure during `devops branches sync`
- **THEN** the command prints the failure reason for that repository, synchronizes the remaining repositories, and exits with code 1
