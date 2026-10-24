# Proposal

## Why

Issue #2024: a usage error sent the text that the person typed to the trace backend, and the command counter did not count it. #1996 removed the argument values from the command spans, but the message of a usage error quotes an argument, such as `Got unexpected extra argument (<value>)`. An argument can be a credential: a person who types `devops config set <key> <value>` with a space in the value gets this error.

Two defects caused this:

- The generic exception handling of the tracer put the message of each error in `error.message` and in the span status. A traced command (`_record_cli_failure` in `src/devops_cli/core/cli.py`) also put it in `cli.error`, which the tracer exports as `error.message`.
- `_delegate` in `src/devops_cli/main.py` caught `click.ClickException`. Typer 0.27 has its own copy of Click, and its usage errors do not come from `click.ClickException`. So the error went out of `_delegate` without a point in `devops_cli_command_total`.

## What Changes

- `_delegate` catches `typer.TyperException`, the public base class of the usage errors of Typer (`UsageError`, `BadParameter`, `NoSuchOption` and the others). It records `cli.status` `error`, the exit code and the duration on the command span, adds a `command_failed` event with the class and no message, counts the command in `devops_cli_command_total` with the status `error`, and raises the error again. The root app then shows the error box of Typer and exits with the exit code of the error, as before.
- The tracer records the class (`error.type`) and the exit code (`cli.exit_code`, `process.exit.code`) of a `typer.TyperException`, and no `error.message`. The span status message is `<class>(exit_code=<code>)`.
- A traced command that a `typer.TyperException` stops, such as a `typer.BadParameter` that the command raises, records no `cli.error`, and its `subcommand_failed` event holds the class and no message.
- The `click.ClickException` branch of `_delegate` goes. No devops-cli code raises that class, and its `exc.show()` printed plain text in place of the error box of Typer.
- `docs/TELEMETRY.md` tells how the command spans record a usage error.
- The span attributes and the command counter are what the trace backend and Prometheus receive, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `command-telemetry`: the spans and the command counter that a devops command sends.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/main.py` (`_delegate`), `src/devops_cli/telemetry/tracer.py` (`_populate_exception_span_attributes`) and `src/devops_cli/core/cli.py` (`_record_cli_failure`).
- Documentation: `docs/TELEMETRY.md`, from `src/devops_cli/docs/generator.py`.
- Tests: `tests/test_otel_command_coverage.py`.
- No dashboard, alert or query under `k8s/monitoring/` reads the message of a usage error.

## Feasibility

- `pyproject.toml` pins `typer==0.27.2` and `click==8.5.0`. In the installed Typer, the method resolution order of `typer._click.exceptions.UsageError` is `UsageError`, `ClickException`, `TyperException`, `Exception`, and `issubclass(UsageError, click.ClickException)` is `False`. `typer.TyperException` is a public name, and in Typer only `typer._click.exceptions.ClickException` comes from it. `src/devops_cli/core/command_resolver.py` already catches the usage errors through `typer.TyperException`.
- `typer.core._main` raises a `ClickException` again when `standalone_mode` is `False`, as `_delegate` calls it. In standalone mode, as the root app runs, it shows the error with `rich_utils.rich_format_error` (the error box) and exits with `exit_code`.
- `OTelTelemetryClient.span` calls `_populate_exception_span_attributes` for each error with an exit code that is not 0. That method put `mask_secrets(str(exc))` in `error.message` and in the status message.
- On the base commit, the new tests in `tests/test_otel_command_coverage.py` found the typed credential in the exported payloads, found no `cli.status` on the command span, and found no point of `devops_cli_command_total`, for an extra argument to `devops config set` and for a `typer.BadParameter` from `devops ai gateway tune --concurrency <value>`.
- `devops config show <extra>` shows the error box of Typer and exits with 2, on the base and after the change.

## Existing Tool Considered

Typer shows a usage error to the person, and `typer.TyperException` is the public class that it gives for its usage errors. OpenTelemetry gives `error.type` for the class of an error. The change uses both and builds nothing. It deletes the `click.ClickException` branch of `_delegate`, with its `exc.show()` and `typer.Exit`, and the `import click` of `src/devops_cli/main.py`.
