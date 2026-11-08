## ADDED Requirements

### Requirement: A test-only other group names its test function
The stage plan SHALL refuse an other task group whose every changed path is under tests when the implementation of the group names no test function in a code span. A code span names a test function when its last segment, after the last `::` when it holds one, starts with `test_`, with optional parentheses.

#### Scenario: Conditional test-only group
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds no code span with a `test_` function
- **THEN** the returned problems hold the refusal sentence for that group

#### Scenario: Named test function
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds a code span with `test_conditional_group`
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Named test function after a path
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds a code span with `tests/roadmap/stage/test_roadmap_stage_content.py::test_conditional_group`
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Group with a source path
- **WHEN** `content_problems` reads an other group whose `changes` lists `tests/roadmap/stage/test_roadmap_stage_content.py` and `src/devops_cli/roadmap/stage/stage_change.py` and whose `implementation` names no test function
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Refusal names the group
- **WHEN** `content_problems` refuses an other group with the title `Keep the roadmap stage tests green`
- **THEN** the returned sentence holds `Keep the roadmap stage tests green`

### Requirement: The planner prompt asks for one exact change and its test
The stage prompt SHALL state that a task group gives one exact change and names the failing test that it updates in a code span.

#### Scenario: The stage prompt loads
- **WHEN** the stage job loads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt text states that a group gives one exact change and names the failing test in a code span
