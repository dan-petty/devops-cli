# Spec Delta

## ADDED Requirements

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
