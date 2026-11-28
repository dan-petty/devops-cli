## Purpose
Resolve the working tree verified by `devops ci`, keep stale worktree warnings, stop outside a git work tree, and key CI cache and coverage index files by the quality gate root.

## ADDED Requirements

### Requirement: Quality gate root for a worktree of a nested clone
`devops ci` MUST resolve its quality gate root from the nearest enclosing git work tree, including a linked worktree of a clone under `repos/` inside another checkout.

#### Scenario: Worktree of a clone below the data directory
- **WHEN** an outer checkout contains a clone under `repos/<owner>/<name>` with a linked worktree at `.data/agent/worktrees/h-1`, and the user runs `devops ci` there
- **THEN** the announced `Quality gate root` is the worktree path and each check process with a working directory runs in that worktree

### Requirement: Stale worktree still checked
When a linked worktree's git directory is missing, `devops ci` MUST still resolve to the nearest ancestor holding a `.git` entry and keep the stale-worktree warning.

#### Scenario: Stale linked worktree
- **WHEN** the git directory of a linked worktree is missing, `git rev-parse --show-toplevel` exits 128, and `devops ci` runs from that worktree
- **THEN** the announced root is the worktree and the command prints the stale linked worktree warning

### Requirement: Stop outside a work tree
When the current directory is not inside any git work tree, `devops ci` MUST stop with exit code 1, print a message naming that directory, and start no check.

#### Scenario: Directory that is not in a work tree
- **WHEN** `devops ci --check` runs in a directory with no `.git` entry in or above it and `git rev-parse --show-toplevel` exits 128
- **THEN** the command exits 1, prints a message naming that directory, and starts no check

### Requirement: Cache and coverage index keyed by the gate root
The CI cache and coverage index paths of a gate run MUST be keyed by `find_gate_root(root)`.

#### Scenario: Cache and coverage paths of the nested clone worktree
- **WHEN** a caller resolves the CI cache path and coverage index path for `.data/agent/worktrees/h-1` of a `repos/` clone and for the outer checkout
- **THEN** the worktree's cache path and coverage index path both differ from those of the outer checkout
