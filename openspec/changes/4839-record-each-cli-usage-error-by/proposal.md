# Proposal: #4839

## Why

Closes #4839. No record shows which names people and agents try and fail on the devops CLI. The command span keeps only the class of a usage error (#2024), and `devops_cli_command_total` counts it as `error`. A help query and a dry run keep nothing. A study of 1,737 usage errors had to read agent transcripts and logs by hand. A record of each usage error by kind and name lets a later analysis find missing flags, commands and aliases.

## What Changes

- The root group of the CLI records each usage error of Click and raises it again. The error box of Typer and exit code 2 do not change. A help query, a dry run and an MCP tool call go through the same group.
- Click's error types give the kind: `unknown_option`, `missing_argument`, `missing_option`, `bad_value`, `option_usage` and `other`. Click raises a plain `UsageError` for an unknown command word and for an extra argument, so the group and command classes of `new_typer()` mark these two kinds where they occur.
- One record goes to three sinks: the counter `devops_cli_usage_error_total` (labels `kind`, `command_path` and `caller`), the log record `cli_usage_error`, and one JSON line of `usage-errors.jsonl` under the user data root. The typed name and Click's suggestion go only to the log record and the ledger.
- A word that is not in the form of a CLI name is recorded as `<value>`. No record holds the message, an argument value or the command line.
- The caller is `mcp`, `agent`, `ci` or `person`. The implement job sets `AI_AGENT=devops-implement`.
- The new setting `telemetry.usage_ledger` (default `true`) turns the ledger off. A ledger write error gives one warning.
- The dry-run branch of a delegated command raises a usage error to the root group. Thus the dry run shows the same error box as a live run.
- This change alters observable behavior (a new metric, log record, file and setting), so it carries a spec delta.

## Capabilities

- `command-telemetry`: ADDED requirements for the usage-error record, its privacy and its caller.

## Impact

- New runtime dependency `detect-agent==0.6.0` (Apache-2.0, no dependencies of its own).
- New file `usage-errors.jsonl` under the user data root, at most 4 MiB with its rotated files.
- The generated `docs/TELEMETRY.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md` and README tables get the metric and the setting.
- The change fits one pull request.

## Feasibility

- Typer 0.27.2 (installed) vendors Click as `typer._click`. `typer/_click/exceptions.py` defines `NoSuchOption`, `MissingParameter`, `BadParameter`, `BadOptionUsage`, `BadArgumentUsage` and `NoArgsIsHelpError`. `typer.core._main` catches `ClickException` from `make_context` and `invoke` of the root group. Thus a root group subclass that overrides those two methods sees every usage error before Typer shows it.
- `TyperGroup.resolve_command` and `_click.core.Command.parse_args` raise a plain `UsageError` through `ctx.fail` for an unknown command and for extra arguments. The message is the only other trace, so the two classes mark the error where it occurs.
- `_delegate` runs each command module with `standalone_mode=False`, so its usage error goes up to the root group. The MCP dispatcher runs the root app through `CliRunner` on a thread of its own. A context variable does not pass to a new thread, so the thread sets it.
- Markers, read on this host on 2026-11-12: Claude Code sets `AI_AGENT` (value `claude-code_<version>_agent`), `CLAUDECODE` and `CLAUDE_CODE_ENTRYPOINT`. A shell of Kilo gets `AGENT`, `KILO` and `OPENCODE`. Antigravity did not run on this host, and its logs hold no marker name. The agent table of `detect_agent` 0.6.0 names `ANTIGRAVITY_AGENT` and `ANTIGRAVITY_CLI_ALIAS`.
- `mask_secrets` does not change a random 32-character hex or URL-safe token. Thus the name form, and not the secret mask alone, keeps such a token out of the record.

## Existing Tool Considered

- `detect_agent` 0.6.0 on PyPI (Together AI, Apache-2.0, released 2026-08-12, repository active on 2026-10-20) is a port of Vercel's `@vercel/detect-agent`. It reads `AI_AGENT` first and then a published table of tool markers. The change uses it for the agent tool. It names Kilo `open_code`, so one line names Kilo when `KILO` is also set.
- Click's own error types give the kind, and `difflib`, which Typer also uses, gives the close match. The stdlib `RotatingFileHandler` writes and rotates the ledger. The `OtlpExporter` seam (#1319) and `emit()` send the counter, and the OTLP log bridge sends the log record.
- No open tool records the usage errors of a Click application. The hook is two short classes on these parts. The change deletes the `click.ClickException` handler of the dry-run branch, which showed the error in a second form.
