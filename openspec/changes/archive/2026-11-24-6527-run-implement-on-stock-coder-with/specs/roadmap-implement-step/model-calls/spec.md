## ADDED Requirements

### Requirement: The agent of a step reads the project instructions and its skills
The agent of an implement step SHALL set `repo_context` on `Coder` and SHALL add the `Skills` capability over the skill folder of the repository.

#### Scenario: The agent of a step has the project instructions
- **WHEN** The test calls `build_agent` for an implement step.
- **THEN** It finds `repo_context` enabled and a `Skills` capability over the skill folder of the repository.

### Requirement: The agent of a step requires the project checks and wraps up at its limits
The agent of an implement step SHALL add `RequireVerification` with the project checks and `WrapUpAtLimits`.

#### Scenario: The agent of a step adds the guard capabilities
- **WHEN** The test calls `build_agent` with a sentinel project-check list.
- **THEN** It finds `RequireVerification` holding the sentinel list and `WrapUpAtLimits` in the capabilities.

### Requirement: One conversation carries the task groups of an item
The implement job SHALL pass one `Conversation` from one task group of an item to the next, and SHALL keep its compaction controls enabled.

#### Scenario: Two task groups share one conversation
- **WHEN** The test runs two task groups of one item through `run_step`.
- **THEN** It finds the messages of the first run in the `Conversation` of the second run, and the compaction controls enabled.
