# Tasks

## 1. One order through pydantic-settings sources

- [x] Add failing tests: the table of a plain setting across the variable, the project file, the global file and the default; the table of a credential across the keyring, Vault, the variable and the file; `Settings(...)` built in code; the embedding model with a variable and with a file; a variable that replaces a file value; a file value that does not validate; a config file that holds no mapping
  - Verification: `uv run devops ci test tests/config/test_setting_sources.py`
- [x] Declare the order in `setting_sources` with `SettingVariables` and `MappingSource`, build `load_settings` and `telemetry_from_environment` from it, make `Settings(...)` read only its arguments, and give the embedding task `AIEmbeddingTaskOverride`
  - Verification: `uv run devops ci test tests/config/ tests/test_config_env_overrides.py tests/test_config_field_validation.py tests/test_data_dir_configuration.py tests/test_secret_resolution.py tests/test_qdrant_timeout_setting.py tests/test_config_declarations.py`
- [x] Delete `_apply_env_overrides`, `_resolve_data_config`, `_deep_merge`, `_read_config_layers`, `_merged_config_data` and `_DEFAULT_CHILD_DATA_MAP`, and move the two tests that relied on the old behavior to the new one
  - Verification: `uv run devops ci test tests/test_embedding_config_retention.py tests/test_config_field_validation.py`
- [x] Describe the order and its rules in `docs/CONFIGURATION.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2445-settings-sources`

## Workflow follow-up

- #2447: the defaults of settings are read only through the settings, with an import-boundary test.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
