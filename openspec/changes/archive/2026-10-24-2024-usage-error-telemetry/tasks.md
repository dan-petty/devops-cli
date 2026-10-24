# Tasks

## 1. Usage errors in the command telemetry

- [x] 1.1 Write `test_a_usage_error_shows_the_error_box_of_typer`, `test_a_usage_error_records_its_class_and_exit_code_and_no_argument_text` and `test_a_usage_error_counts_as_a_failed_command` in `tests/test_otel_command_coverage.py`, for an extra argument to `devops config set` and for a `typer.BadParameter` from `devops ai gateway tune`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py` fails on the base: the exported payloads hold the typed credential, and `devops_cli_command_total` has no point
- [x] 1.2 Make `_delegate` catch `typer.TyperException`, record the status, the exit code and the duration, count the command as failed and raise the error again, and remove its `click.ClickException` branch, and verify that `uv run devops ci test tests/test_otel_command_coverage.py` passes
- [x] 1.3 Make the tracer and `_record_cli_failure` record the class and no message of a `typer.TyperException`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py tests/test_telemetry.py tests/test_telemetry_deduplication.py tests/test_telemetry_semconv.py tests/test_security_sandbox_and_protection.py tests/test_fast_dispatch.py tests/test_main_dry_run.py` passes
- [x] 1.4 Add the usage error bullet to the tracing section of `docs/TELEMETRY.md` in `src/devops_cli/docs/generator.py`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
