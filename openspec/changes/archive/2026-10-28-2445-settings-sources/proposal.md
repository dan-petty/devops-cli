# Proposal

## Why

Issue #2445, part 2 of #1000: the resolution order of a setting was in more than one place.

- `load_settings` merged the global and the project config file with `_deep_merge`, built `Settings` with `model_validate`, and then `_apply_env_overrides` set each variable with `dotted_set`. `Settings` is a pydantic-settings `BaseSettings`, but `model_validate` reads no source, so pydantic-settings resolved nothing.
- `_resolve_data_config` rebuilt the `data` section with a third set of rules for the data paths.
- `telemetry_from_environment` applied a partial copy of the variable step.
- `Settings()` built in code read some variables through pydantic-settings' default environment source (`env_prefix="DEVOPS_CLI_"`), such as `DEVOPS_CLI_DOMAIN`, which `load_settings` did not read.

## What Changes

- `setting_sources` in `config/settings.py` declares the one order as pydantic-settings sources: `SettingVariables` (the variables that part 1 declares on the fields), the project config file, then the global config file. A setting that no source holds keeps its default. `load_settings` builds `Settings` from these sources with pydantic-settings' own merge (`BaseSettings(_build_sources=...)`). `telemetry_from_environment` uses the same variable source, with a fixed layer that keeps export off.
- `Settings.settings_customise_sources` returns only the arguments, so `Settings(...)` built in code holds its arguments and the defaults, and reads no variable and no file. `env_prefix` goes.
- `_apply_env_overrides`, `_resolve_data_config`, `_deep_merge`, `_read_config_layers`, `_merged_config_data` and `_DEFAULT_CHILD_DATA_MAP` are deleted. The file cache (#1310) now holds the two files apart, and the variable source holds the rule of `DEVOPS_CLI_DATA_DIR`.
- A value from a variable that does not validate still stops the load with `Environment variable <name> cannot set <key>: ...` (#992).
- These results change, and the change carries a spec delta in `config-commands` and `ai-task-models`:
  - A setting takes the value of the first source that holds it, and only that value is checked. Before, a config file value that a variable replaced was checked first and could stop the load.
  - A config file that sets only another field of `ai.tasks.embedding` keeps the embedding model. Before, the task model became None, and the embedding task used the chat model `ai.model`. A variable kept it before too. The embedding task gets its own override class, `AIEmbeddingTaskOverride`, whose `model` defaults to the embedding model.
  - A config file whose document is not a mapping stops the load with an error that names the file. Before, it ended in an `AttributeError`.
  - `Settings(...)` built in code reads no variable.
- Credentials keep their chain: the OS keyring, Vault, the variable, then the config file. `security.secrets.build_default_resolver` declares it, and `setting_sources` names that place.
- `docs/CONFIGURATION.md` says where the order is declared and the rules above.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `config-commands`: one declared order, the value that wins is the one checked, a config file that holds no mapping, and `Settings(...)` built in code.
- `ai-task-models`: the embedding task keeps its model when a source sets another of its fields.

## Impact

- `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/docs/generator.py`.
- `tests/config/test_setting_sources.py` (new), `tests/test_config_field_validation.py`, `tests/test_embedding_config_retention.py`.
- `docs/CONFIGURATION.md`, which `devops docs generate --sync-readme` writes.

## Feasibility

Checked on `origin/main` 0137f231 with pydantic-settings 2.15.0, the pinned version:

- `load_settings` built `Settings` with `model_validate` (`config/settings.py`), so `settings_customise_sources` was never called on a load. `Settings()` read `DEVOPS_CLI_DOMAIN` through the default environment source, and `load_settings().domain` did not: the new test failed on the base with `('example.com', ..., 'example.com')`.
- `BaseSettings.__init__` takes `_build_sources`, documented as "Pre-initialized sources and init kwargs to use for building instantiation values", and merges them with `_settings_build_values` (`pydantic_settings/main.py`): the first source wins, with `deep_update` for nested sections. `PydanticBaseSettingsSource` is the documented base of a custom source.
- `Settings.model_validate({"ai": {"tasks": {"embedding": {"timeout": 5}}}})` gave the model None and `for_task("embedding").model` `qwen3.8:27b`, the chat model. The test for the config file failed on the base with `(None, 45.0)`.
- 113 tests and 2 modules in `src` build `Settings()` and expect the defaults, and the test floor sets `DEVOPS_CLI_DATA_DIR`, `DEVOPS_CLI_TELEMETRY_ENDPOINT` and `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` for every test. So `Settings()` cannot read the sources, and the order is declared in `setting_sources`, not in `settings_customise_sources`.
- A full run of the suite on the branch: 11852 passed. The one failure was a test of this change that certified a failure without checking it, now fixed.

## Existing Tool Considered

pydantic-settings 2.15.0: `PydanticBaseSettingsSource` for the two sources, and `BaseSettings(_build_sources=...)` for the merge and the validation. The change builds no merge of its own.

- `YamlConfigSettingsSource` is not used for the files. It reads the file on each build with no cache, and the error of PyYAML quotes the text of the file, which can hold a credential (#1468). `_read_config_file` keeps the error that quotes no text, and `_config_layers` keeps the cache.
- pydantic-settings' `EnvSettingsSource` is not used for the variables. Its nested binding gives `DEVOPS_CLI_AI__TASKS__CHAT__MODEL`-style names, not the declared names such as `DEVOPS_CLI_AI_TASK_CHAT_MODEL` (part 1, #2444).

Deleted: `_apply_env_overrides`, `_resolve_data_config`, `_deep_merge`, `_read_config_layers`, `_merged_config_data`, `_DEFAULT_CHILD_DATA_MAP` and the default environment source of `Settings`.
