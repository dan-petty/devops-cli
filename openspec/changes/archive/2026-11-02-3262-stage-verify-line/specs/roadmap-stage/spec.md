## MODIFIED Requirements

### Requirement: A task group renders the tasks of its kind
A `behavior` group SHALL render `n.1` as its failing test, `n.2` as its implementation, and `n.3` as its documentation when `documentation` is set. An `other` group SHALL render `n.1` as its implementation with its `verify` or its `process`, and `n.2` as its documentation when `documentation` is set. A task with a command SHALL write it on a line `- Verification: ` under the task, as a code span that `step_files` reads. A group with no `documentation` SHALL render no documentation task.

#### Scenario: A deletion that keeps behavior
- **WHEN** an `other` group deletes a definition and its `verify` is a `git grep` that must print nothing
- **THEN** its first task names the deletion, and the line under it holds the `git grep` and says "passes", and no task asks for a test

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
