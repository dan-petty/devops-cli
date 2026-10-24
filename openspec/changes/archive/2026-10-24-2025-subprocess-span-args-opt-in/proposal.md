# Proposal

## Why

Issue #2025: a subprocess span held the first eight arguments of its command in `subprocess.cmd` and `process.command_line`. A secret pattern was the only filter. Commands such as `devops uv run` and `devops gh api` pass the arguments of a person on to a program, so these arguments went to the trace backend. #1996 showed that the pattern does not find the values of 5 of the 13 secret config keys, and it removed the same data from the command span.

## What Changes

- A subprocess span (`run_subprocess` and `run_subprocess_async` in `src/devops_cli/core/process.py`) holds the name of the program (`process.executable.name` and `subprocess.bin`) and the number of its arguments (`process.args_count` and `subprocess.args_count`). By default it holds no argument value.
- The new setting `telemetry.capture_command_args` is off by default. When a person turns it on, the span holds the arguments in `process.command_args`, each argument through the secret mask.
- No subprocess span holds `subprocess.cmd` or `process.command_line`. The change deletes `_sanitize_command_for_telemetry` and the `subprocess.cmd` alias of the tracer.
- The tracer reads the setting with the rest of the telemetry section: `_resolve_telemetry_settings` returns the `TelemetryConfig`.
- `docs/TELEMETRY.md` (from `src/devops_cli/docs/generator.py`), `docs/CONFIGURATION.md` and `ARCHITECTURE.md` describe the attributes and the setting.
- The span attributes go to the trace backend, and the setting is a config option. A consumer can see both, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `subprocess-spans`: the attributes of the span of each program that devops-cli runs.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/core/process.py`, `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/config/settings.py` and `src/devops_cli/docs/generator.py`.
- Documents: `docs/TELEMETRY.md`, `docs/CONFIGURATION.md` and `ARCHITECTURE.md`.
- Tests: `tests/test_otel_command_coverage.py` adds the tests. `tests/test_process.py` and `tests/test_subprocess_env_boundary.py` lose the tests of the deleted summary. Five test modules that replace `_resolve_telemetry_settings` now give a `TelemetryConfig`.

## Feasibility

- Code: `run_subprocess` and `run_subprocess_async` put `_sanitize_command_for_telemetry(cmd)` in `subprocess.cmd` and `process.command_line`. That function kept the first eight arguments and masked them with `mask_secrets`.
- Trace backend: on 2026-10-24, the Tempo data source listed `subprocess.cmd` and `process.command_line` as span attributes. The values of `span.subprocess.cmd` for `subprocess.bin = "gh"` held the paths and the fields of `gh api` calls, such as GraphQL queries and their variables.
- Upstream: the process entities of the OpenTelemetry semantic conventions (`model/process/entities.yaml` on the main branch, read on 2026-10-24) give `process.command_args`, `process.command_line` and `process.args_count` as Opt-In, and `process.executable.name` as Recommended. The pinned `opentelemetry-semantic-conventions` 0.66b1 says of `process.command_args` and `process.command_line`: "SHOULD NOT be collected by default unless there is sanitization that excludes sensitive data". It also says not to assemble `process.command_line` for monitoring, and to use `process.command_args` instead. `process.args_count` is a number and has no note about sensitive data, so the span keeps it, as the issue asks.
- Readers: no dashboard, alert or query under `k8s/` reads `subprocess.cmd` or `process.command_line`, and no code under `src/` reads them from a span. Only the tests of the deleted summary read them.
- On the base commit, the four new test cases fail. With the default settings, the span held `process.command_line` and `subprocess.cmd`, and an exported payload held the credential. With the setting on, the span held no `process.command_args`.

## Existing Tool Considered

The OpenTelemetry semantic conventions name the attributes, and the change uses their names: `process.executable.name`, `process.args_count` and `process.command_args`. The tests take the names from the constants of `opentelemetry-semantic-conventions`, which the project pins. No OpenTelemetry instrumentation traces Python subprocesses: PyPI has no `opentelemetry-instrumentation-subprocess` (HTTP 404 on 2026-10-24). The tracer of devops-cli makes the spans, so the setting is one field that the tracer reads. Nothing is built. The change deletes `_sanitize_command_for_telemetry`, the `subprocess.cmd` alias of `_ATTRIBUTE_NORMALIZATION`, and their two tests.
