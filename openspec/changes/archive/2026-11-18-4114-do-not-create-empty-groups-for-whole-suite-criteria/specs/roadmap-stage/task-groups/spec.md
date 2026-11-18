## ADDED Requirements

### Requirement: The stage prompts forbid empty task groups for whole-suite criteria
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the split prompt `src/devops_cli/ai/tasks/roadmap_stage_split.md` SHALL state that global, performance, or hermeticity criteria MUST be mapped to the task group that delivers or completes the suite, and SHALL forbid creating task groups that only update docstrings or restate instructions.

#### Scenario: Stage prompts state whole-suite criteria mapping
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`
- **THEN** both prompts instruct the model to map global, performance, or hermeticity criteria to the task group that delivers or completes the suite

#### Scenario: Stage prompts forbid docstring-only or instruction-only groups
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`
- **THEN** both prompts forbid creating task groups that only update docstrings or restate instructions
