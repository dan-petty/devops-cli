## ADDED Requirements

### Requirement: The startup-import row probes a config with decision modes
The `startup-imports` row SHALL run `devops config get ai.provider` in a fresh interpreter with a config file that sets `roadmap.decisions`, and SHALL fail when that run imports `pydantic_ai` or its settings do not hold the modes of the file.

#### Scenario: A decisions probe that imports pydantic_ai
- **WHEN** the decisions probe prints that `pydantic_ai` is loaded
- **THEN** the row names the probe and its value as a problem
