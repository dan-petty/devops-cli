## ADDED Requirements

### Requirement: The planner prompt names the issue form of a dependency
The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL state that a `dependencies` entry which starts with `#<number>:` names an issue that must be delivered first, and MUST keep the rule that names each overlap and each metric sender.

#### Scenario: The prompt-rules test reads the form
- **WHEN** the prompt-rules test reads the dependencies rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the test finds the form `#<number>:` and the rule of the overlaps, and it passes
