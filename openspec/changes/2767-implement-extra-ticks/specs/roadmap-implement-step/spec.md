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

### Requirement: The turn for the ticks changes only the tasks file
The extra turn SHALL change no file except the `tasks.md` of the change. The step SHALL check this with git, by comparing the checkout after the turn with the tree of the checkout before it, and SHALL stop with a reason that names the other paths when the turn changed any. After the turn every exit check SHALL run again, and the step SHALL restore the checkboxes of the other groups again. The outcome SHALL count the requests and the tokens of both turns, and the spend ledger SHALL hold the replies of both.

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

### Requirement: A change of another group beyond its checkboxes stops the step
A difference in another group other than its checkboxes, the title, the text of a task, a verification command, or a task or group added or removed, SHALL stop the step with the group named. The own group SHALL keep its rule: its checkboxes may change, and its text may not. A fix step SHALL change no task, checkboxes included, and SHALL restore nothing.

#### Scenario: The model ticks a later group and edits its text
- **WHEN** the model ticks a task of group 2 and also changes the text of that task
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A fix step
- **WHEN** a fix step ticks a task of any group
- **THEN** the step reports stopped with the reason that a fix step changes no task
