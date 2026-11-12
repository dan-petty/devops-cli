# Design

## Decisions

- **One hook at the root group.** `UsageRecordingGroup` (`core/cli.py`) is the `cls` of the root app. It wraps `make_context` and `invoke`, records each `UsageError` except `NoArgsIsHelpError`, and raises it again. Only the root group records, so one error gives one record, also when it comes up from a delegated module.
- **Two tags for the plain `UsageError`.** `new_typer()` gives each group `UsageTaggedGroup`, whose `resolve_command` marks an unknown command word with the typed word and the first `difflib` match. `OTelTyper.command` gives each command `UsageTaggedCommand`, whose `parse_args` marks an extra argument. No code reads the message of an error.
- **The command path of a parse error.** The parser of Click raises `BadOptionUsage` with no context, and `Context.invoke` then gives it the context of the parent group: `devops pr list --limit` showed the path `pr`. The `parse_args` of both classes marks the error with the command path of the command that parses. The error keeps its context, so the error box does not change.
- **Command path.** The command path of the error's context without the program name `devops`, so a live run, a dry run and an MCP call give the same path, such as `pr view`. The root group gives an empty path.
- **Name form.** A recorded name is a short option of one character, or lowercase words of letters and digits of at most 20 characters, joined by `-` or `_`, with an optional `-` or `--` before them, at most 40 characters, which `mask_secrets` does not change. Any other word is `<value>`. A random token, a number and a path do not have this form.
- **Sinks.** The counter has the labels `kind`, `command_path` and `caller` only: a bounded set. The log record `cli_usage_error` (logger `devops_cli.usage`, level WARNING) has the fields as `usage.*` attributes, and a `NullHandler` keeps `logging.lastResort` from printing it. The ledger is one JSON line for each error, written through `RotatingFileHandler` (1 MiB, 3 backups) that opens and closes for each record.
- **Caller.** `mcp` when the MCP dispatcher thread set the context variable, else `agent` when `detect_agent` finds an agent, else `ci` when `CI` or `GITHUB_ACTIONS` is set, else `person`. The agent tool is computed on its own, so an MCP call can also name its tool.
- **Settings that cannot load.** The ledger then stays off, as export does (#956): such settings can be the ones that turn it off.
- **Dry run.** The dry-run branch lets the usage error go up to the root group. The dry run then shows the error box of Typer, the same as a live run.

## Rejected alternatives

- **Parse the message of the error.** The message quotes what the caller typed, such as `Got unexpected extra argument (<value>)` (#2024). Click's types and the two tags give the kind with no text.
- **A data table of agent markers of our own.** `detect_agent` 0.6.0 publishes the same table as Vercel's package and is maintained (Feasibility). A table of our own would need its own updates.
- **Name the parameter by its option flag (`--summary`).** The plan of #4839 records `param.name`, which every parameter has. An option flag would need a second rule for arguments.
- **One long-lived file handler.** The user data root can change between calls in one process (an MCP server, a test run), and a handler kept open writes to the old path. A handler for each record costs one open and close on an error path.
- **Keep the `ClickException` handler of the dry-run branch.** It printed the error in Click's plain form and stopped the error before the root group, so the dry run left no record.
