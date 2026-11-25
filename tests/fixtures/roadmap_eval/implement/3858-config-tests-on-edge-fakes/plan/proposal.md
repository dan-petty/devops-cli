# Proposal

## Why

Issue #3858 is item 2 of the Fit note of #1333. Three config test files rebind `devops_cli.config.settings.CONFIG_PATH` with `monkeypatch.setattr`. The rebinding is a patch of a private name of the product. The hermetic floor already gives each test its own `config.yaml` through `DEVOPS_CLI_CONFIG`, and its own HOME for the global config file. So no test needs the rebinding.

- `tests/telemetry/test_config_env_overrides.py` rebinds it in 5 tests.
- `tests/core/test_config_settings_cache.py` rebinds it in 2 helpers, and reads the private `_CONFIG_CACHE` in 2 tests.
- `tests/config/test_ai_task_settings_paths.py` rebinds it in its own `own_config` fixture.

Item 7 of #1333 removes `CONFIG_PATH` from the key of the settings cache. It cannot do that while these tests rebind the name.

The same files also hold other patches of devops-cli names. This change removes them where the edge fakes cover them: the patch of `run_store.gateway_pool`, and the private `_make_review_clients`, `_find_project_config_path`, `_resolve_telemetry_settings` and `EmbeddingsEngine._get_ollama_urls`.

## What Changes

- `tests/telemetry/test_config_env_overrides.py` sets configuration through the `config` fixture, or writes raw text into the floor's config file when the text is not a mapping (a malformed file). The gateway pool test serves `/model/info` through the `web` fixture instead of patching `gateway_pool`. The private functions give way to their public behavior: `config_layer_paths()`, `AIConfig.for_task()`, `EmbeddingsEngine.embed_texts()` and the `enabled` switch of the tracer.
- `tests/core/test_config_settings_cache.py` moves to `tests/config/test_settings_cache.py`, the mirror of `config/settings.py`. It runs each stamp case over both layers: the global file and the project file. It checks the cache through what `load_settings` returns, not through `_CONFIG_CACHE`.
- `tests/config/test_ai_task_settings_paths.py` takes the floor's config through the `config` fixture. It compares the whole file as parsed YAML.
- `global_config` moves from `tests/config/test_setting_sources.py` to `tests/support/config.py`, next to `config`, so the cache tests share it.
- This change alters no product code and no behavior a consumer observes. It has no spec delta, and `skip_specs: true` is set.
- The change fits one pull request.

Not in this change: the key of the settings cache (item 7 of #1333), the other tests that rebind `CONFIG_PATH` (in `tests/roadmap/`, `tests/commands/`, `tests/ai/client/test_response_cache.py` and `tests/telemetry/test_telemetry_collector_export.py`), `tests/config/test_metadata.py`, and `tests/ai/benchmark/test_data_dir_configuration.py`. The first patches the standard library (`importlib.metadata`). The second imports a private name of the benchmark runner. Both belong to other items.

## Impact

- `tests/telemetry/test_config_env_overrides.py`, `tests/config/test_settings_cache.py` (moved), `tests/config/test_ai_task_settings_paths.py`, `tests/config/test_setting_sources.py` and `tests/support/config.py`.
- `docs/TESTING.md` (the Config section).
- No path under `src/` changes.

## Feasibility

Checked on `origin/main` 5bc50d0a, 2026-11-06. The tree has moved since #1333 was written, so each claim was read again.

- The 6 `_keyring` patches are gone. `rg -n "_keyring_get|_keyring_set" tests` finds nothing, and `tests/config/test_headless_auth.py` uses the `keyring_store` fake. No keyring work is left for this item.
- The floor no longer patches `CONFIG_PATH`. `tests/support/bootstrap.py` sets HOME before devops-cli loads, so `CONFIG_PATH` is a path under the run's HOME, and `isolate_devops_cli_config` points `DEVOPS_CLI_CONFIG` at a file of each test. `rg -n CONFIG_PATH tests/conftest.py` finds nothing.
- The cache holds both layers (`_config_layers` in `config/settings.py`): the stamps of the global file and of the project file. A test of the cache therefore needs both layers. The global file is writable under the run's HOME, as `tests/config/test_setting_sources.py` already does, and the project file is the one `DEVOPS_CLI_CONFIG` names.
- Gateway pool: `gateway_pool` reads `GET <gateway_url>/model/info` through `http_client` (`ai/gateway.py`, `_fetch_endpoint_resp`). The `web` fixture serves that request, so the patch is not needed. The migrated test passes with the fake.
- Coverage check: the product code was mutated in the working tree, one change at a time, and the migrated tests ran after each change. Killed: ignore the project stamp, ignore the global stamp, cache a file that is not settled, keep the cache on save, drop the untrusted rule from the key, and no pool for a gateway task. One mutation survives: the cache returns its held copy instead of a deep copy. The tests of `origin/main` do not kill it either, so coverage is not lower than before.

## Existing Tool Considered

pytest `monkeypatch`, and the project's own fixtures: `config` (#1310), `web` (#1314) and `keyring_store` (#1318). The fixtures exist, so this change builds nothing new except the move of the `global_config` fixture. The change deletes 8 `CONFIG_PATH` rebinding sites, the patch of `gateway_pool`, the `own_config` rebinding fixture and the `_isolate` helper.
