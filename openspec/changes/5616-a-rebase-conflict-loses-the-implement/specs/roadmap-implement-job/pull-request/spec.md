## ADDED Requirements

### Requirement: A conflict push keeps the work on the item branch
When the rebase of a `wip:`, a checkpoint or a stop push conflicts, the job SHALL abort the rebase and SHALL push the head commit to the item branch with `--force-with-lease` on the remote tip that it has seen. The job SHALL create the branch when `origin` holds none, SHALL open no pull request, SHALL write each conflicting path to `implement.conflict`, and SHALL go on with the run. The push SHALL run with the pre-push hook skipped.

#### Scenario: A conflict at a checkpoint push
- **WHEN** the default branch gains a change to a file that group 1 also changed, and the checkpoint push of group 2 rebases onto it and conflicts
- **THEN** the push aborts the rebase, the item branch on `origin` holds the commit of group 1, the job record holds the conflicting path, and the run goes on

#### Scenario: A conflict at a wip push
- **WHEN** a task of group 1 is ticked and leaves a task unticked, the default branch gains a change to the same file, and the rebase of the copy conflicts
- **THEN** the job aborts the rebase of the copy, the item branch on `origin` holds the `wip:` commit, and the step goes on

#### Scenario: A Planned item with no branch
- **WHEN** a Planned item has no branch on `origin` and its first push conflicts
- **THEN** the job creates the item branch at the head commit and asks GitHub for no pull request

#### Scenario: A conflict push skips the pre-push hook
- **WHEN** the head does not hold the default branch and the job pushes it after a conflict
- **THEN** the `git push` command holds `--no-verify` and the item branch on `origin` holds the head

### Requirement: A conflict at the end push keeps the branch and stops
When the rebase of the end push conflicts, the job SHALL push the head commit to the item branch with `--force-with-lease` on the remote tip that it has seen, SHALL open no pull request, and SHALL stop the item with the class `conflict`. The item branch on `origin` SHALL hold each commit that the run passed.

#### Scenario: A conflict at the end push
- **WHEN** the default branch gains a change to a file that group 1 also changed, and the end push rebases onto it and conflicts
- **THEN** the item branch on `origin` holds the commit of group 1 and the commit of the archive, and the item stops with the class `conflict`

#### Scenario: The end push of a one-group item
- **WHEN** an item of one task group reaches the end push and its rebase conflicts
- **THEN** the item branch on `origin` holds each commit of the run and the item stops with the class `conflict`

## MODIFIED Requirements

### Requirement: Each push holds the default branch unless its rebase conflicts
The job SHALL fetch `origin/<default>` before each push of the item branch and SHALL push a commit that holds it. Between steps and at a stop the job SHALL rebase the checkout. During a step the job SHALL rebase a copy of `HEAD` in a detached worktree and push its tip with a lease, and the checkout MUST stay as it is. A conflict SHALL abort the rebase and go to the log, and the conflict push SHALL push the head.

#### Scenario: The first push of a Planned item
- **WHEN** the default branch gains a commit while the first step runs, and the step commits its first `wip:` commit
- **THEN** the default branch has no commit that the branch on `origin` lacks

#### Scenario: A later work-in-progress push
- **WHEN** the default branch gains a commit after the first `wip:` push, and the step commits a second `wip:` commit
- **THEN** the default branch has no commit that the branch on `origin` lacks

#### Scenario: A checkpoint
- **WHEN** the default branch gains a commit while group 2 runs
- **THEN** after the checkpoint of group 2 the branch on `origin` holds that commit

#### Scenario: A stop
- **WHEN** the default branch gains a commit and the step stops
- **THEN** the push of the stop holds that commit, and the job record names the last `wip:` commit of the branch on `origin`

#### Scenario: A conflict during a step
- **WHEN** the default branch of a Planned item gains a commit that conflicts with the first `wip:` commit, and the step then stops
- **THEN** the item branch on `origin` holds the `wip:` commit, the log holds the text of the rebase conflict, and no rebase stays in progress

## RENAMED Requirements

- FROM: `### Requirement: Every push holds the default branch`
- TO: `### Requirement: Each push holds the default branch unless its rebase conflicts`
