# Design

## The seam

`OTelTyper.command` already wraps each command in `_execute_traced_cli_command`, which records the span and the metric and raises the error again. The wrapper now runs that inside `_report_devops_error`, so the span records the failure first and the report comes after it. This was the behavior of `exit_on=` for one class, and it is now the behavior for every `DevOpsCLIError`.

`OTelTyper.callback` wraps the callback in `_report_devops_error` only, with no span: a group callback runs before each of its commands, and the command has its own span.

## Rejected alternatives

- **`DevOpsCLIError` as a `click.ClickException`.** Click would print it and exit with its `exit_code` with no wrapper. But Click prints "Error: <message>" in its own format, which changes every error line, and Rich markup in a message would not be escaped. The exception package would also depend on the CLI framework, and the MCP server and the Service raise the same classes.
- **A top-level handler in `_delegate`.** It runs only for a command reached through `devops <group>`, not for a command app that a test or `devops_cli.main.app` invokes, and the span of the command would end before the report. The wrapper covers both.
- **Keep `exit_on=` and make `DevOpsCLIError` the default.** Two ways to say the same thing stay, and an app could still narrow the class and let the rest escape.
- **Keep the per-site text ("Valkey ping failed: ").** Each site would need its own handler again. The error's message names the failure, and #1006 asks for one report.
