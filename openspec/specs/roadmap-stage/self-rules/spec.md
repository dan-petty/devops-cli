# roadmap-stage/self-rules Specification

## Purpose
The rules for a plan that changes the stage job itself: the self-acceptance test of a plan check, the eval replay task, the prompt-rule test, and the gate quote rule.

## Requirements

### Requirement: A plan that adds a text rule carries its self-acceptance test
A plan with a behavior group that changes `src/devops_cli/roadmap/stage/stage_change.py` SHALL give a group test text that names `StageProposal`, `content_problems` and no problem, so the plan holds no text that its own rule refuses.

#### Scenario: Plan without the test is refused
- **WHEN** `check_proposal` receives a valid proposal with a behavior group that changes `src/devops_cli/roadmap/stage/stage_change.py` and no group test text that names `StageProposal`, `content_problems` and no problem.
- **THEN** `check_proposal` returns one problem that names `StageProposal` and `content_problems`.

#### Scenario: Plan with the test is accepted
- **WHEN** `check_proposal` receives a valid proposal with a behavior group that changes `src/devops_cli/roadmap/stage/stage_change.py` and a group test text that names `StageProposal`, `content_problems` and no problem.
- **THEN** `check_proposal` returns no self-acceptance problem.

### Requirement: A plan that changes no plan check needs no self-acceptance test
A plan whose groups change no path in `src/devops_cli/roadmap/stage/stage_change.py` MUST NOT be refused by the self-acceptance rule.

#### Scenario: Plan that changes another file is accepted
- **WHEN** `check_proposal` receives a valid proposal whose groups change only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** `check_proposal` returns no self-acceptance problem.

#### Scenario: Plan that only refactors the plan check is accepted
- **WHEN** `check_proposal` receives a valid proposal with an other group that changes `src/devops_cli/roadmap/stage/stage_change.py`.
- **THEN** `check_proposal` returns no self-acceptance problem.

### Requirement: The staging prompt states the self-acceptance test rule
The staging prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` MUST state the self-acceptance test rule beside the other checks of a plan.

#### Scenario: Prompt names the self-acceptance test
- **WHEN** A test loads the prompt with `load_task_prompt`.
- **THEN** The prompt text contains `StageProposal`, `content_problems` and the self-acceptance test rule.

### Requirement: A plan that changes the stage prompt or a stage gate gives the eval replay task
The stage job SHALL refuse a plan whose groups change `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_criteria.py` or `src/devops_cli/roadmap/stage/stage_eval_gates.py` unless one group task holds the command `uv run devops roadmap eval stage --replay` and the words `score`, `before` and `after`.

#### Scenario: Prompt change without a replay task
- **WHEN** A plan changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Gate change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_eval_gates.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Check module change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_paths.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Replay command without the score
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay` but not the words `score`, `before` and `after`.
- **THEN** `check_proposal` returns a problem that asks for the before and after score.

#### Scenario: Trigger path with a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay`, `score`, `before` and `after`.
- **THEN** `check_proposal` returns no problem for the eval replay rule.

#### Scenario: Unrelated source change
- **WHEN** A plan changes only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** `check_proposal` returns no problem for the eval replay rule.

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

### Requirement: A plan that names a defect type member passes
`check_proposal` MUST NOT return a problem for a plan that names a `DefectType` member, including a member that the plan adds.

#### Scenario: A plan adds a member and names it
- **WHEN** `check_proposal` runs on a valid plan whose group changes `src/devops_cli/roadmap/stage_eval_cases.py` and whose test text names `DefectType.PROMPT_KEY_MISSING`
- **THEN** `check_proposal` returns an empty list

### Requirement: A plan that adds a StageProposal field names the reply key of the prompt
The stage job SHALL refuse a plan that adds a field to `StageProposal` and does not change `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the reply key of that field.

#### Scenario: Missing reply key
- **WHEN** A plan has a group that changes `src/devops_cli/roadmap/stage/stage_change.py` and names a new field of `StageProposal`, and no group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The job returns a problem that names `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the missing reply key, and the reply returns to the model once.

#### Scenario: Reply key and rule present
- **WHEN** A plan has a group that adds a field to `StageProposal` and another group that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the new reply key bullet and its rule.
- **THEN** The job returns no problem for the prompt keys.

#### Scenario: A change to the file that adds no field
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` in a group whose text names no new field of `StageProposal`.
- **THEN** The job returns no problem for the prompt keys.

### Requirement: Replay case in golden set
The golden set MUST include one replay case from #3183 or #3225 that exercises the failure taxonomy and runner capability context.

#### Scenario: Replay case runs offline
- **WHEN** The golden-set test runs the #3183 or #3225 replay case.
- **THEN** The case passes with the expected context facts and the expected gate result.

### Requirement: Gate plan quotes the refused defect
A plan that changes a gate file SHALL quote the defective text that the gate must refuse in its Feasibility.

#### Scenario: A gate plan without the defect quote
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_eval_gates.py`, and its Feasibility holds no code span.
- **THEN** `content_problems` returns the message that the Feasibility must quote the defective text.

### Requirement: Gate plan tests the defect on the base
A plan that changes a gate file SHALL give a test task that holds the quoted text and the phrase `fails on the base`.

#### Scenario: A gate plan with the quote and the failing test
- **WHEN** A plan changes a gate file, its Feasibility quotes the defective text, and its test task holds that text and the phrase `fails on the base`.
- **THEN** `content_problems` returns no gate defect problem.

### Requirement: Gate plan without the failing test is refused
A plan that changes a gate file and gives a test task with no `fails on the base` phrase SHALL be refused.

#### Scenario: A gate plan with the quote and no failing test
- **WHEN** A plan changes a gate file and quotes the defective text, and its test task omits `fails on the base`.
- **THEN** `content_problems` returns the message that the test task must fail on the base.

### Requirement: Gate plan states a skipped case as a non-goal
A plan whose gate test says that the rule skips a case SHALL state that non-goal in its design decisions, its rejected alternatives or its spec delta.

#### Scenario: A gate plan that skips a case without a non-goal
- **WHEN** A plan changes a gate file, its test text holds `skip`, and no decision, rejected alternative or spec delta text holds `non-goal`.
- **THEN** `content_problems` returns the message that the plan must state the skipped case as a non-goal.

### Requirement: Gate plan accepts a stated non-goal
A plan that states the non-goal for a skipped gate case MUST pass the non-goal rule.

#### Scenario: A gate plan with the non-goal
- **WHEN** A plan changes a gate file, its test text holds `skip`, and a decision text holds `non-goal`.
- **THEN** `content_problems` returns no non-goal problem.

### Requirement: The gate quote rule runs in the shared check
The gate quote rule MUST run from `content_problems`, which `check_proposal` and the replay call.

#### Scenario: The stage job and the replay report the same message
- **WHEN** A plan changes a gate file and quotes no defective text.
- **THEN** `check_proposal` and `_content_gate` both return the same `RoadmapMessages` text.

### Requirement: The gate quote rule has offline tests
`tests/roadmap/stage/test_roadmap_stage_plan.py` SHALL hold one test that refuses a gate plan with no defect quote and one test that accepts a gate plan with the quote and the failing test task.

#### Scenario: The gate quote tests run
- **WHEN** The test module runs.
- **THEN** The refusing test and the accepting test both pass.

### Requirement: A plan with no gate change is not refused
A plan that changes no gate file MUST pass the gate defect quote rule.

#### Scenario: A plan with no gate change
- **WHEN** A plan changes only `src/devops_cli/sample.py`.
- **THEN** `content_problems` returns no gate quote problem.
