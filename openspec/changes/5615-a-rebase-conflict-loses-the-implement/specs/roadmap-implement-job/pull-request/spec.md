## ADDED Requirements

### Requirement: A conflicting push keeps the head on the item branch
A checkpoint, `wip:` or stop push whose rebase conflicts SHALL abort the rebase, push the head of the checkout to the item branch with a lease, and record the conflicting paths in `implement.conflict`. The run SHALL make its next checkpoint push. The final push whose rebase conflicts MUST push nothing, MUST keep the item branch on `origin`, and SHALL stop the item with the class `conflict`, naming the conflicting paths in its comment.

#### Scenario: A conflict at a checkpoint
- **WHEN** `main` gains a commit that changes `CONTEXT.md` after group 1 passed, and the checkpoint push before group 2 conflicts
- **THEN** the checkpoint push before group 3 puts the commit of group 2 on the item branch, and `implement.conflict` names `CONTEXT.md`

#### Scenario: A conflict at a work-in-progress push
- **WHEN** `main` of a Planned item gains a commit that conflicts with the first `wip:` commit of a step
- **THEN** the `wip:` push puts that commit on the item branch, and no rebase stays in progress

#### Scenario: A conflict at the final push
- **WHEN** the final push rebases onto a `main` that conflicts with the branch after a checkpoint kept the passed groups
- **THEN** the item stops with the class `conflict`, the comment names the conflicting path, and `origin` keeps the item branch

## MODIFIED Requirements

### Requirement: A push rebases onto the default branch
The job SHALL fetch `origin/<default>` before each push of the item branch, and SHALL push a commit that holds it. Between steps and at a stop the job SHALL rebase the checkout. During a step the job SHALL rebase a copy of `HEAD` in a detached worktree and push the tip of the copy with a lease on the remote tip that it has seen, and the checkout MUST stay as it is.

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
- **THEN** the push of the stop holds that commit

#### Scenario: A conflict during a step
- **WHEN** `main` of a Planned item gains a commit that conflicts with the first `wip:` commit, and the step then stops
- **THEN** the job aborts the rebase, and no rebase stays in progress

## RENAMED Requirements

- FROM: `### Requirement: Every push holds the default branch`
- TO: `### Requirement: A push rebases onto the default branch`
