# Tasks

## 1. The error of a refused key

- [x] 1.1 Write failing tests in `tests/config/test_unknown_config_keys.py` for the error of a removed key, of an unknown key in each section that refuses one, of two keys, and of a key in the config file that is not the active one, and move the sampling-key test in `tests/test_ai_model_sampling.py` to the load of the settings; verify that they fail with `uv run devops ci test tests/config/test_unknown_config_keys.py tests/test_ai_model_sampling.py`
- [x] 1.2 Add `round_trip.find`, the module `src/devops_cli/config/unknown_keys.py`, the table of removed keys and the serving settings in `src/devops_cli/config/constants.py`, and the messages in `src/devops_cli/lang/en/errors.py`; make `load_settings` raise the error, and delete the unknown-key loops of `AIConfig` and `AITaskOverride` in `src/devops_cli/config/settings.py`
- [x] 1.3 Run `uv run devops ci test tests/config/test_unknown_config_keys.py tests/test_ai_model_sampling.py tests/test_ai_task_settings_paths.py` and verify that the tests pass

## 2. devops config unset

- [x] 2.1 Write failing tests in `tests/config/test_config_key_removal.py` for a removal, a section, a key whose name holds a dot, a dry run, a key that the file does not hold and a file that is not YAML, and in `tests/commands/test_config.py` for the command, its exit codes, its output and `--dry-run`; verify that they fail with `uv run devops ci test tests/config/test_config_key_removal.py tests/commands/test_config.py`
- [x] 2.2 Add `remove_config_key` and `_write_content` in `src/devops_cli/config/settings.py`, `ConfigKeyRemoval` in `src/devops_cli/models/config.py`, the `unset` command in `src/devops_cli/commands/config.py`, its help and messages in `src/devops_cli/lang/en/`, and the exclusion of `config unset` from the MCP tools in `tests/test_mcp.py`
- [x] 2.3 Run `uv run devops ci test tests/config tests/commands/test_config.py tests/test_config_save_round_trip.py tests/test_config_write_history.py tests/test_mcp.py` and verify that the tests pass
- [x] 2.4 Describe `devops config unset` and the error in `src/devops_cli/docs/generator.py` and `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` and `uv run devops openspec check` pass

## Workflow follow-up

- Pending a person: run `devops config unset ai.vllm_url` on the workstation config file, then `devops config show`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
