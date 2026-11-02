# Spec Delta

## MODIFIED Requirements

### Requirement: A model reply has an output cap and a call has a deadline
The agent of a step SHALL set the model settings `max_tokens` to the context window of the task divided by `CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE`, and `request_timeout` to the setting `roadmap.implement.request_timeout_seconds`. The default of the deadline SHALL be less than the timeout of the router in `k8s/llm/gateway/config.yaml`. A call that runs past the deadline SHALL end the step as stopped, and the model SHALL get no second request for it.

#### Scenario: The settings of the first request
- **WHEN** the step makes its first model request
- **THEN** the model settings of the request hold the cap, a quarter of the window, and the deadline of the setting

#### Scenario: The cap reaches the wire
- **WHEN** the agent of a step sends a request to an OpenAI chat model
- **THEN** the body of the request holds `max_completion_tokens` with the value of the cap, and no `request_timeout`

#### Scenario: The deadline is short of the router timeout
- **WHEN** a test reads `router_settings.timeout` of the gateway config
- **THEN** the default of the deadline is less than that timeout

#### Scenario: A call that never ends
- **WHEN** a model call does not answer within the deadline
- **THEN** the step reports stopped with a reason that starts with `ModelRequestTimeout: ` and holds the deadline, the model got one request, and the checkout is reset

## ADDED Requirements

### Requirement: The time limits of the implement job are settings
The settings `roadmap.implement.request_timeout_seconds`, `roadmap.implement.command_timeout_seconds` and `roadmap.implement.monitor_timeout_seconds` SHALL set the seconds that a model call, a command and the watch of the checks of a pull request may take. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 1200, 1800 and 3600, and a value below 1 SHALL be refused. A reader SHALL ask for the value when it runs.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a time limit
- **THEN** the call deadline is 1200 seconds, the command limit is 1800 seconds and the watch limit is 3600 seconds

#### Scenario: A config file and a variable
- **WHEN** the config file sets `command_timeout_seconds` to 90 and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS` holds 120
- **THEN** the command limit is 90 and the watch limit is 120

#### Scenario: A limit of zero
- **WHEN** the config file sets a time limit to 0
- **THEN** loading the settings fails and the message names the setting

#### Scenario: A model call
- **WHEN** the config file sets `request_timeout_seconds` to 77 and a step makes its first model request
- **THEN** the model settings of the request hold `request_timeout` 77

#### Scenario: A scoped check
- **WHEN** the config file sets `command_timeout_seconds` to 41 and the job runs the scoped checks
- **THEN** each command runs with the limit 41, and a command that runs out of time fails its check with a reason that names 41 seconds

#### Scenario: The watch of the checks
- **WHEN** the config file sets `monitor_timeout_seconds` to 123 and the checks of the pull request are still pending
- **THEN** the watch waits at most 123 seconds, and the reason of the stop names 123 seconds
