# Tasks

## 1. Command spans hold no process.command_line

- [x] 1.1 Write `test_a_command_span_holds_no_process_command_line` in `tests/test_otel_command_coverage.py`, make `test_normalize_and_deduplicate_attributes_removes_duplicate_tags` in `tests/test_telemetry_deduplication.py` expect no `process.command_line`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py tests/test_telemetry_deduplication.py` fails on the base in these two tests
- [x] 1.2 Delete the `cli.command` entry of `_ATTRIBUTE_NORMALIZATION`, make `test_response_span_attributes_and_semantic_conventions` in `tests/test_telemetry.py` read `cli.command`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py tests/test_telemetry_deduplication.py tests/test_telemetry.py tests/test_telemetry_semconv.py tests/test_sandbox_traces.py tests/test_trace_propagation.py` passes
- [x] 1.3 Say in `src/devops_cli/docs/generator.py` that the command spans have no `process.command_line`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
