## ADDED Requirements

### Requirement: The verification prompt names a line that quotes no statement of its module
The verification prompt SHALL state that a line which names a type, a member or a module under `src/` and quotes no statement of its module is a `false_premise` finding.

#### Scenario: The prompt-rule test reads the rule
- **WHEN** The test `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` loads `src/devops_cli/ai/tasks/roadmap_stage_verify.md`
- **THEN** It finds the false-premise rule that names a line with no statement of its module.
