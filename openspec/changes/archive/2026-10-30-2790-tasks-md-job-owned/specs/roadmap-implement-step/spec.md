# Spec Delta

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. An edit of `tasks.md` SHALL be no reason to stop. A task left unticked after the first three checks first gets the extra turn of the requirement "A step asks once for the missing ticks".

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
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step ticks no task of group 1, gives the extra turn, and stops with the reason that names the first unticked task when the turn changes nothing

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step writes the file from before the run, gives the extra turn for the unticked tasks, and stops with the reason that names the first unticked task when the turn changes nothing

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

### Requirement: A fix step makes a failed check pass
The step SHALL accept a fix request: the name of a failed check and its log. The group of a fix step SHALL be "Make check `<name>` pass", with the verification commands of every group of the change. The inputs SHALL hold the log cut to `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters from its end. The exit checks SHALL be those of a group, except that no task is ticked and `tasks.md` SHALL be as it was. A done fix step SHALL commit as `Make check <name> pass (#N)`.

#### Scenario: A fix step with a long log
- **WHEN** a fix request holds a log longer than the limit
- **THEN** the first message of the step holds the last characters of the log up to the limit, and the first characters are not in it

#### Scenario: The fix step ticks a task
- **WHEN** the model of a fix step ticks or edits a task in `tasks.md`, and changes a source file
- **THEN** the step reports done, and the commit holds the source file and `tasks.md` as it was

### Requirement: The turn for the ticks changes only the tasks file
The extra turn SHALL change no file except the `tasks.md` of the change. The step SHALL check this with git, by comparing the checkout after the turn with the tree of the checkout before it, and SHALL stop with a reason that names the other paths when the turn changed any. After the turn every exit check and the restore of `tasks.md` SHALL run again. The outcome SHALL count the requests and the tokens of both turns, and the spend ledger SHALL hold the replies of both.

#### Scenario: The turn changes another file
- **WHEN** the model changes `src/sample.py` in the extra turn
- **THEN** the step reports stopped with the reason that names `src/sample.py`, makes no commit and resets the checkout

#### Scenario: The turn edits the text of another group
- **WHEN** the model changes the text of a task of group 2 in the extra turn
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: The turn ticks a task of another group
- **WHEN** the model ticks the tasks of group 1 and a task of group 2 in the extra turn
- **THEN** the step reports done, and the commit holds `tasks.md` with group 1 ticked and group 2 as it was

#### Scenario: The spend of two turns
- **WHEN** the first turn took two model requests and the extra turn took one
- **THEN** the outcome reports three requests, and the spend ledger holds the tokens of the three replies

### Requirement: A step makes the only commit
The first exit check SHALL be that `HEAD` is still the commit where the step started.

#### Scenario: A commit by the agent
- **WHEN** the agent commits its work with `git`, and ticks the tasks
- **THEN** the step reports stopped with the reason that `HEAD` moved, makes no commit, and the checkout is back at the commit where the step started

## REMOVED Requirements

### Requirement: A step restores the checkboxes of the other groups
**Reason**: The requirement "A step writes `tasks.md` back to its text before the run" restores the whole file, the checkboxes of the other groups included.
**Migration**: None. The scenarios of this requirement move to the new requirement.

### Requirement: A change of another group beyond its checkboxes stops the step
**Reason**: An edit of `tasks.md` stops the step no more. The job writes the file back (#2790).
**Migration**: None. A file that numbers a group twice before the run is still refused before the step starts, by the new requirement.

### Requirement: A step writes the text of its own group back
**Reason**: The new requirement writes the whole file back, and the own group is a part of it.
**Migration**: None. The scenarios of this requirement move to the new requirement.

## ADDED Requirements

### Requirement: A step writes tasks.md back to its text before the run
After each turn of the model, the step SHALL write the `tasks.md` of the change as it was before the run, with each task of its own group ticked that the model ticked, by position. The step SHALL tick none when the model changed the number of the tasks of the group. The step SHALL print one line that names the change when the file differed, and SHALL stop for no edit of the file. A fix step SHALL tick none. A file that numbers a group twice SHALL be refused before the step starts.

#### Scenario: The model ticks two groups and edits a task of the later one
- **WHEN** the model works on group 1, ticks the tasks of groups 1 and 2, and deletes the number "2.1" from a task of group 2
- **THEN** the step reports done, and the commit holds `tasks.md` as before the run with only the tasks of group 1 ticked, and the step prints one line that names the change

#### Scenario: The model ticks a later group
- **WHEN** the model completes group 1, ticks its tasks and the tasks of group 2, and ends its run
- **THEN** the step reports done, and the commit holds group 1 ticked and group 2 unticked

#### Scenario: The model unticks an earlier group
- **WHEN** the model works on group 2, ticks its tasks, and unticks a task of group 1, which was ticked
- **THEN** the step reports done, and the commit holds group 1 as it was

#### Scenario: The model rewrites the text of a task and ticks it
- **WHEN** the model rewrites the text of task 1.1 and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the text from before the run with the tasks of group 1 ticked

#### Scenario: The model rewrites the text in the extra turn
- **WHEN** the model leaves a task unticked, and in the extra turn rewrites the text of that task and ticks it
- **THEN** the step reports done, and the commit holds the text from before the run with the task ticked

#### Scenario: The model rewrites a verification command to one that passes
- **WHEN** the model replaces the command of a `Verification:` line of group 1 with a command that exits 0, and the original command exits 1
- **THEN** the step runs only the original command, reports stopped, the reason names the original command, and the checkout is reset

#### Scenario: The model adds, removes or reorders groups or tasks
- **WHEN** the model adds a group, removes a group, swaps two tasks of group 2, or adds a section outside every group, and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the structure from before the run with group 1 ticked

#### Scenario: The model ticks part of the group
- **WHEN** the model ticks one of the two tasks of group 1
- **THEN** the step gives the extra turn for the other task, and the task stays unticked in the file

#### Scenario: The model changes the number of the tasks of its group
- **WHEN** the model adds a task to group 1 and ticks every task of the group
- **THEN** the step ticks none, gives the extra turn, and stops with the first unticked task named when the turn changes nothing

#### Scenario: The model removes or garbles the file
- **WHEN** the model removes `tasks.md`, or writes bytes that are not UTF-8 to it, and ticks nothing else
- **THEN** the step writes the file from before the run, and the unticked tasks of the group give the extra turn

#### Scenario: A link or a directory in place of the file
- **WHEN** the model replaces `tasks.md` with a link to a file that holds the text to write, or with a directory
- **THEN** the step removes the link or the directory and writes the file, and the commit holds a regular file

#### Scenario: A file with CRLF or lone CR line ends
- **WHEN** the `tasks.md` has CRLF line ends, or many lone CR line ends before the groups, and the model ticks its group and a later group
- **THEN** the committed `tasks.md` keeps those line ends, the group is ticked on its own lines, and the later group is unticked

#### Scenario: A tick and nothing else
- **WHEN** the last line of group 1 ends with two spaces and the model only ticks its tasks
- **THEN** the step reports done, the commit holds the two spaces, and the step prints no line

#### Scenario: A fix step edits a task
- **WHEN** a fix step ticks a task of any group, or edits the text of a task
- **THEN** the step reports done, and the commit holds `tasks.md` as it was

#### Scenario: A tasks file that numbers a group twice
- **WHEN** the `tasks.md` of the change holds two groups with the number 2
- **THEN** the step is refused before the model runs, and the message names the change and group 2
