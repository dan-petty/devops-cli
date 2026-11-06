# Design

## Context

See proposal.md for the motivation and the scope (#3858). The change edits test files only.

## Decisions

### 1. A test controls the project file

- **Decision**: A test writes its configuration into the floor's config file (the file `DEVOPS_CLI_CONFIG` names) through the `config` fixture. A test of the cache over the global layer writes the global file through `global_config`, under the run's HOME.
- **Rejected**: Keep `monkeypatch.setattr(settings, "CONFIG_PATH", path)`. The name is a private patch, and item 7 of #1333 removes it from the cache key.
- **Rejected**: Point HOME at a new directory per test. The floor sets HOME once per run, before devops-cli loads, and `CONFIG_PATH` is bound at import. A second HOME would not change it.

### 2. The cache is checked through what a load returns

- **Decision**: The tests of the settle window and of `save_settings` rewrite a file with the same stamp and compare the model that the next load returns. They do not read `_CONFIG_CACHE`.
- **Rejected**: Read `len(_CONFIG_CACHE)`. It is a private name, and it ties the test to the layout of the cache.

### 3. Mirror directory

- **Decision**: `test_config_settings_cache.py` moves to `tests/config/test_settings_cache.py`, because it tests only `config/settings.py`.
- `tests/telemetry/test_config_env_overrides.py` stays where it is: half of its tests build the tracer.
