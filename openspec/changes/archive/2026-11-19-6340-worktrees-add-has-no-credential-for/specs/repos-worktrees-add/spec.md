## ADDED Requirements

### Requirement: The run reads origin before the reclaim
The `worktrees add` command SHALL read the branches of `origin` with one `git ls-remote --heads origin` before it removes any worktree when it reclaims, and MUST change nothing in the clone when that read fails.

#### Scenario: The read of origin exits 128
- **WHEN** a test runs `worktrees add` on a clone whose `git ls-remote --heads origin` exits 128 and that holds one merged worktree
- **THEN** the command exits non-zero, the merged worktree stays, no worktree is created, the HEAD of the clone is the same as before the run, the run reads no pull request, and the error names `git ls-remote --heads origin` with no `-c` value.

#### Scenario: The read of origin succeeds
- **WHEN** a test runs `worktrees add` on a clone whose `git ls-remote --heads origin` exits 0 and that holds one merged worktree
- **THEN** the command removes that worktree, creates the worktree of the issue, and exits 0.
