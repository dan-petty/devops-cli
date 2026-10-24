# Tasks

## 1. The profile span holds no argument value

- [x] 1.1 Write `test_the_profile_span_holds_the_command_path_and_the_argument_count_and_no_argument` and `test_a_person_who_turns_on_capture_gets_the_profiled_arguments_on_the_subprocess_span_only` in `tests/test_otel_command_coverage.py`, and `test_a_command_path_names_only_the_commands_and_counts_the_other_words` in `tests/test_docs_command_resolver.py`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py tests/test_docs_command_resolver.py` fails on the base in the 12 new cases: the profile span holds `command.line`, an exported payload holds the credential, and `resolve_command_path` does not exist
- [x] 1.2 Add `resolve_command_path` to `src/devops_cli/core/command_resolver.py`, make `_run_profiled_command` record `cli.command_path` and `cli.args_count` in place of `command.line`, and verify that `uv run devops ci test tests/test_otel_command_coverage.py tests/test_docs_command_resolver.py tests/test_telemetry_profile.py` passes
- [x] 1.3 Describe the profile span in the tracing section of `docs/TELEMETRY.md` in `src/devops_cli/docs/generator.py`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
