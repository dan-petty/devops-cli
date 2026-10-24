# Design

## Context

`_normalize_and_deduplicate_attributes` in `src/devops_cli/telemetry/tracer.py` copies each legacy attribute of a span to its name in the semantic conventions, through `_ATTRIBUTE_NORMALIZATION`. The command spans set `cli.command`. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- No command span holds `process.command_line`.
- A command span keeps the name of its command and its command path.

**Non-Goals:**

- The `command.line` attribute of the `telemetry.profile` span of `devops telemetry profile` (#2058).
- `process.command_args` on a command span. #1996 removed the argument values from the command spans, because a secret pattern does not find all credentials.

## Decisions

- **Delete the alias and put no other value in `process.command_line`.** The conventions give the attribute to the full command line, and they say not to assemble it for monitoring. Rejected: put the command path, such as `devops config set`, in `process.command_line`. That value is not the full command line either. Rejected: put the full command line in it. It holds the argument values, which #1996 removed.
- **Keep `cli.command` and `cli.command_path`.** The CLI span conventions have no attribute for the name or the path of a subcommand.

## Risks / Trade-offs

- [The spans in Tempo from before the change keep `process.command_line`] → Tempo deletes them at the end of its retention. No dashboard or query reads the attribute.
