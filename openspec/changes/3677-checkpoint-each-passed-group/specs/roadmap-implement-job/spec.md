## MODIFIED Requirements

### Requirement: The job runs the scoped checks before it pushes
After the final rebase and before the push, the job SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, and `devops ci test` with test modules. It SHALL run each outside the agent shell and without a GitHub token. The job SHALL push a finished item only after all of them pass. The one exception is the checkpoint of a group that passed its step, which the job pushes at the next group boundary before the scoped checks run.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py`, a test module imports it, and every scoped check exits 0
- **THEN** `devops ci test` ran with the path of that test module, the job pushed, and no fix step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the worktree

#### Scenario: A checkpoint comes before the scoped checks
- **WHEN** group 1 of two groups passes its step, and the job reaches the boundary of group 2
- **THEN** `origin` holds the commit of group 1 before any scoped check runs, and the final push still follows only after the scoped checks pass

### Requirement: The job pushes the work in progress of a step
After each `wip:` commit of a step that leaves a task of the group unticked, the job SHALL push the item branch to `origin` with the push of a stop (a push with a lease, or the publish of a Planned item). A `wip:` commit that ticks the last task SHALL wait for the next checkpoint, the push of the stop or the push of the end of the run. A push that fails SHALL NOT stop the step.

#### Scenario: A step is killed after three of five tasks
- **WHEN** a step ticks three of five tasks in three separate tool calls, each verification passes, and the model then fails
- **THEN** `origin` held three `wip:` commits on the item branch before the model failed, and `implement.wip` holds the group, 3 done, 5 tasks and the last commit

#### Scenario: The commit of the last tick waits
- **WHEN** a step ticks all five tasks in five tool calls and the model then fails
- **THEN** `origin` held four `wip:` commits before the model failed, and five after the stop

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.base` (the tip that a withdraw restores), `implement.stopped`, `implement.spend` and `implement.trace` in the job record of the item. It SHALL write `implement.base` once, in the write that sets the Status In Progress, and keep an existing value. The value SHALL be the sha of `origin/<branch>` for a Staged item and `new` for a Planned item. It SHALL clear `implement.base` when it marks the pull request ready and when it returns the item to New. The spend SHALL be the requests, input tokens and output tokens of every step the job ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a ready pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a ready pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

#### Scenario: The base of a Staged item and of a Planned item
- **WHEN** the job starts a Staged item and a Planned item
- **THEN** the record of the Staged item holds the sha of its branch on `origin`, and the record of the Planned item holds `new`

#### Scenario: The base is kept by a second Job and cleared at ready
- **WHEN** a first Job is killed after two groups, a second Job takes the item, and the second Job marks the pull request ready
- **THEN** the second Job sees the base of the first Job, and the record holds no `implement.base` after the ready mark

### Requirement: A false premise returns the item to New
When a step stops with a `premise` request whose evidence is not empty, the job SHALL return the item to New through `apply_return`, with a comment that holds the evidence masked and cut. Before it returns the item, it SHALL withdraw the checkpoints that it pushed. For a Staged item, the withdraw SHALL push the sha of `implement.base` back to the item branch with a lease on the last tip that the job pushed. For a Planned item, the withdraw SHALL delete the item branch with the same lease and close the recorded draft pull request, and SHALL do nothing when `origin` holds no item branch. A withdraw that fails, for a failed lease or for any other reason, SHALL stop the item as Blocked, SHALL NOT return it to New, and SHALL leave the push of a person on the branch. A return SHALL remove the worktree and SHALL clear `implement.group`, `implement.sha`, `implement.branch`, `implement.pr` and `implement.base`. It SHALL NOT set `implement.stopped`.

#### Scenario: A false premise on a Planned item
- **WHEN** the first step of a Planned item ends with a `premise` request and evidence
- **THEN** the Status is New, the comment holds the evidence, `origin` has no branch for the item, no worktree is left, and the record has no `implement.stopped`

#### Scenario: A false premise on a Planned item after a checkpoint
- **WHEN** groups 1 and 2 of a Planned item passed, the checkpoints opened one draft pull request, and the step of group 3 ends with a `premise` request and evidence
- **THEN** the Status is New, `origin` has no branch for the item, the draft pull request is closed, and the record holds no `implement.base`

#### Scenario: A false premise on a Staged item
- **WHEN** the step of group 2 of a Staged item ends with a `premise` request, and group 1 passed in this run
- **THEN** the Status is New, `origin` holds the staged branch at the commit it had before the run, and `implement.group` and `implement.base` are cleared

