## Problem or Motivation

Item 2 of the Fit note of #1333. Three config test files rebind `devops_cli.config.settings.CONFIG_PATH` with `monkeypatch.setattr`: `tests/telemetry/test_config_env_overrides.py` (5 sites), `tests/core/test_config_settings_cache.py` (2 sites) and `tests/config/test_ai_task_settings_paths.py` (1 site). The hermetic floor already gives each test its own `config.yaml` through `DEVOPS_CLI_CONFIG`, and the `config` fixture (`tests/support/config.py`) writes overrides into that file and resets the settings cache. So the rebinding is a private patch that the floor makes needless.

The tree has moved since #1333 was written. The 6 `_keyring` patches are already gone: `tests/config/test_headless_auth.py` and the telemetry tests use the `keyring_store` fake (#1318). No test patches a `_keyring` name or imports `_keyring_get` or `_keyring_set`.

A later item (item 7 of #1333) removes `CONFIG_PATH` from the settings cache key. It cannot do so while these tests rebind it.

## Proposed Solution & Architectural Design

- Each test writes its config through the `config` fixture, or through the floor's config file when it needs raw text that is not a mapping. No test rebinds `CONFIG_PATH`.
- `tests/core/test_config_settings_cache.py` tests the stamp cache through the floor's config file. It checks the cache through behavior (what `load_settings` returns), not through the private `_CONFIG_CACHE`, where the behavior shows it.
- `tests/config/test_ai_task_settings_paths.py` uses the floor's config and drops its own `own_config` rebinding.
- Prove the migration keeps coverage: mutate the product code in a scratch copy and confirm the migrated tests fail.
- Out of scope: the cache key in `config/settings.py` (item 7), other `CONFIG_PATH` rebinding sites in other files, and the other items of #1333.

## Target Subsystem

Tests (`tests/config`, `tests/core`, `tests/telemetry`).

## Existing Tool Considered

pytest `monkeypatch` and the project's `config` fixture. The fixture exists, so no new tool is built. No cost to build.

## Acceptance criteria

- [ ] No test in the three files names `CONFIG_PATH` or `settings.CONFIG_PATH`.
- [ ] No test in the three files patches a `_keyring` name.
- [ ] Each migrated test fails when the product behavior it covers is mutated.
- [ ] `uv run devops ci` passes.

## Related

Related: #1333 (parent), #1307, #1310 (`config` fixture), #1318 (keyring fake).


<!-- devops-roadmap-record {"Effort": "Medium", "Priority": "P2-Medium", "Status": "In Progress", "Value": "Medium"} -->
