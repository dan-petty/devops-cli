## ADDED Requirements

### Requirement: Event of a changed deferred section
The comment step of refine SHALL post the event comment when the deferred items of the round differ from the recorded `RefineRecordKey.DEFERRED`, also when its text equals the comment of the round before.

#### Scenario: A second deferred change with no comment between
- **WHEN** the record holds deferred issue `#21`, the round files deferred issue `#22`, its event text equals the text of the round before, and no comment follows that text
- **THEN** the store posts one more event comment and the event comment holds no `#22`

### Requirement: Module docstring line limit of refine
Each line of the module docstring of `src/devops_cli/roadmap/refine/refine.py` MUST have at most 100 characters.

#### Scenario: The module docstring of refine
- **WHEN** a test inspects `devops_cli.roadmap.refine.refine.__doc__` line by line
- **THEN** every line has at most 100 characters