#### Scenario: A premise request with no evidence
- **WHEN** the `premise` request has an empty `evidence`
- **THEN** the item is stopped as a question and its Status is Blocked

#### Scenario: A person pushed after the last checkpoint
- **WHEN** a person pushes to the item branch after a checkpoint, and a `premise` request with evidence follows
- **THEN** the lease of the withdraw fails, the item is Blocked and is not returned, and the push of the person stays on the branch

#### Scenario: A withdraw that fails
- **WHEN** the push of the withdraw fails with an error that is not a failed lease
- **THEN** the item is Blocked and is not returned, and `origin` keeps the checkpoints

#### Scenario: A withdraw after a refused draft
- **WHEN** GitHub refused the draft of a Planned item at its first checkpoint, and a `premise` request with evidence follows
- **THEN** the withdraw finds no branch on `origin` and does nothing, and the Status is New

### Requirement: The job checks the premise of a behavior group at the branch tip
Before the job runs a behavior group, the job SHALL check each guard or check identifier that a task of the group adds against the branch tip, and SHALL return the item to New with the definition line when the branch tip defines it. The job SHALL read the kind of the group from `TaskGroup.is_behavior` of `src/devops_cli/roadmap/step_files.py`.

#### Scenario: A task adds a guard that the base already runs
- **WHEN** A behavior group task says to add the guard `_delivery_title` and the branch tip defines `_delivery_title`
- **THEN** The job runs no group step, writes no group file, makes no group commit, and comments the definition line with the return to New.

#### Scenario: A task adds a guard that the base lacks
- **WHEN** A behavior group task says to add the guard `_missing_guard` and the branch tip defines no `_missing_guard`
- **THEN** The job runs the group and commits the file that the group writes.

#### Scenario: A group that is not behavior adds a defined name
- **WHEN** A group whose kind is not behavior has a task that says to add the name `_delivery_title`, which the branch tip defines
- **THEN** The job returns no item to New and runs the group.

#### Scenario: The guard premise fails after a checkpoint
- **WHEN** groups 1 and 2 passed and were pushed as checkpoints, and a behavior group 3 adds a guard that the branch tip defines
- **THEN** the job runs no step for group 3, withdraws the checkpoints as for a `premise` request, and returns the item to New

## ADDED Requirements

### Requirement: The job checkpoints each passed group on the item branch
At each group boundary, after the claim check and the premise check and before the step of the group, the job SHALL push the item branch with the push of a stop (a push with a lease, or the publish of a Planned item), when a group passed in this run. The end boundary SHALL push nothing: only the final push, which follows the scoped checks, pushes after the last group.

#### Scenario: A runner is killed after two of four groups
- **WHEN** an item has four groups of one task each, and the runner is killed in group 3
- **THEN** `origin` holds the item branch with the commits of groups 1 and 2

#### Scenario: A second Job runs only the groups that are left
- **WHEN** a first Job is killed after two of four groups, and a second Job takes the item
- **THEN** the second Job runs groups 3 and 4 only, and the item reaches ready

#### Scenario: The first boundary pushes nothing
- **WHEN** the job reaches the boundary of group 1
- **THEN** the job makes no checkpoint push

#### Scenario: The end boundary pushes nothing
- **WHEN** all four groups pass
- **THEN** the job made one push at each of the boundaries of groups 2, 3 and 4, and one final push, and no push at the end boundary

### Requirement: A Planned item gets its draft at the first checkpoint
The first checkpoint of a Planned item SHALL publish the branch and open the draft pull request. A later Job SHALL take the branch as a Staged item. GitHub SHALL be asked for the draft once when it refuses it, and the run SHALL make no more checkpoint pushes after the refusal.

#### Scenario: A Planned item is killed after two of four groups
- **WHEN** a Planned item has four groups of one task each, and the runner is killed in group 3
- **THEN** `origin` holds the item branch with the commits of groups 1 and 2, and GitHub received one request to open a draft pull request

#### Scenario: GitHub refuses the draft
- **WHEN** GitHub refuses the draft at the first checkpoint of a Planned item
- **THEN** the job asked for the draft once, `origin` holds no item branch, the run makes no more checkpoint pushes, and the final push stops the item as it does without a checkpoint

### Requirement: A failed checkpoint does not stop the run
A checkpoint push that fails SHALL NOT stop the run. The job SHALL log the failure, SHALL make no more checkpoint pushes in the run, and SHALL still make the final push.

#### Scenario: A checkpoint push fails
- **WHEN** the push at the boundary of group 2 fails
- **THEN** the run goes on, makes no checkpoint push at the boundaries of groups 3 and 4, and makes the final push
