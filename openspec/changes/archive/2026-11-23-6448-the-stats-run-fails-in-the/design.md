# Design

## Decisions

### Initialize mutants root with git init
Initialize `mutants/.git` before starting mutmut.
`_resolve_git_dir` and `_repository` find `.git` inside the mutants root.
This stops traversal before reaching the parent checkout.

### Keep checkout .git unchanged
`git init -q` in the mutants directory does not alter the parent checkout.
Linked worktrees keep their `.git` file pointer unchanged.

### No commit required for path resolution
The path resolution checks only require a `.git` directory or marker.
An empty Git repository satisfies the guard without committing files.

## Rejected alternatives

- **Allow parent `.git` in host path guard**: Permits tests to inspect code outside the mutant tree.
- **Fake Git in each affected test**: Requires altering dozens of tests and does not fix real runs.
- **Create an empty commit in mutants tree**: Unnecessary overhead since directory checks only require `.git`.
