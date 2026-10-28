# Tasks

## 1. A config file that is not valid YAML

- [x] 1.1 Write failing tests: `tests/config/test_config_file_that_is_not_yaml.py` for the error of the load, and `tests/commands/test_config.py` for `devops config get`; change the malformed-file case of `tests/test_config_env_overrides.py` to expect `ConfigurationError`; verify that they fail with `uv run devops ci test tests/config/test_config_file_that_is_not_yaml.py tests/commands/test_config.py tests/test_config_env_overrides.py`
- [x] 1.2 Add `_read_config_file` and `_yaml_error_location` in `src/devops_cli/config/settings.py` and the message `not_yaml` in `src/devops_cli/lang/en/errors.py`, make `devops config get` in `src/devops_cli/commands/config.py` load the settings inside `exit_on_error(ConfigurationError)`, and move the non-zero exit of `_delegate` in `src/devops_cli/main.py` to the `else` clause of its `try`; verify with `uv run devops ci test tests/config tests/commands/test_config.py tests/test_config_env_overrides.py`
- [ ] 1.3 Describe the error in `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` and `uv run devops openspec check` pass

## Workflow follow-up

- One exit seam that reports a `DevOpsCLIError` with no traceback for every command is #1006.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
