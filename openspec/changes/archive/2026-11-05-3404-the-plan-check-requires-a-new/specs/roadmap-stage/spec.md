## ADDED Requirements

### Requirement: A plan that adds a text rule carries its self-acceptance test
A plan with a behavior group that changes `src/devops_cli/roadmap/stage_change.py` SHALL give a group test text that names `StageProposal`, `content_problems` and no problem, so the plan holds no text that its own rule refuses.

#### Scenario: Plan without the test is refused
- **WHEN** `check_proposal` receives a valid proposal with a behavior group that changes `src/devops_cli/roadmap/stage_change.py` and no group test text that names `StageProposal`, `content_problems` and no problem.
- **THEN** `check_proposal` returns one problem that names `StageProposal` and `content_problems`.

#### Scenario: Plan with the test is accepted
- **WHEN** `check_proposal` receives a valid proposal with a behavior group that changes `src/devops_cli/roadmap/stage_change.py` and a group test text that names `StageProposal`, `content_problems` and no problem.
- **THEN** `check_proposal` returns no self-acceptance problem.

### Requirement: A plan that changes no plan check needs no self-acceptance test
A plan whose groups change no path in `src/devops_cli/roadmap/stage_change.py` MUST NOT be refused by the self-acceptance rule.

#### Scenario: Plan that changes another file is accepted
- **WHEN** `check_proposal` receives a valid proposal whose groups change only `src/devops_cli/roadmap/stage.py`.
- **THEN** `check_proposal` returns no self-acceptance problem.

#### Scenario: Plan that only refactors the plan check is accepted
- **WHEN** `check_proposal` receives a valid proposal with an other group that changes `src/devops_cli/roadmap/stage_change.py`.
- **THEN** `check_proposal` returns no self-acceptance problem.

### Requirement: The staging prompt states the self-acceptance test rule
The staging prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` MUST state the self-acceptance test rule beside the other checks of a plan.

#### Scenario: Prompt names the self-acceptance test
- **WHEN** A test loads the prompt with `load_task_prompt`.
- **THEN** The prompt text contains `StageProposal`, `content_problems` and the self-acceptance test rule.
