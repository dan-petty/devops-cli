## ADDED Requirements

### Requirement: A verify command has the project form
`check_proposal` SHALL refuse a group whose `verify` command does not start with `uv run devops` as a whole word, unless it starts with `! git grep `.

#### Scenario: A pytest verify command is refused
- **WHEN** a group gives the `verify` command `uv run pytest tests/roadmap/test_stage.py`
- **THEN** `check_proposal` returns a problem that names the command and the accepted forms

#### Scenario: A devops command or a negative search is accepted
- **WHEN** a group gives the `verify` command `uv run devops ci test tests/roadmap/test_stage.py` or `! git grep -n old_name src/ tests/`
- **THEN** `check_proposal` returns no problem about the `verify` command

### Requirement: A new test module sits in a mirror directory
`check_proposal` SHALL refuse a path in `creates` that is a test module under `tests/` unless it is in `tests/invariants/` or in the directory that mirrors the package of a source file that the plan changes.

#### Scenario: A flat test path is refused
- **WHEN** a group creates `tests/test_stage.py` and the plan changes `src/devops_cli/roadmap/stage.py`
- **THEN** `check_proposal` returns a problem that names the path and the directory `tests/roadmap`

#### Scenario: A mirrored or an invariant test path is accepted
- **WHEN** a group creates `tests/roadmap/test_stage.py` or `tests/invariants/test_source_tree.py`
- **THEN** `check_proposal` returns no problem about the test path

### Requirement: The prompt and the rules give a mirrored test path
The stage prompt and `openspec/config.yaml` SHALL give only example test paths whose folder under `tests/` mirrors a package of `src/devops_cli/`.

#### Scenario: Every example path is mirrored
- **WHEN** a test reads the stage prompt and `openspec/config.yaml`
- **THEN** each example test path has a folder under `tests/` that mirrors a package of `src/devops_cli/`
