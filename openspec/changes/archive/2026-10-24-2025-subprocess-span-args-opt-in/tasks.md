# Tasks

## 1. Subprocess spans hold no argument value by default

- [x] 1.1 Write `test_a_subprocess_span_holds_the_executable_and_the_argument_count_and_no_argument` and `test_a_person_who_turns_on_capture_gets_each_argument_through_the_secret_mask` in `tests/test_otel_command_coverage.py`, each over `run_subprocess` and `run_subprocess_async`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py` fails on the base in the four new cases
- [x] 1.2 Add `capture_command_args` to `TelemetryConfig`, make `_resolve_telemetry_settings` return the `TelemetryConfig` and give the setting to the tracer, build the span attributes in `_subprocess_span_attributes`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py` passes
- [x] 1.3 Delete `_sanitize_command_for_telemetry`, the `subprocess.cmd` alias and their tests in `tests/test_process.py` and `tests/test_subprocess_env_boundary.py`, make the tests that replace `_resolve_telemetry_settings` give a `TelemetryConfig`, and verify that `uv run devops ci test tests/test_process.py tests/test_subprocess_env_boundary.py tests/test_telemetry.py tests/test_telemetry_deduplication.py tests/test_trace_propagation.py tests/test_k8s_push_secrets.py tests/test_k8s_qdrant_security.py tests/test_sandbox_lifecycle.py tests/test_workload_sandbox.py` passes
- [x] 1.4 Describe the attributes and the setting in `src/devops_cli/docs/generator.py` and `ARCHITECTURE.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- The `telemetry.profile` span of `devops telemetry profile` holds the profiled command as the person typed it, with its argument values, in `command.line`: moved to #2058.
- A command span holds the name of the command in `process.command_line` through the `cli.command` alias of `_ATTRIBUTE_NORMALIZATION`, but the conventions give that attribute to the full command line: moved to #2059.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
