# Spec Delta

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the own group keeps the number, the order and the heading of its tasks and no other group changed beyond its checkboxes, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A task left unticked after the first three checks first gets the extra turn of the requirement "A step asks once for the missing ticks".

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

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

### Requirement: A change of another group beyond its checkboxes stops the step
After the restore, the text of each other group SHALL equal its text before the run. Any difference beyond the checkboxes SHALL stop the step with the group named: a title, a task, a command, a bullet or a line changed, added or removed. A group number that two groups hold after the run SHALL stop the step, and one that two groups hold before the run SHALL be refused before the step starts. The own group SHALL follow the requirement "A step writes the text of its own group back". A fix step SHALL change no task and restore nothing.

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

## ADDED Requirements

### Requirement: A step writes the text of its own group back
After each turn of the model, the step SHALL write the text of its own group from before the run back to `tasks.md`, when the group holds the same tasks in the same order under the same heading. It SHALL keep the checkbox state that the model set, and print one line to the error stream that names the group. A change of the checkboxes only SHALL print no line. The verification commands SHALL be those of the text before the run. A fix step SHALL change no task.

#### Scenario: The model rewrites the text of a task
- **WHEN** the model writes its files, rewrites the text of task 1.1 in `tasks.md` to name another file, ticks the tasks of group 1, and ends its run
- **THEN** the step reports done, the commit holds `tasks.md` with the text of group 1 from before the run and its tasks ticked, and the step prints one line that names group 1

#### Scenario: The model rewrites the text in the extra turn
- **WHEN** the model leaves a task unticked, and in the extra turn rewrites the text of that task and ticks it
- **THEN** the step reports done, and the commit holds the text from before the run with the task ticked

#### Scenario: The model rewrites a verification command to one that passes
- **WHEN** the model replaces the command of a `Verification:` line of group 1 with a command that exits 0, and the original command exits 1
- **THEN** the step runs only the original command, reports stopped, the reason names the original command, and the checkout is reset

#### Scenario: The model rewrites a line that is no task
- **WHEN** the model changes a paragraph of group 1 that is no task, and ticks the tasks
- **THEN** the step reports done, and the commit holds the paragraph from before the run

#### Scenario: The model ticks and changes nothing else
- **WHEN** the model ticks the tasks of group 1 and changes no text
- **THEN** the step reports done, and the step prints no line about the group

#### Scenario: A file with CRLF line ends
- **WHEN** the `tasks.md` has CRLF line ends and the model rewrites the text of a task of group 1
- **THEN** the committed `tasks.md` keeps its CRLF line ends and the text from before the run

#### Scenario: A fix step edits a task
- **WHEN** a fix step edits the text of a task of group 1
- **THEN** the step reports stopped with the reason that a fix step changes no task
