# Proposal

## Why

Issue #2059: the tracer copied `cli.command` to `process.command_line` through `_ATTRIBUTE_NORMALIZATION` in `src/devops_cli/telemetry/tracer.py`. Thus each command span held the name of the command, such as `ci`, in `process.command_line`. The OpenTelemetry semantic conventions give `process.command_line` to the full command line, so a backend or a dashboard that reads the attribute gets a wrong value. #1996 removed `process.command_line` from the resource, and #2025 removed it from the subprocess spans. This alias was the last source of the attribute.

## What Changes

- The tracer has no alias from `cli.command` to `process.command_line`. A command span keeps the name of its command in `cli.command`, and the span of the command that runs keeps its command path in `cli.command_path`.
- `docs/TELEMETRY.md` (from `src/devops_cli/docs/generator.py`) says that the command spans have no `process.command_line`.
- The span attributes go to the trace backend, and a consumer can see them. Thus the change carries a spec delta for `command-telemetry`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: a command span holds no `process.command_line`.

## Impact

- Code: `src/devops_cli/telemetry/tracer.py`.
- Documents: `docs/TELEMETRY.md`, from `src/devops_cli/docs/generator.py`.
- Tests: `tests/test_otel_command_coverage.py` adds the test. `tests/test_telemetry_deduplication.py` and `tests/test_telemetry.py` read `cli.command` and not the alias.
- No dashboard, alert, query or code reads `process.command_line` from a command span.

## Feasibility

- Code: `_normalize_and_deduplicate_attributes` runs for each span. It set `process.command_line` from `cli.command` when the span had no `process.command_line`. `_delegate` in `src/devops_cli/main.py` and `_execute_traced_cli_command` in `src/devops_cli/core/cli.py` set `cli.command` on the command spans. No other code under `src/` sets `cli.command`.
- Trace backend: on 2026-10-24, the TraceQL search `{ span.process.command_line = "ci" && span.cli.command = "ci" }` on the Tempo data source found `cli.ci` spans with the two attributes equal. The values of `span.process.command_line` included the command names `ci`, `pr`, `docs`, `scan`, `test` and `create-pr`.
- Upstream: the pinned `opentelemetry-semantic-conventions` 0.66b1 defines `process.command_line` as "The full command used to launch the process as a single string representing the full command". It also says "Do not set this if you have to assemble it just for monitoring; use `process.command_args` instead". Thus a command name in this attribute has the wrong meaning, and devops-cli does not assemble the full command line for it. The CLI span conventions (`docs/cli/cli-spans.md` on the main branch, status Development, read on 2026-10-24) do not list `process.command_line`, and they have no attribute for the name or the path of a subcommand.
- Readers: no dashboard, alert or query under `k8s/` reads `process.command_line`. On 2026-10-24, no dashboard of the 16 in Grafana and no provisioned alert rule held `process.command_line` or a TraceQL query. No code under `src/` reads `process.command_line` from a span. Only two tests read the alias: `tests/test_telemetry_deduplication.py` and `tests/test_telemetry.py`.
- On the base commit, `test_a_command_span_holds_no_process_command_line` and `test_normalize_and_deduplicate_attributes_removes_duplicate_tags` fail: the spans `cli.dummy` and `cli.set` hold `process.command_line`.

## Existing Tool Considered

The OpenTelemetry semantic conventions name the attributes, and the change follows them. Nothing is built. The conventions have no attribute for the name or the path of a subcommand, so `cli.command` and `cli.command_path` stay. The change deletes the `cli.command` entry of `_ATTRIBUTE_NORMALIZATION`.
