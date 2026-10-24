# Design

## Context

`run_subprocess` and `run_subprocess_async` in `src/devops_cli/core/process.py` open a `subprocess.<program>` span for each program that devops-cli runs. The tracer in `src/devops_cli/telemetry/tracer.py` exports the span to the trace backend. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- By default, a subprocess span holds the program and the number of its arguments, and no argument value.
- A person can turn on the arguments for a debugging session.

**Non-Goals:**

- The `command.line` attribute of the `telemetry.profile` span of `devops telemetry profile` (a follow-up issue).
- The `cli.command` alias to `process.command_line` on the command spans (a follow-up issue).
- An environment variable for the setting. A person turns it on and off with `devops config set`.

## Decisions

- **The setting records `process.command_args`, not `process.command_line`.** The conventions say not to assemble `process.command_line` for monitoring, and to use `process.command_args` instead (`opentelemetry-semantic-conventions` 0.66b1). Rejected: keep `process.command_line` behind the setting.
- **Each argument goes through the secret mask when the setting is on.** The mask removes the tokens that it knows, and costs nothing for a person who debugs. Rejected: record the raw arguments. Rejected: keep the bounds of the deleted summary (eight arguments, 60 characters each, and no value after `--body` or `--comment`). The conventions define `process.command_args` as all the arguments, and a person who turns on the setting asks for them.
- **The tracer reads the setting once, with the rest of the telemetry section.** `_resolve_telemetry_settings` returns the `TelemetryConfig`, and `get_tracer` gives `capture_command_args` to the tracer. Rejected: read the settings in each subprocess run. The tracer already loads the telemetry section when it is made, and a second read in `core.process` would repeat its fallback for settings that cannot load (#956). Rejected: a tuple of three values. A model names each field, and the tests that replace the resolver give a `TelemetryConfig`.
- **The span keeps the `subprocess.*` names next to the convention names.** `subprocess.bin`, `subprocess.cwd` and `subprocess.exit_code` already sit next to `process.executable.name`, `process.working_directory` and `process.exit.code`. `process.args_count` joins `subprocess.args_count` in the same way.

## Risks / Trade-offs

- [The secret mask does not find all credentials] → The setting is off by default, and `docs/TELEMETRY.md` tells a person to turn it off after the session.
- [A long argument makes a large span when the setting is on] → This occurs only while a person has the setting on.
