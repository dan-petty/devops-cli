## ADDED Requirements

### Requirement: The hourly budget has a variable and a description
`DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` SHALL set `service.github_requests_per_hour`, and `devops config show` and `devops config env` SHALL list the setting and the variable, each with a description.

#### Scenario: The variable sets the budget
- **WHEN** `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` is `2000` and the settings load
- **THEN** `service.github_requests_per_hour` is 2000

#### Scenario: A budget of zero
- **WHEN** `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` is `0` and the settings load
- **THEN** the load stops with an error that names the variable

#### Scenario: The setting is listed
- **WHEN** `devops config show --json` runs
- **THEN** a row has the key `service.github_requests_per_hour`
