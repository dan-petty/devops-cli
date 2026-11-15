## MODIFIED Requirements

### Requirement: A push rebases onto the default branch
The job SHALL fetch `origin/<default>` before each push of the item branch, including after the scoped checks of the final push, and SHALL push a commit that holds it. Between steps, after the scoped checks, and at a stop the job SHALL rebase the checkout. During a step the job SHALL rebase a copy of `HEAD` in a detached worktree and push the tip of the copy with a lease on the remote tip that it has seen, and the checkout MUST stay as it is.

#### Scenario: The first push of a Planned item
- **WHEN** `main` gains a commit while the first step runs, and the step commits its first `wip:` commit
- **THEN** `main` has no commit that the branch on `origin` lacks

#### Scenario: A later work-in-progress push
- **WHEN** `main` gains a commit after the first `wip:` push, and the step commits a second `wip:` commit
- **THEN** `main` has no commit that the branch on `origin` lacks

#### Scenario: A checkpoint
- **WHEN** `main` gains a commit while group 2 runs
- **THEN** after the checkpoint of group 2 the branch on `origin` holds that commit

#### Scenario: The final push
- **WHEN** `main` gains a commit while the scoped checks run
- **THEN** after the scoped checks the pushed branch on `origin` holds that commit

#### Scenario: A conflict after scoped checks
- **WHEN** `main` gains a conflicting commit while the scoped checks run
- **THEN** the job stops with status Blocked, and the job pushes nothing

#### Scenario: A stop
- **WHEN** `main` gains a commit and the step stops
- **THEN** the push of the stop holds that commit

#### Scenario: A conflict during a step
- **WHEN** `main` of a Planned item gains a commit that conflicts with the first `wip:` commit, and the step then stops
- **THEN** the job aborts the rebase, and no rebase stays in progress
