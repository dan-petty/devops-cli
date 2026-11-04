## ADDED Requirements

### Requirement: A test-only other group names its test function
The stage plan SHALL refuse an other task group whose every changed path is under tests when the implementation of the group names no test function in a code span.

#### Scenario: Conditional test-only group
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/test_roadmap_stage_content.py` and whose `implementation` holds no code span with a `test_` function
- **THEN** the returned problems hold the refusal sentence for that group

#### Scenario: Named test function
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/test_roadmap_stage_content.py` and whose `implementation` holds a code span with `test_conditional_group`
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Group with a source path
- **WHEN** `content_problems` reads an other group whose `changes` lists `tests/roadmap/test_roadmap_stage_content.py` and `src/devops_cli/roadmap/stage_change.py` and whose `implementation` names no test function
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Refusal names the group
- **WHEN** `content_problems` refuses an other group with the title `Keep the roadmap stage tests green`
- **THEN** the returned sentence holds `Keep the roadmap stage tests green`
