# Spec Delta

## Purpose

The telemetry that a devops command sends: the command spans with their attributes and events, and the command counter `devops_cli_command_total`.

## ADDED Requirements

### Requirement: A usage error records its class and exit code and no message
When a devops command stops on a usage error of Typer, the command span SHALL record the class of the error in `error.type` and the exit code in `cli.exit_code`. No exported span attribute, span event, span status or resource attribute SHALL hold the message of the error.

#### Scenario: An unexpected extra argument
- **WHEN** a person runs `devops config set <key> <value> <extra>`
- **THEN** the command span records the `error.type` `UsageError` and the `cli.exit_code` `2`
- **AND** no exported payload holds `<extra>`

#### Scenario: A command raises a bad parameter
- **WHEN** a person runs `devops ai gateway tune --concurrency <value>` with a value that is not a list of integers
- **THEN** the command span records the `error.type` `BadParameter` and the `cli.exit_code` `2`
- **AND** no exported payload holds `<value>`

### Requirement: A usage error counts as a failed command
`devops_cli_command_total` SHALL count a command that stops on a usage error of Typer one time, with the status `error`.

#### Scenario: An unexpected extra argument is counted
- **WHEN** a person runs `devops config set <key> <value> <extra>`
- **THEN** `devops_cli_command_total` has one point with the `command` `config` and the `status` `error`

### Requirement: A usage error shows the error box of Typer
A command that stops on a usage error SHALL show the error box of Typer with the message of the error, and SHALL exit with the exit code of the error.

#### Scenario: The person sees the error
- **WHEN** a person runs `devops config set <key> <value> <extra>`
- **THEN** the output shows the error box of Typer with `Got unexpected extra argument`
- **AND** the command exits with the code `2`
