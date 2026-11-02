## ADDED Requirements

### Requirement: A text of a group stays on one line
The `title`, `test`, `implementation`, `documentation`, `verify` and `process` of a task group, and the `reason` of a criterion, SHALL be written to `tasks.md` on one line. A line break in one of them SHALL add no line, no task, no group and no `Verification:` line.

#### Scenario: A line break and a command
- **WHEN** the `implementation` of a group holds a line break and a line `- Verification: ` with a command
- **THEN** the `verification_commands` of the parsed group are the `verify` of the group and the check of the documents, and no more

#### Scenario: A line break in a title
- **WHEN** the `title` of a group holds a blank line and a line `- [ ] 9.9 Extra`
- **THEN** `tasks.md` holds one group and the task list is that of the group

#### Scenario: A line break in the reason of a criterion
- **WHEN** the `reason` of a `pending-person` criterion holds a line `## 2. Extra`
- **THEN** `tasks.md` holds one group

### Requirement: A verify command holds no backtick
`form_problems` SHALL give a problem for a `verify` command that holds a backtick, and the problem SHALL say that it holds a backtick.

#### Scenario: A backtick in a command
- **WHEN** the `verify` of a group is ``uv run devops ci test `x` ``
- **THEN** `form_problems` gives one problem, and it says that the command holds a backtick

## MODIFIED Requirements

### Requirement: A task group renders the tasks of its kind
A `behavior` group SHALL render `n.1` as its failing test, `n.2` as its implementation, and `n.3` as its documentation when `documentation` is set. An `other` group SHALL render `n.1` as its implementation with its `verify` or its `process`, and `n.2` as its documentation when `documentation` is set. A task with a command SHALL write it on a line `- Verification: ` under the task, as a code span that `step_files` reads. A group with no `documentation` SHALL render no documentation task.

#### Scenario: A deletion that keeps behavior
- **WHEN** an `other` group deletes a definition and its `verify` is a `git grep` that must print nothing
- **THEN** its first task names the deletion, the line under it holds the `git grep` and says "passes", and no task asks for a test or says "fails on the base"

#### Scenario: A manual check
- **WHEN** an `other` group has a `process`
- **THEN** its first task holds the steps of the process, and it has no `Verification:` line

#### Scenario: A behavior group
- **WHEN** a `behavior` group has a `test`
- **THEN** its first task is the test, and the line under it holds the `verify` command and says "fails on the base"

#### Scenario: The step reads the command
- **WHEN** the text that `group_text` writes for a group with a `verify` is parsed with `parse_task_groups`
- **THEN** `verification_commands` of the parsed group holds the `verify` of the group

#### Scenario: A group with documentation
- **WHEN** a group has a `documentation` task
- **THEN** its last task holds the command that regenerates the documents, and its `Verification:` line holds `uv run devops ci docs`
