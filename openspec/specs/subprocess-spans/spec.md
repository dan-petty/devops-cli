# subprocess-spans Specification

## Purpose
The attributes of the OpenTelemetry span of each program that devops-cli runs, and the setting that adds the arguments of the program to the span.

## Requirements

### Requirement: A subprocess span holds no argument value by default
The span of each program that `run_subprocess` or `run_subprocess_async` runs SHALL hold the name of the program in `process.executable.name` and the number of its arguments, the program included, in `process.args_count`. While `telemetry.capture_command_args` is off, which is the default, the span SHALL hold no `process.command_args`, no `process.command_line` and no `subprocess.cmd`, and no payload that the tracer exports SHALL hold an argument value.

#### Scenario: A credential that a person passes on to uv
- **WHEN** devops-cli runs `uv run devops config set cloudflare.tunnel_token <credential>` with telemetry export on and the default settings
- **THEN** the span `subprocess.uv` holds `process.executable.name` `uv` and `process.args_count` 7
- **AND** the span holds no `process.command_args`, no `process.command_line` and no `subprocess.cmd`
- **AND** no exported payload holds the credential

### Requirement: A person can turn on the arguments
While `telemetry.capture_command_args` is on, the span SHALL hold each argument of the program, the program first, in `process.command_args`, each argument through the secret mask. The span SHALL hold no `process.command_line`.

#### Scenario: The setting is on
- **WHEN** `telemetry.capture_command_args` is true and devops-cli runs uv with a GitHub token as its last argument
- **THEN** `process.command_args` holds each argument, and the secret mask replaces the token
- **AND** the span holds no `process.command_line` and no `subprocess.cmd`
