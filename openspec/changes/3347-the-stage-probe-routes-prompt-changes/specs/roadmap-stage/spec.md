## ADDED Requirements

### Requirement: A prompt change lists the prompt-rule test
A task group that changes a path of the form `src/devops_cli/ai/tasks/roadmap_stage_*.md` SHALL list `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in its `reads` or its `changes`, and `check_proposal` SHALL refuse a group that lists it in neither.

#### Scenario: A prompt change omits the prompt-rule test
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in neither `reads` nor `changes`
- **THEN** `check_proposal` returns one problem that names the prompt path and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

#### Scenario: A prompt change reads the prompt-rule test
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in `reads`, and gives `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` as `verify`
- **THEN** `check_proposal` returns no problem about the prompt-rule test

#### Scenario: A change of another file is not refused
- **WHEN** a group changes `src/devops_cli/roadmap/stage/stage_change.py` and no group changes a `roadmap_stage_*.md` prompt
- **THEN** `check_proposal` returns no problem about the prompt-rule test

### Requirement: A prompt change verifies the prompt-rule test
A task group that changes a path of the form `src/devops_cli/ai/tasks/roadmap_stage_*.md` SHALL give a `verify` command that names `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. A group that gives `process` in place of `verify` SHALL get one problem that names the prompt path and the test path.

#### Scenario: A prompt change verifies another command
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_split.md`, lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in `reads`, and gives `uv run devops ci docs` as `verify`
- **THEN** `check_proposal` returns one problem that names the prompt path and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

#### Scenario: A prompt change gives a process
- **WHEN** a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` in `changes`, and gives `process` with `verify` as `null`
- **THEN** `check_proposal` returns one problem that names the prompt path and the prompt-rule test path

### Requirement: The stage prompts name the prompt-rule test
Each prompt of the form `src/devops_cli/ai/tasks/roadmap_stage_*.md` SHALL state that a group which changes a prompt lists `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and gives it as `verify`.

#### Scenario: The prompt-rule test pins the sentence
- **WHEN** `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` reads `roadmap_stage_change.md` and `roadmap_stage_split.md`
- **THEN** each prompt holds a sentence that names `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
