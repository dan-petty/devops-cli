# command-telemetry Specification

## Purpose
The telemetry that a devops command sends: the command spans with their attributes and events, and the command counter `devops_cli_command_total`.

## Requirements

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

### Requirement: A command span holds no process.command_line
Each command span SHALL hold the name of its command in `cli.command`, and SHALL hold no `process.command_line`. The span of the command that runs SHALL hold its command path in `cli.command_path`.

#### Scenario: A person runs a command of a command group
- **WHEN** a person runs `devops <group> set <key> <value>` with telemetry export on
- **THEN** the span `cli.<group>` holds the `cli.command` `<group>`, and the span `cli.set` holds the `cli.command` `set` and the `cli.command_path` `devops <group> set`
- **AND** neither span holds `process.command_line`

### Requirement: The profile span names the profiled command and holds no argument value
The `telemetry.profile` span of `devops telemetry profile` SHALL hold the command path of the profiled command in `cli.command_path` and the number of its words that are not command names in `cli.args_count`. The span SHALL hold no `command.line` and no argument value, also while `telemetry.capture_command_args` is on. While the setting is on, the subprocess span under the profile span SHALL hold the arguments of the profiled command in `process.command_args`.

#### Scenario: A credential in the profiled command line
- **WHEN** a person runs `devops telemetry profile "devops config set cloudflare.tunnel_token <credential>"` with telemetry export on and the default settings
- **THEN** the `telemetry.profile` span holds `cli.command_path` `devops config set` and `cli.args_count` 2
- **AND** the span holds no `command.line`
- **AND** no exported payload holds the credential

#### Scenario: The person turns on the arguments
- **WHEN** `telemetry.capture_command_args` is true and a person profiles the same command line
- **THEN** the `telemetry.profile` span holds no argument value
- **AND** the subprocess span under the profile span holds the arguments of the profiled command in `process.command_args`

### Requirement: Warning and error logs are exported via OTLP with trace correlation
When telemetry is enabled, log records of level WARNING and above SHALL be exported to the collector's `/v1/logs` endpoint carrying the active `trace_id` and `span_id`. No exported log payload SHALL contain prompt or reply text.

#### Scenario: A warning is logged during command execution
- **WHEN** a command executes an active trace span and emits a warning log
- **THEN** the log record is exported to `/v1/logs` with `severityText` `WARN`
- **AND** the log record carries the active `traceId` and `spanId`
- **AND** the payload contains no prompt or reply preview text

#### Scenario: A failed command logs an error with trace context
- **WHEN** a command fails with an unhandled exception
- **THEN** an error log is exported to `/v1/logs` with `severityText` `ERROR`
- **AND** the log record carries the active `traceId` and `spanId`

### Requirement: Loki datasource configures derived trace link to Tempo
The Grafana Loki datasource in `k8s/monitoring/grafana-values.yaml` SHALL configure a derived field targeting the Tempo datasource (`datasourceUid: tempo`) matching trace IDs in log entries.

#### Scenario: Derived field is configured in Loki datasource
- **WHEN** the Loki datasource configuration in `k8s/monitoring/grafana-values.yaml` is read
- **THEN** `jsonData.derivedFields` contains an entry targeting `datasourceUid` `tempo`
- **AND** `matcherRegex` matches trace ID values in logs

### Requirement: devops-cli dashboard includes an error stream panel
The `k8s/monitoring/dashboards/devops-cli.json` dashboard SHALL include a logs panel displaying the error and warning stream from Loki for `devops-cli`.

#### Scenario: Error stream panel is present in the dashboard
- **WHEN** the panels of `devops-cli.json` are read
- **THEN** a panel of type `logs` with title "devops-cli Error Stream" is present
- **AND** the panel targets the `loki` datasource

### Requirement: A command that reports its own failure counts once and records its exit code
When a delegated devops command reports its own failure and exits with a non-zero code, `devops_cli_command_total` SHALL count the command one time with the status `error`. The command span SHALL record that code in `cli.exit_code` and the status `error` in `cli.status`. `devops` SHALL exit with that code and SHALL log no record for the exit.

#### Scenario: A command prints its error and exits 2
- **WHEN** a delegated command prints its error and exits with the code 2
- **THEN** `devops_cli_command_total` has one point with the `command` of the command and the `status` `error`
- **AND** the command span records the `cli.exit_code` `2` and the `cli.status` `error`
- **AND** `devops` exits with the code 2, and logs no record for the exit
