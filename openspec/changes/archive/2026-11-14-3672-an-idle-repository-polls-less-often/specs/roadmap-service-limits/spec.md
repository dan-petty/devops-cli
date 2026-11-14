## ADDED Requirements

### Requirement: A repository with no open work polls at the idle interval
The configuration SHALL define `service.poll_interval_idle_seconds` in the `service` section with a default of 600 seconds, and SHALL refuse a value below `service.poll_interval_seconds` with an error that names both settings. The Service SHALL give a repository with no open issue and no open pull request the idle interval, and one with open work the normal interval. A webhook delivery SHALL clear the idle state and start the update at once.

#### Scenario: The default idle interval
- **WHEN** the configuration loads with no value for `service.poll_interval_idle_seconds`
- **THEN** the loaded value is 600 seconds

#### Scenario: An idle interval below the normal one
- **WHEN** the configuration sets `poll_interval_seconds` to 120 and `poll_interval_idle_seconds` to 60
- **THEN** loading the configuration fails with an error that names both settings

#### Scenario: A repository with no open work
- **WHEN** the repository has zero open issues and zero open pull requests, and the idle interval is 600 seconds
- **THEN** the next poll for the repository is due after 600 seconds

#### Scenario: A repository with open work
- **WHEN** the repository has one open issue or one open pull request, and the normal interval is 300 seconds
- **THEN** the next poll for the repository is due after 300 seconds

#### Scenario: A webhook on an idle repository
- **WHEN** a webhook delivery arrives for a repository in the idle state
- **THEN** the idle state ends and the update starts at once
