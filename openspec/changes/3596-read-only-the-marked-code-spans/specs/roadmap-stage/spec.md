## ADDED Requirements

### Requirement: The stage writes the mark before each verification command
The stage job SHALL write the code span of each `Verification:` line it writes as `$ ` followed by the command, for a task that tests, a task that implements and a task that documents, so that the implement step reads the command.

#### Scenario: A staged group
- **WHEN** the stage job writes the tasks of a `behavior` group with the `verify` command `uv run devops ci test tests/test_sample.py`
- **THEN** the `Verification:` line of each of its first two tasks holds the code span `$ uv run devops ci test tests/test_sample.py`, and `parse_task_groups` reads the command without the mark
