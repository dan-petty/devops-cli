## ADDED Requirements

### Requirement: The time limits of a model call and a command are settings
The settings `roadmap.implement.request_timeout_seconds` and `roadmap.implement.command_timeout_seconds` SHALL set the seconds that a model call and a command may take. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 1200 and 1800, and a value below 1 SHALL be refused. A reader SHALL ask for the value when it runs.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a time limit
- **THEN** the call deadline is 1200 seconds and the command limit is 1800 seconds

#### Scenario: A config file and a variable
- **WHEN** the config file sets `command_timeout_seconds` to 90 and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS` holds 120
- **THEN** the command limit is 90 and the call deadline is 120

#### Scenario: A limit of zero
- **WHEN** the config file sets a time limit to 0
- **THEN** loading the settings fails and the message names the setting

#### Scenario: A model call
- **WHEN** the config file sets `request_timeout_seconds` to 77 and a step makes its first model request
- **THEN** the model settings of the request hold `request_timeout` 77

#### Scenario: A scoped check
- **WHEN** the config file sets `command_timeout_seconds` to 41 and the job runs the scoped checks
- **THEN** each command runs with the limit 41, and a command that runs out of time fails its check with a reason that names 41 seconds

## REMOVED Requirements

### Requirement: The time limits of the implement job are settings
**Reason**: The implement Job runs no watch of the checks, so `roadmap.implement.monitor_timeout_seconds` goes (#6559).
**Migration**: The requirement "The time limits of a model call and a command are settings" holds the rule.
