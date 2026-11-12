## MODIFIED Requirements

### Requirement: A stopped item is Blocked and the job does not retry it
When a step, the rebase, the documentation, the archive, a push or the checks stop the item, the job SHALL post a comment that starts with the marker and names the step, the reason and the last message of the agent, SHALL set Status to Blocked, and SHALL record `implement.stopped` with the step. It SHALL push the commits of the steps that passed, unless a rebase stopped. The job SHALL NOT run the item again until a clear rule removes the record. The job SHALL go on to the next selected item.

#### Scenario: A step stops
- **WHEN** the step of group 2 reports stopped
- **THEN** Status is Blocked, `implement.stopped` is `group 2`, the comment holds the reason, `origin` holds the commit of group 1, and the pull request is still a draft

#### Scenario: A conflict on the rebase before a push
- **WHEN** the default branch gains a change that conflicts with the branch after the last group, or after the fix step
- **THEN** the job aborts the rebase, `origin` holds only the commits that a checkpoint pushed, Status is Blocked, and `implement.stopped` is `push`

### Requirement: Every push holds the default branch
The job SHALL fetch `origin/<default>` before each push of the item branch, and SHALL push a commit that holds it. Between steps and at a stop the job SHALL rebase the checkout. During a step the job SHALL rebase a copy of `HEAD` in a detached worktree and push the tip of the copy with a lease on the remote tip that it has seen, and the checkout MUST stay as it is. A conflict SHALL abort the rebase and go to the log, and the job SHALL push nothing.

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
- **WHEN** `main` of a Planned item gains a commit that conflicts with the first `wip:` commit, and the step then stops
- **THEN** `origin` has no item branch, the log holds the text of the rebase conflict, and no rebase stays in progress
