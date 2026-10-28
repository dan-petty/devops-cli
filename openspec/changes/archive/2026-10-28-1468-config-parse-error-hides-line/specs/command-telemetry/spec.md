## ADDED Requirements

### Requirement: A command that reports its own failure counts once and records its exit code
When a delegated devops command reports its own failure and exits with a non-zero code, `devops_cli_command_total` SHALL count the command one time with the status `error`. The command span SHALL record that code in `cli.exit_code` and the status `error` in `cli.status`. `devops` SHALL exit with that code and SHALL log no record for the exit.

#### Scenario: A command prints its error and exits 2
- **WHEN** a delegated command prints its error and exits with the code 2
- **THEN** `devops_cli_command_total` has one point with the `command` of the command and the `status` `error`
- **AND** the command span records the `cli.exit_code` `2` and the `cli.status` `error`
- **AND** `devops` exits with the code 2, and logs no record for the exit
