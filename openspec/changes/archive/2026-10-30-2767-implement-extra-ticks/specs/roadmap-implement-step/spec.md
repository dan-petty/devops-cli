# Spec Delta

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the group changed only in its checkboxes and no other group changed beyond its checkboxes, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A task left unticked after the first three checks first gets the extra turn of the requirement "A step asks once for the missing ticks".

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no commit and resets the checkout

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, the verification command and the static checks exit 0, and the extra turn leaves the task unticked
- **THEN** the step reports stopped, the reason names the unticked task, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

### Requirement: A step asks once for the missing ticks
When the agent ends its run, the check of the tasks passes, each verification command passes, the static checks pass, and a task of the group is unticked, the step SHALL run one more model turn. The turn SHALL continue the same conversation under the same `UsageLimits`. Its message SHALL name the path of the `tasks.md` and list the unticked tasks, and SHALL ask only for their ticks. The step SHALL run the turn at most once, and SHALL run none for a fix step.

#### Scenario: The agent forgot the ticks
- **WHEN** the model writes a test file and a source file, ends its run with the tasks of group 1 unticked, the verification command and the static checks exit 0, and the model ticks the tasks in the extra turn
- **THEN** the step reports done, the extra turn got the list of the unticked tasks, the new commit holds the test file, the source file and the ticked `tasks.md`, and the verification command ran twice

#### Scenario: The turn ticks nothing
- **WHEN** the model ends the extra turn and leaves the task unticked
- **THEN** the step reports stopped with the reason that names the unticked task, and the model got no third turn

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and no ticks
- **THEN** the step commits the fix and the model gets no extra turn

### Requirement: The turn for the ticks changes only the tasks file
The extra turn SHALL change no file except the `tasks.md` of the change. The step SHALL check this with git, by comparing the checkout after the turn with the tree of the checkout before it, and SHALL stop with a reason that names the other paths when the turn changed any. After the turn every exit check and the restore of the other groups SHALL run again. The outcome SHALL count the requests and the tokens of both turns, and the spend ledger SHALL hold the replies of both.

#### Scenario: The turn changes another file
- **WHEN** the model changes `src/sample.py` in the extra turn
- **THEN** the step reports stopped with the reason that names `src/sample.py`, makes no commit and resets the checkout

#### Scenario: The turn edits the text of another group
- **WHEN** the model changes the text of a task of group 2 in the extra turn
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: The turn ticks a task of another group
- **WHEN** the model ticks the tasks of group 1 and a task of group 2 in the extra turn
- **THEN** the step reports done, and the commit holds `tasks.md` with group 1 ticked and group 2 as it was

#### Scenario: The spend of two turns
- **WHEN** the first turn took two model requests and the extra turn took one
- **THEN** the outcome reports three requests, and the spend ledger holds the tokens of the three replies

## ADDED Requirements

### Requirement: A step restores the checkboxes of the other groups
After each turn of the model, the step SHALL compare every group other than its own with its text before the run. A group that differs only in its checkboxes SHALL get the checkbox state of that text written back to `tasks.md`, and the step SHALL print one line to the error stream that names the restored groups. The commit SHALL hold the restored file.

#### Scenario: The model ticks a later group
- **WHEN** the model completes group 1, ticks its tasks and the tasks of group 2, which was unticked, and ends its run
- **THEN** the step reports done, the commit holds the work and `tasks.md` with group 1 ticked and group 2 unticked, and the step prints one line that names group 2

#### Scenario: The model unticks an earlier group
- **WHEN** the model works on group 2, ticks its tasks, and unticks a task of group 1, which was ticked
- **THEN** the step reports done, and the commit holds `tasks.md` with group 1 as it was

#### Scenario: A file with CRLF line ends
- **WHEN** the `tasks.md` has CRLF line ends and the model ticks a later group
- **THEN** the committed `tasks.md` keeps its CRLF line ends and the later group is unticked

#### Scenario: A file with lone CR line ends
- **WHEN** the model writes a `tasks.md` that has many lone CR line ends before the groups, and ticks a later group
- **THEN** the step reports done, and the committed `tasks.md` has the later group unticked on its own line

### Requirement: A change of another group beyond its checkboxes stops the step
After the restore, the text of each other group SHALL equal its text before the run. Any difference beyond the checkboxes SHALL stop the step with the group named: a title, a task, a command, a bullet or a line changed, added or removed. A group number that two groups hold after the run SHALL stop the step, and one that two groups hold before the run SHALL be refused before the step starts. The own group SHALL keep its rule. A fix step SHALL change no task and restore nothing.

#### Scenario: The model ticks a later group and edits its text
- **WHEN** the model ticks a task of group 2 and also changes the text of that task
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: The model changes a bullet of a later group
- **WHEN** the model ticks the tasks of group 2 and changes `-` to `*` before one of them
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: The model adds a line to a later group
- **WHEN** the model adds a paragraph to group 2, with or without a change of its checkboxes
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A copy of a group hides an edit
- **WHEN** the model edits a task of group 2 and adds a second group 2 that is a copy of the original
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A fix step with a copy of a group
- **WHEN** a fix step edits a task of group 2 and adds a second group 2 that is a copy of the original
- **THEN** the step reports stopped with the reason that a fix step changes no task

#### Scenario: A tasks file that numbers a group twice
- **WHEN** the `tasks.md` of the change holds two groups with the number 2
- **THEN** the step is refused before the model runs, and the message names the change and group 2

#### Scenario: A fix step
- **WHEN** a fix step ticks a task of any group
- **THEN** the step reports stopped with the reason that a fix step changes no task
