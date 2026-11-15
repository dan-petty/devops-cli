## ADDED Requirements

### Requirement: A command that the process runner refuses stops as a refused tool
A `SecurityError` that ends an implement run, such as the refusal of the environment of a scoped check command, SHALL give the stop the class `refused_tool`, not `ci_infra`. The action left SHALL be `wait`, and the stop SHALL keep the work of the finished groups on the branch. The rule `digest` SHALL NOT clear the stop.

#### Scenario: A scoped check command with a refused environment key
- **WHEN** the pre-push check of the scoped checks raises `SecurityError` with "Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'"
- **THEN** `implement.failure` is `refused_tool`, the stop comment names the action left `wait` and the message, and `origin` holds the commits of both groups
