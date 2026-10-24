# Tasks

## 1. A settings save writes only the changed keys and keeps the rest of the file

- [x] 1.1 Write `tests/test_config_save_round_trip.py` (comments, unknown keys and the removed Valkey keys kept, a copy of `config.example.yaml`, a new file, a removed entry, a file of comments alone, a `---` marker, settings made in code, a file that holds no mapping), rewrite `tests/test_config_write_history.py` to save changed keys of loaded settings, and add `tests/support/config_writes.py`, which reads the keys of each config write from the audit log. Verify that `uv run devops ci test tests/test_config_save_round_trip.py tests/test_config_write_history.py` fails on the base because each save wrote the whole model
- [x] 1.2 Add `ruamel.yaml==0.19.1` with `uv add`, add `src/devops_cli/config/round_trip.py`, keep the loaded values in `Settings._loaded`, make `save_settings` write the changed keys through `round_trip.edit`, make `write_history.record_write` name the keys that changed in the file, and delete `_prune_default_data_config` and `write_history._leaves`. Make the save of `tests/invariants/test_hermetic_floor.py` change a key, so that the guard still sees a write. Verify that `uv run devops ci test tests/test_config_save_round_trip.py tests/test_config_write_history.py tests/invariants/test_hermetic_floor.py tests/test_data_dir_configuration.py tests/test_config_settings_cache.py` passes
- [x] 1.3 Describe the save in the generator text of `docs/CONFIGURATION.md` and in the knowledge base pages `libraries/pyyaml_jinja2.md` and `python_packages.md`. Verify with `uv run devops docs generate --sync-readme`, then `uv run devops docs check`

## 2. Each caller of save_settings names the keys that it writes

- [x] 2.1 Add the keys that each caller writes to its test: `devops ai runs connect` in `tests/test_run_store.py`, `devops k8s configure-urls` in `tests/test_k8s_bootstrap.py` (without the patches of `load_settings` and `save_settings`), `devops k8s switch-context` in `tests/test_k8s_context.py`, `devops ai config` in `tests/test_ai_task_settings_paths.py`, `devops telemetry connect` in `tests/test_telemetry_collector_export.py`, `devops ai gateway connect` in `tests/test_ai_gateway.py` (without the patch of `save_settings`), `devops config set` in `tests/test_config_write_history.py` and `tests/test_config_save_round_trip.py`, and `devops config init` in `tests/commands/test_config.py`. Verify that `uv run devops ci test tests/test_run_store.py tests/test_k8s_bootstrap.py tests/test_k8s_context.py tests/test_ai_task_settings_paths.py tests/test_telemetry_collector_export.py tests/test_ai_gateway.py tests/commands/test_config.py` fails on the base
- [x] 2.2 Give `save_settings` the `keys` parameter, and make `devops config set` give the key that it names unless it is a credential. Verify that `uv run devops ci test tests/test_config_save_round_trip.py tests/test_config_write_history.py tests/test_config_commands.py tests/test_config_cmd.py` passes, and that the tests of 2.1 pass

## 3. A save keeps the removed Valkey keys

- [x] 3.1 Change the test of the removed `valkey.host`, `valkey.port` and `valkey.db` keys in `tests/test_valkey.py` to save a changed key and find the four `valkey` keys as the file holds them. Verify that `uv run devops ci test tests/test_valkey.py` fails on the base and passes after group 1

## Workflow follow-up

- `devops k8s configure-urls` saves only when its `configured` table holds a key, but `_update_task_gateway_urls` changes `ai.tasks.analysis.api_base_url` and `ai.tasks.chat.api_base_url` without an entry in that table, so a run that changes only these URLs saves nothing: moved to #2108.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
