## ADDED Requirements

### Requirement: A verify command runs a test that its group names
`form_problems` SHALL return one problem for each test module in a group's `verify` command that the group does not name in `changes`, `creates` or `reads`.

#### Scenario: Unnamed test module
- **WHEN** Group 1 changes `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and `tests/roadmap/test_roadmap_stage_verify.py`, and its `verify` command runs `tests/roadmap/test_roadmap_stage_task_verification.py`.
- **THEN** `form_problems` returns one problem that names group 1, the command and `tests/roadmap/test_roadmap_stage_task_verification.py`.

#### Scenario: Test module in reads
- **WHEN** Group 1 reads `tests/roadmap/test_roadmap_stage_form.py` and its `verify` command runs that module.
- **THEN** `form_problems` returns no problem.

#### Scenario: Test module in changes
- **WHEN** Group 1 changes `tests/roadmap/test_roadmap_stage_form.py` and its `verify` command runs that module.
- **THEN** `form_problems` returns no problem.

#### Scenario: Test module in creates
- **WHEN** Group 1 creates `tests/roadmap/test_roadmap_stage_form.py` and its `verify` command runs that module.
- **THEN** `form_problems` returns no problem.

#### Scenario: Two unnamed test modules
- **WHEN** Group 1's `verify` command runs two test modules that the group does not name.
- **THEN** `form_problems` returns two problems, one for each module.

#### Scenario: Command with no test module
- **WHEN** Group 1 gives `uv run devops ci docs` or `! git grep -n -w unused_probe src/ tests/` as its `verify` command.
- **THEN** `form_problems` returns no problem.
