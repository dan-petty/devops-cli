# Tasks

## 1. A config file that is not valid YAML

- [x] 1.1 Write failing tests: `tests/config/test_config_file_that_is_not_yaml.py` for the error of the load, and `tests/commands/test_config.py` for `devops config get`; change the malformed-file case of `tests/test_config_env_overrides.py` to expect `ConfigurationError`; verify that they fail with `uv run devops ci test tests/config/test_config_file_that_is_not_yaml.py tests/commands/test_config.py tests/test_config_env_overrides.py`
- [x] 1.2 Add `_read_config_file` and `_yaml_error_location` in `src/devops_cli/config/settings.py` and the message `not_yaml` in `src/devops_cli/lang/en/errors.py`, make `devops config get` in `src/devops_cli/commands/config.py` load the settings inside `exit_on_error(ConfigurationError)`, and move the non-zero exit of `_delegate` in `src/devops_cli/main.py` to the `else` clause of its `try`; verify with `uv run devops ci test tests/config tests/commands/test_config.py tests/test_config_env_overrides.py`
- [x] 1.3 Describe the error in `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`, change the YAML example of `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pyyaml_jinja2.md` to an error that quotes no text of the file, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` and `uv run devops openspec check` pass
- [x] 1.4 Write failing tests in `tests/config/test_config_file_that_is_not_yaml.py` for a tagged value that PyYAML cannot build (`!!int`, `!!bool`, `!!timestamp`) and for a file that is not UTF-8, then make `_read_config_file` catch each error but `OSError`; verify with `uv run devops ci test tests/config/test_config_file_that_is_not_yaml.py`
- [x] 1.5 Write a test in `tests/test_otel_command_coverage.py` that a delegated command that exits 2 is counted one time, records the exit code 2 and logs no record, and add the `command-telemetry` delta; verify that the test fails with the exit in the `try` of `_delegate` and passes with `uv run devops ci test tests/test_otel_command_coverage.py`
- [x] 1.6 Add the cases `!!int ''` (`IndexError`) and a document that nests too deep (`RecursionError`) to `tests/config/test_config_file_that_is_not_yaml.py`, and make `_read_config_file` catch `(yaml.YAMLError, ValueError, LookupError, AttributeError, RecursionError)` in place of `Exception`, so that `tests/test_swallowed_failures_ratchet.py` passes with the ceiling of `config/settings.py` unchanged; verify with `uv run devops ci test tests/config/test_config_file_that_is_not_yaml.py tests/test_swallowed_failures_ratchet.py`

## Workflow follow-up

- One exit seam that reports a `DevOpsCLIError` with no traceback for every command is #1006.
- The config paths that do not load the settings and can still show text of a config file are #2451.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
