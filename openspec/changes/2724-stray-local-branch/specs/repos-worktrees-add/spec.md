## ADDED Requirements

### Requirement: A stray local branch that origin holds is cleared
Before the command creates the worktree on the branch `<type>/N-<slug>`, in a new worktree or in a takeover, it SHALL look for a local branch of that name that no worktree uses. When every commit of that branch is also in `origin/main` or in a remote-tracking ref of `origin`, the command SHALL delete the branch, log one line that names the branch and its commit, and create the worktree.

#### Scenario: A stray branch at the tip of main
- **WHEN** the clone has the local branch `feat/2337-worktrees-add` at the tip of `origin/main` with no worktree, `origin` has no branch for issue 2337, and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the command exits 0 and the worktree `w-2337` is on `feat/2337-worktrees-add`
- **AND** the log has one line that names the branch and its commit

#### Scenario: A stray branch whose commits origin holds
- **WHEN** the local branch has a commit, `origin` has the same commit on a branch of another issue, and the user runs the same command
- **THEN** the command deletes the stray branch and creates the worktree

#### Scenario: A pushed branch and a stray local branch
- **WHEN** `origin` has the staged branch `feat/2657-staged` with a commit by the App, the clone has a local branch of the same name at the tip of `origin/main` with no worktree, and the user runs `add 2657`
- **THEN** the local branch is deleted and the worktree is created on the pushed branch with `origin/feat/2657-staged` as its upstream

#### Scenario: A dry run
- **WHEN** the clone has a stray local branch of the new name and the user runs `add 2337 --type feat --slug worktrees-add --dry-run`
- **THEN** the command deletes nothing and its output says that a real run can delete a stray branch

### Requirement: A stray local branch with a commit that origin lacks is kept and named
When the local branch of the new name has a commit that neither `origin/main` nor a remote-tracking ref of `origin` holds, the command SHALL exit 1 with no change. The error SHALL name the branch and the number of those commits. The command SHALL never delete such a branch.

#### Scenario: A stray branch with a commit of its own
- **WHEN** the local branch `feat/2337-worktrees-add` has one commit that `origin` does not hold, and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the command exits 1 and the error names `feat/2337-worktrees-add` and one commit
- **AND** the branch still has its commit and no worktree is created

#### Scenario: A stray branch of the pushed issue with its own commit
- **WHEN** `origin` has the staged branch `feat/2657-staged`, the clone has a local branch of the same name with a commit that `origin` does not hold, and the user runs `add 2657`
- **THEN** the command exits 1, the error names the branch and one commit, and the branch keeps its commit
