## ADDED Requirements

### Requirement: A verify command runs a test that its group names
`form_problems` SHALL return one problem for each test module in a group's `verify` command that the group does not name in `changes`, `creates` or `reads`. The problem SHALL name the group, the command and the module, and SHALL tell the model to list the module in `reads` or to give the command of the group's own test.

#### Scenario: Unnamed test module
- **WHEN** Group 1 changes `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and `tests/roadmap/test_roadmap_stage_verify.py`, and its `verify` command runs `tests/roadmap/test_roadmap_stage_task_verification.py`.
- **THEN** `form_problems` returns one problem that names group 1, the command and `tests/roadmap/test_roadmap_stage_task_verification.py`, and gives the remedy.

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

#### Scenario: Negative search that names a test module
- **WHEN** Group 1 gives `! git grep -n -w old_name tests/roadmap/test_roadmap_stage_form.py` as its `verify` command, and the group does not name that module.
- **THEN** `form_problems` returns no problem, because the command searches and runs no test.

### Requirement: The staging prompt states the verify-test rule
`src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL say that a `verify` command runs a test module that the group names in `reads`, `changes` or `creates`. `tests/roadmap/test_roadmap_stage_prompt_rules.py` SHALL assert the text.

#### Scenario: The prompt names the rule
- **WHEN** a person reads the `verify` paragraph of `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** it says that a verify test module is one of the group's own paths, and the prompt test asserts the sentence.
