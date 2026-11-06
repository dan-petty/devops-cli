# Tasks

## 1. Config tests use the config fixture and the edge fakes (test-only edits)

- [x] 1.1 Move `global_config` to `tests/support/config.py`, and move the cache tests to `tests/config/test_settings_cache.py`, where each stamp case runs over the global file and over the project file, without `CONFIG_PATH` and without `_CONFIG_CACHE`
  - Verification: `uv run devops ci test tests/config/test_settings_cache.py tests/config/test_setting_sources.py`
- [x] 1.2 Set the configuration of `tests/telemetry/test_config_env_overrides.py` through the `config` fixture and the floor's config file, serve the gateway pool and the embedding request through the `web` fixture, and use public behavior in place of private functions
  - Verification: `uv run devops ci test tests/telemetry/test_config_env_overrides.py`
- [x] 1.3 Take the config of `tests/config/test_ai_task_settings_paths.py` through the `config` fixture, and compare the whole file as parsed YAML
  - Verification: `uv run devops ci test tests/config/test_ai_task_settings_paths.py`
- [x] 1.4 No test of the three files rebinds `CONFIG_PATH` or reads the private cache
  - Verification: `! git grep -nw -e CONFIG_PATH -e _CONFIG_CACHE -- tests/telemetry/test_config_env_overrides.py tests/config/test_settings_cache.py tests/config/test_ai_task_settings_paths.py`

## 2. Documents

- [x] 2.1 Name the `global_config` fixture in the Config section of `docs/TESTING.md`
  - Verification: `uv run devops ci docs`

## 3. Archive

- [x] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 3858-config-tests-on-edge-fakes`
