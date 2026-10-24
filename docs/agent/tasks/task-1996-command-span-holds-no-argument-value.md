# Task: The Command Span Holds No Argument Value (#1996)

**Issue**: [#1996](https://github.com/dan-petty/devops-cli/issues/1996)
**Scope**: `type/security`, `scope/telemetry`
**Feasibility**: Verified against the code, the live trace backend and the upstream conventions. `_delegate` in `src/devops_cli/main.py` put `" ".join(effective_args)` in the span attribute `cli.args`, with no mask. `OTelTelemetryClient` in `src/devops_cli/telemetry/tracer.py` put `mask_secrets(" ".join(sys.argv))` in the resource attribute `process.command_line` of every trace payload. The Tempo data source lists `cli.args` as a span attribute and `process.command_line` as a resource attribute, so both reach the backend. `mask_secrets` finds secrets by pattern: for `devops config set <key> correct-horse-battery-staple`, it keeps the value for 5 of the 13 secret keys (`cloudflare.api_token`, `cloudflare.tunnel_token`, `runs.index_password`, `service.webhook_secrets`, `telemetry.logfire_token`). The OpenTelemetry semantic conventions give `process.command_args` and `process.command_line` as Opt-In, and say that a producer "SHOULD NOT" collect them by default "unless there is sanitization that excludes sensitive data". No dashboard, alert or query under `k8s/monitoring/` reads `cli.args` or `process.command_line`.

## Description

A command span recorded each argument, so a credential given to `devops config set` went to the trace backend. The command span of `_delegate` now holds the command and the number of arguments (`cli.args_count`), and no argument. The resource holds no `process.command_line`. The span of the command that runs (`_execute_traced_cli_command` in `src/devops_cli/core/cli.py`) now holds Click's command path (`cli.command_path`, such as `devops config set`), which holds the command names and no argument. Thus the trace still names the command that ran.

## Acceptance Criteria

- [x] A test runs `set <key> <credential>` through `_delegate` with telemetry export captured, and no exported span attribute, event or resource attribute holds the credential (`test_no_exported_attribute_holds_an_argument_value` in `tests/test_otel_command_coverage.py`). The test fails on `origin/main`, and it fails with only the `cli.args` change, because the resource also held the credential.
- [x] The spans keep the command, the number of arguments and the command path (`test_the_command_spans_keep_the_command_path_and_the_argument_count`).
- [x] No dashboard query under `k8s/monitoring/` reads `cli.args`. No change was necessary.

## Deliverables

- [x] `src/devops_cli/main.py`: the command span has no `cli.args`.
- [x] `src/devops_cli/telemetry/tracer.py`: the resource has no `process.command_line`.
- [x] `src/devops_cli/core/cli.py`: the span of the command that runs holds `cli.command_path`.
- [x] `docs/TELEMETRY.md` (from `src/devops_cli/docs/generator.py`) and `ARCHITECTURE.md` say which attributes describe the command line, and that no attribute holds an argument value.
- The message of a usage error can quote an argument (Click's "Got unexpected extra argument (<value>)"), and the tracer records it in `error.message`. `except click.ClickException` in `_delegate` does not catch the errors Typer 0.27 raises, because Typer has its own copy of Click, so a usage error also counts no `devops_cli_command_total` with status `error`. Moved to #2024.
- A subprocess span holds the first eight arguments of the command it runs (`subprocess.cmd` and `process.command_line`, through a secret pattern). A command that passes the arguments of a person to a program, such as `devops uv run` or `devops gh api`, puts them there. Moved to #2025.
