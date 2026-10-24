# Design

## Context

`_delegate` in `src/devops_cli/main.py` opens the command span of each delegated command and calls the Typer app of the command with `standalone_mode=False`. The root app in the same file runs in standalone mode and shows the errors that come out of `_delegate`. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- No span of a usage error holds its message. The spans hold its class and its exit code.
- `devops_cli_command_total` counts a usage error with the status `error`.
- The person sees the same error box and exit code as before.

**Non-Goals:**

- The arguments in a subprocess span (#2025).

## Decisions

- **Catch `typer.TyperException`.** It is the public base class of the usage errors of Typer, and `src/devops_cli/core/command_resolver.py` already catches them through it. Rejected: `typer._click.exceptions.ClickException`, a private module path that can move in a Typer release.
- **Raise the error again in `_delegate`.** The root app then shows the error box of Typer. Rejected: `exc.show()` and `typer.Exit`, as the old branch did. `exc.show()` prints plain text, not the error box.
- **The tracer leaves out the message.** The error goes through the generic exception handling of the tracer when `_delegate` raises it again, and also when a traced command raises it. Rejected: catch the error in the span and raise it after the span closes. The span then ends with the status `OK`, because `SpanHandle.set_status` sets only attributes, not the span status.
- **No `click.ClickException` branch.** No devops-cli code raises that class, and the root app of Typer does not show it.

## Risks / Trade-offs

- [A trace no longer shows which argument was wrong] → The person sees the message in the error box. The command span keeps the command, the class and the exit code.
