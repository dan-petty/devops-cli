## ADDED Requirements

### Requirement: A behavior group runs a test module of the group
`form_problems` SHALL refuse a `behavior` group whose `verify` command names no test module, or names a test module that its `test`, `changes`, `creates` and `reads` do not name. A directory under `tests/` SHALL be no test module. A negative search SHALL stay accepted, and a command with a form problem SHALL get the form problem only. The problem SHALL name the group, the command and the test module that the group should run.

#### Scenario: A command that runs no test module
- **WHEN** a behavior group has the verify `uv run devops ci docs` and the test module `tests/test_sample.py`
- **THEN** `form_problems` returns one problem that names the group, the command and `tests/test_sample.py`

#### Scenario: The verify names a test directory
- **WHEN** a behavior group has the verify `uv run devops ci test tests/roadmap/` and the test module `tests/roadmap/test_roadmap_stage_form.py`
- **THEN** `form_problems` returns one problem for that group

#### Scenario: The group runs its own test module
- **WHEN** a behavior group has the verify `uv run devops ci test tests/test_sample.py` and its `test` text names `tests/test_sample.py`
- **THEN** `form_problems` returns no problem for that group

#### Scenario: An other group runs another command
- **WHEN** an `other` group has the verify `uv run devops ci docs`
- **THEN** `form_problems` returns no problem for that group
