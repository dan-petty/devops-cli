# Proposal

## Why

Issue #2487, part 1 of #1006: a command reported a `DevOpsCLIError` in four ways, and some commands did not report it at all.

- `OTelTyper(exit_on=<class>)` reported one error class for each app. 18 apps passed it: `gh` (10), `pr` (2), `grafana` (2), `argo`, `openspec`, `prometheus` and `valkey`.
- 41 `with exit_on_error(<class>):` blocks in 16 command modules reported one class for one block.
- 21 `except <class> as exc: ... raise typer.Exit(exc.exit_code)` sites wrote the report by hand: `commands/cloudflare.py` (9), `commands/valkey.py` (9), `commands/sandbox.py`, `commands/telemetry.py` and `commands/scan.py`. Each put its own text before the message, for example "Valkey ping failed: ".
- `commands/config.py` built a plain `typer.Typer`, so its commands did not pass through the `OTelTyper.command` wrapper.

A `DevOpsCLIError` that no block caught left the command. `_delegate` (`src/devops_cli/main.py`) logged it with a traceback and raised it again, and the process ended with status 1, not with the error's `exit_code`. For example, `devops docker sandbox --dry-run` on a refused workspace ended with a traceback.

## What Changes

- The wrapper in `OTelTyper.command` reports every `DevOpsCLIError` that a command raises: `print_error(exc.message, safe=True)`, then `typer.Exit(exc.exit_code)`, with no traceback.
- `OTelTyper.callback` gets the same report, so a callback with `invoke_without_command=True` (`devops benchmark`, `devops dashboard`) reports its errors too.
- The `exit_on` parameter of `OTelTyper`, the `exit_on_error` blocks and the 21 hand-rolled sites are deleted. `exit_on_error` becomes `_report_devops_error`, the private implementation of the wrapper. `_print_cloudflare_error` and `_print_valkey_error` have no caller left and are deleted.
- `commands/config.py` builds its app with `new_typer()`. Its commands now get the `cli.<command>` span, which holds the parameter names and no parameter value.
- The report of a Cloudflare, Valkey, sandbox-logs or SBOM error is the error's message. The text that the hand-rolled sites put before it ("Valkey ping failed: ") is gone. The exit status of each error class stays the same.
- An exception that is not a `DevOpsCLIError` propagates as before.
- The report and the exit status are behavior that a person sees, so the change carries a spec delta: the new capability `command-error-exit`.
- `ARCHITECTURE.md` and `CONTRIBUTING.md` describe the seam.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `command-error-exit`: how a command reports a `DevOpsCLIError` and which status it exits with.

## Impact

- `src/devops_cli/core/cli.py`.
- `src/devops_cli/commands/`: `ai_ingest`, `analyze`, `argo`, `benchmark`, `ci`, `cloudflare`, `config`, `dashboard`, `gh`, `grafana`, `k8s/networking`, `openspec`, `pr`, `prometheus`, `rag`, `repos`, `review`, `sandbox`, `scan`, `telemetry`, `valkey`, `vault`.
- `tests/commands/test_command_error_exit.py` (new), `tests/invariants/test_source_tree.py`, `tests/test_sandbox_lifecycle.py`, `tests/test_sandbox_logs.py`, `tests/test_valkey.py`.
- `ARCHITECTURE.md`, `CONTRIBUTING.md`.

## Feasibility

- On origin/main 0137f231, a command on `new_typer()` with no `exit_on` that raised a `DevOpsCLIError` subclass with `exit_code=7` ended with status 1 and the exception, not with a report. The new test `test_a_devops_error_ends_the_command_with_one_line_and_its_exit_status` failed with `(1, _Refused, ...)`, for a command and for a callback.
- `test_every_command_app_passes_its_commands_through_the_exit_seam` found `config: Typer`.
- An AST walk of each `exit_on_error` block and each hand-rolled site found no enclosing `try` in its function and none at the call sites of the five helpers that held one. Removing a block thus moves the report to the wrapper and changes no control flow: before, the block raised `typer.Exit`; now, the error passes up to the wrapper, which raises `typer.Exit`. Each hand-rolled `try` had one handler and no `else` or `finally`.
- `typer.Typer.callback` registers the function it is given, as `command` does, and Typer reads the signature through `functools.wraps`. The callback test passes with the wrapper.

## Existing Tool Considered

Click owns the exit: `typer.Exit` carries the status, and Click's standalone mode ends the process with it. The seam is one `except` in the wrapper that every command already passes through. A `click.ClickException` base for `DevOpsCLIError` was rejected in the design. The change deletes the `exit_on` parameter, 41 `exit_on_error` blocks, 21 hand-rolled handlers and two error printers.
