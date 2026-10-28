# Tasks

## 1. devops config set refuses an unknown key first

- [x] 1.1 Write failing tests in `tests/config/test_config_keys.py` for the keys that the settings know and the similar keys, and in `tests/commands/test_config.py` for `devops config set` of an unknown key without a VALUE, with a VALUE and with `--from-file -`, and for `devops config get` of an unknown key; verify that they fail with `uv run devops ci test tests/config/test_config_keys.py tests/commands/test_config.py`
- [x] 1.2 Add `is_config_key` and `similar_config_keys` in `src/devops_cli/config/settings.py`, check the key first in the `set` command, print the two lines from `get` and `set` in `src/devops_cli/commands/config.py`, and add the messages in `src/devops_cli/lang/en/messages.py`; verify with `uv run devops ci test tests/config/test_config_keys.py tests/commands/test_config.py tests/test_config_commands.py tests/test_config_cmd.py tests/test_config_field_validation.py tests/test_ai_task_settings_paths.py tests/test_config_write_history.py`
- [x] 1.3 Describe the check in `src/devops_cli/docs/generator.py`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
