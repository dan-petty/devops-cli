# Spec Delta

## MODIFIED Requirements

### Requirement: A verify command has the project form
`check_proposal` SHALL refuse a group whose `verify` command does not start with `uv run devops` as a whole word, unless it is a negative search. It SHALL refuse a `verify` command of the project form that the implement step refuses to run, and the problem SHALL hold the reason of the step. The reason SHALL come from the table that the step reads, so that the gate and the step cannot differ.

#### Scenario: A pytest verify command is refused
- **WHEN** a group gives the `verify` command `uv run pytest tests/roadmap/test_stage.py`
- **THEN** `check_proposal` returns a problem that names the command and the accepted forms

#### Scenario: A devops command or a negative search is accepted
- **WHEN** a group gives the `verify` command `uv run devops ci test tests/roadmap/test_stage.py` or `! git grep -n old_name src/ tests/`
- **THEN** `check_proposal` returns no problem about the `verify` command

#### Scenario: A negative search that the step refuses
- **WHEN** a group gives the `verify` command `! git grep -n name src/ | cat` or `! git grep -O name src/`
- **THEN** `check_proposal` returns a problem that names the command and the reason that the step gives

#### Scenario: A verify command that the step runs
- **WHEN** a group gives any of the commands `uv run devops ci`, `uv run devops docs check`, `! git grep -n absent_name src/ tests/` and `! git grep -nI -F old_name -- src/ tests/`
- **THEN** `check_proposal` returns no problem, and the step runs each of them
