## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, no test from the start is lost, each verification command passes, the static checks pass, the hooks pass, and every task is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no step commit, and reset the checkout to its last `wip:` commit, or to its start. A failed static check or hook, and an unticked task, first get the extra turns of their own requirements.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in every extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no step commit and resets the checkout to its last `wip:` commit

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, the verification command and the static checks exit 0, and every extra turn leaves the task unticked
- **THEN** the step reports stopped, the reason names the unticked task, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step ticks no task of group 1, gives the extra turn, and stops with the reason that names the first unticked task when the turns change nothing

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step writes the file from before the run, gives the extra turn for the unticked tasks, and stops with the reason that names the first unticked task when the turns change nothing

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

#### Scenario: A test that the agent removes
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks the tasks
- **THEN** the step reports stopped with the reason that names the file and the missing tests, no verification command runs, and the checkout is reset

### Requirement: A step makes the only commit
The first exit check SHALL be that `HEAD` is still the commit where the step started, or the last `wip:` commit of the step.

#### Scenario: A commit by the agent
- **WHEN** the agent commits its work with `git`, and ticks the tasks
- **THEN** the step reports stopped with the reason that `HEAD` moved, makes no commit, and the checkout is back at its last `wip:` commit, or at the commit where the step started when it made none

## ADDED Requirements

### Requirement: A step keeps a ticked task whose verification passes
When the agent ticks a task of the group, the step SHALL run the verification commands of that task, as the text of the `tasks.md` before the run gives them. When they pass, or the task has none, the step SHALL commit the checkout as `wip: <done> of <total> tasks of group <n>, <title> (#<issue>)` and tell its caller through `on_wip`. A task that fails its verification SHALL NOT be kept, and a fix step SHALL keep nothing.

#### Scenario: Two tasks, one ticked
- **WHEN** the model writes the test, ticks the first task, writes the code of the second task, and ends without a tick for it
- **THEN** the step reports stopped, the checkout holds one `wip:` commit with the test and the first task ticked, the code of the second task is gone, and `on_wip` was called once with 1 of 2

#### Scenario: A task that fails its verification
- **WHEN** the model ticks the first task and its verification command exits 1
- **THEN** the step makes no `wip:` commit and calls no `on_wip`

#### Scenario: A lint error after the last tick
- **WHEN** the model ticks every task, each verification passes, and `ruff check` fails at the exit
- **THEN** the step reports stopped, and the checkout holds one `wip:` commit with the work and the ticks

### Requirement: A work-in-progress commit holds the tasks file of the job
The `wip:` commit SHALL hold the `tasks.md` as it was before the run with the ticks that the step verified, and no stray file of the group. The step SHALL make no `wip:` commit that would lose a test that existed at the start. The agent SHALL find its own `tasks.md` in the checkout after the commit.

#### Scenario: A test that the work would lose
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks a task
- **THEN** the step runs no verification command at the tick and makes no `wip:` commit

#### Scenario: A stray file
- **WHEN** the model writes a file outside `src/`, `tests/`, `docs/` and `openspec/` and ticks a task
- **THEN** the `wip:` commit does not hold that file

### Requirement: A step that ends done folds its work in progress into its commit
A step that starts on a branch with `wip:` commits and ends done SHALL make one commit, titled `<group title> (#N)`, that holds all the work since the last commit that is no `wip:` commit. The branch SHALL then hold no `wip:` commit of that step. The exit checks SHALL judge all the work since that commit.

#### Scenario: A second step finishes the group
- **WHEN** a step stopped after a `wip:` commit, and a second step ticks the remaining task
- **THEN** the second step reports done, the message of its first request shows the kept task ticked, and the branch holds one new commit past the start, which does not start with `wip:`
