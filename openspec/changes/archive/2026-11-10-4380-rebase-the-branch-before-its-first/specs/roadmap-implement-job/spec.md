## ADDED Requirements

### Requirement: Every push holds the default branch
The job SHALL fetch `origin/<default>` before each push of the item branch, and SHALL push a commit that holds it. Between steps and at a stop the job SHALL rebase the checkout. During a step the job SHALL rebase a copy of `HEAD` in a detached worktree and push the tip of the copy with a lease on the remote tip that it has seen, and the checkout MUST stay as it is. A conflict SHALL abort the rebase, go to the log, and leave the push to go on with the head.

#### Scenario: The first push of a Planned item
- **WHEN** `main` gains a commit while the first step runs, and the step commits its first `wip:` commit
- **THEN** `main` has no commit that the branch on `origin` lacks

#### Scenario: A later work-in-progress push
- **WHEN** `main` gains a commit after the first `wip:` push, and the step commits a second `wip:` commit
- **THEN** `main` has no commit that the branch on `origin` lacks

#### Scenario: A checkpoint
- **WHEN** `main` gains a commit while group 2 runs
- **THEN** after the checkpoint of group 2 the branch on `origin` holds that commit

#### Scenario: A stop
- **WHEN** `main` gains a commit and the step stops
- **THEN** the push of the stop holds that commit, and `implement.wip` names the last `wip:` commit of the branch on `origin`

#### Scenario: A conflict during a step
- **WHEN** `main` gains a commit that conflicts with the first `wip:` commit
- **THEN** the push keeps the `wip:` commit on `origin`, the log holds the text of the rebase conflict, and no rebase stays in progress
