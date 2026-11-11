## MODIFIED Requirements

### Requirement: A test-only other group names its test function
The stage plan SHALL refuse an other task group whose every changed path is a test module under tests when the implementation of the group names no test function in a code span, and SHALL accept the group when one changed path under tests is no test module. A test module is a path under tests whose base name starts with `test_` and ends with `.py`, the form that `devops ci test` runs as a test module. A code span names a test function when its last segment, after the last `::` when it holds one, starts with `test_`, with optional parentheses.

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

#### Scenario: Test helper group
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/support/builders.py` and whose `implementation` names no test function
- **THEN** the returned problems hold no refusal sentence for that group

#### Scenario: Test file path with no function
- **WHEN** `content_problems` reads a proposal with an other group whose `changes` lists only `tests/roadmap/stage/test_roadmap_stage_content.py` and whose `implementation` holds the code span `tests/roadmap/stage/test_roadmap_stage_content.py` and no other code span
- **THEN** the returned problems hold the refusal sentence for that group
