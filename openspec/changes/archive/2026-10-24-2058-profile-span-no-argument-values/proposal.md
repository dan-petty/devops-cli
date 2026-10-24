# Proposal

## Why

Issue #2058: the `telemetry.profile` span of `devops telemetry profile` (`_run_profiled_command` in `src/devops_cli/commands/telemetry.py`) held the profiled command line in `command.line`, exactly as the person typed it, with each argument value. A credential given to the profiled command, such as `devops telemetry profile "devops config set <key> <value>"`, went to the trace backend. #1996, #2024 and #2025 removed the same data from the command spans, the usage errors and the subprocess spans.

## What Changes

- The `telemetry.profile` span holds the command path of the profiled command in `cli.command_path`, such as `devops config set`, and the number of its other words in `cli.args_count`. It holds no `command.line` and no argument value.
- The new function `resolve_command_path` in `src/devops_cli/core/command_resolver.py` gives the command path and the count. It walks the command tree from the module app that the first word names, as `main._delegate` does, with the walk of Typer's own shell completion.
- The profile span holds no argument value also when `telemetry.capture_command_args` is on. The profiled command runs through `run_subprocess`, so with the setting on, its subprocess span under the profile span already holds the arguments in `process.command_args`. Thus one setting and one span record the arguments of a program that devops-cli runs.
- `docs/TELEMETRY.md` (from `src/devops_cli/docs/generator.py`) describes the profile span.
- The span attributes go to the trace backend, so a consumer sees them, and the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: adds the requirement for the profile span of `devops telemetry profile`.

## Impact

- Code: `src/devops_cli/commands/telemetry.py` (`_run_profiled_command`), `src/devops_cli/core/command_resolver.py` (`resolve_command_path`) and `src/devops_cli/docs/generator.py`.
- Documentation: `docs/TELEMETRY.md`.
- Tests: `tests/test_otel_command_coverage.py` and `tests/test_docs_command_resolver.py`.
- No dashboard, alert or query under `k8s/` reads `command.line`, and no code under `src/` reads it from a span.

## Feasibility

- Code: on the base commit, `_run_profiled_command` opened `trace_span("telemetry.profile", attributes={"command.line": command})`, with `command` the text that the person typed.
- Tests: on the base commit, the new test in `tests/test_otel_command_coverage.py` runs `devops telemetry profile "devops config set cloudflare.tunnel_token <credential>"` with the export captured. The profile span held `command.line` and no `cli.command_path`, and an exported payload held the credential.
- Trace backend: on 2026-10-24, a TraceQL search of the Tempo data source for `{ name = "telemetry.profile" }` over the last 7 days found no trace, and `span.command.line` had no value. No reader depends on the attribute.
- Upstream: the pinned `opentelemetry-semantic-conventions` 0.66b1 says of `process.command_args` and `process.command_line`: "SHOULD NOT be collected by default unless there is sanitization that excludes sensitive data".
- Library: the pinned `typer` 0.27.2 vendors Click, and its `typer._click.shell_completion._resolve_context` follows the commands of a command line with resilient parsing: "it doesn't trigger input prompts or callbacks". On the installed tree, it gives `devops config set` for `config set <key> <value>`, `devops ai gateway tune` for `ai gateway tune --concurrency <value>` and `devops format` for `format --check`, and the help and completion options print nothing.

## Existing Tool Considered

Click names the command path (`Context.command_path`), and the shell completion of Typer's vendored Click (`_resolve_context`) follows the commands of a command line without a callback. The change uses both, and the command tree that `src/devops_cli/core/command_resolver.py` already loads (`module_click_command`). It builds no parser and no heuristic over the words. The change deletes the `command.line` attribute of the profile span. No OpenTelemetry instrumentation makes the profile span: the tracer of devops-cli makes it.
