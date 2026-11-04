# test-host-path-guard Specification

## Purpose
The roots that the host path guard of the test harness allows a test to open. The guard fails a test that opens a file outside the checkout, the temporary directory and the interpreter, so a test run in a linked git worktree needs the git directory of that worktree.

## Requirements

### Requirement: A linked worktree may read its git directory
The host path guard SHALL allow a read of the files under the common git directory of a linked worktree, which hold the `HEAD` file of the git directory of the worktree.

#### Scenario: HEAD of a linked worktree
- **WHEN** the allowed roots are built for a linked worktree whose common git directory lies outside it, and the path is `<common dir>/worktrees/<name>/HEAD`
- **THEN** the guard allows the path

#### Scenario: A file outside the git directory
- **WHEN** the allowed roots are built for the same worktree and the path is a file of the main checkout outside its `.git` directory
- **THEN** the guard does not allow the path

### Requirement: No git process finds the common git directory
The host path guard SHALL find the common git directory without a `git` process.

#### Scenario: No process starts
- **WHEN** the allowed roots are built for a linked worktree in a test that has the process fake
- **THEN** the process fake records no call

### Requirement: Another checkout adds no git directory
The host path guard SHALL add no git directory root for a checkout whose `.git` is a directory or points to the git directory of a submodule.

#### Scenario: A plain checkout and a submodule
- **WHEN** the allowed roots are built for a checkout with a `.git` directory, and for a submodule whose `.git` file names a module directory
- **THEN** the roots of each hold the checkout directory only
