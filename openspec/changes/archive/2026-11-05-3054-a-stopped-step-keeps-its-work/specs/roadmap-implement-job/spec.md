## ADDED Requirements

### Requirement: The job pushes the work in progress of a step
After each `wip:` commit of a step that leaves a task of the group unticked, the job SHALL push the item branch to `origin` with the push of a stop (a push with a lease, or the publish of a Planned item). A `wip:` commit that ticks the last task SHALL wait for the push of the stop or of the end of the run. A push that fails SHALL NOT stop the step.

#### Scenario: A step is killed after three of five tasks
- **WHEN** a step ticks three of five tasks in three separate tool calls, each verification passes, and the model then fails
- **THEN** `origin` held three `wip:` commits on the item branch before the model failed, and `implement.wip` holds the group, 3 done, 5 tasks and the last commit

#### Scenario: The commit of the last tick waits
- **WHEN** a step ticks all five tasks in five tool calls and the model then fails
- **THEN** `origin` held four `wip:` commits before the model failed, and five after the stop

### Requirement: The job records the work in progress of a step
The job SHALL write `implement.wip` to the job record as JSON with the keys `group`, `done`, `of` and `sha` for a `wip:` commit that it pushes, and at a stop for the last `wip:` commit. When a group passes, the job SHALL remove `implement.wip`.

#### Scenario: A group passes
- **WHEN** a step ends done after a `wip:` commit
- **THEN** the job record holds no `implement.wip`

### Requirement: A second Job resumes from the kept work
The next run of an item SHALL take the branch from `origin` with its `wip:` commits. The step message SHALL show the ticks of the kept tasks, and the step SHALL end done in one commit that holds the kept work.

#### Scenario: A retry after a stop
- **WHEN** a Job stopped after three of five tasks, a person comments `implement: retry`, and the second Job does the fourth and the fifth task
- **THEN** the message of the second step shows three tasks ticked and two unticked, the item reaches a ready pull request, and no commit on the branch has a subject that starts with `wip:`

### Requirement: The stop comment names the kept work
When the branch holds `wip:` commits past the default branch, the stop comment SHALL say how many commits the job kept, the branch on `origin`, and the last commit.

#### Scenario: A stop with kept work
- **WHEN** a step stops with three `wip:` commits on the branch
- **THEN** the comment says that the job kept 3 work-in-progress commits on the branch and names the last commit
