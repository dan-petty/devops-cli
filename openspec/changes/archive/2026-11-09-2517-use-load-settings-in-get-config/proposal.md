# Proposal: #2517

## Why

The `GET /api/v1/config` route of the Service says that it returns the active, non-secret configuration, but it builds `Settings()` directly. `Settings.settings_customise_sources` returns only `init_settings` (`src/devops_cli/config/settings.py:1378`), so the constructor reads no variable and no config file and returns the field defaults. The route therefore reports defaults instead of the settings that the Service runs with (#2517).

## What Changes

- `get_configuration` in `src/devops_cli/server/routes/workspace.py:111` calls `load_settings()` instead of `Settings()`.
- The import changes from `Settings` to `load_settings`; no other code in the file uses `Settings`.
- Tests in `tests/server/test_server.py` prove that an environment variable and a config file value reach the reply, and that a loaded secret is redacted.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `service-config-route`: the `GET /api/v1/config` route returns the active, non-secret configuration.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/server/routes/workspace.py`
- Tests: `tests/server/test_server.py`

## Feasibility

- `rg -n "Settings\(" src/devops_cli/server/routes/workspace.py` finds one use, at the line that builds the reply (`:115` before the change).
- `Settings.settings_customise_sources` states that the constructor reads no variable and no file and returns `(init_settings,)` (`src/devops_cli/config/settings.py:1378`).
- `load_settings()` builds the settings from the declared sources: its variables, the project config file and the global config file (`src/devops_cli/config/settings.py:1675`, `setting_sources` at `:1628`).
- The probe `DEVOPS_CLI_AI_MODEL=example-model uv run python -c "from devops_cli.config.settings import Settings, load_settings; print(Settings().ai.model, load_settings().ai.model)"` printed `qwen3.8:27b example-model`. The premises of the issue hold: the constructor drops the variable and `load_settings` keeps it.

## Existing Tool Considered

The project already uses `pydantic-settings`, and `load_settings()` is the existing loading path. The change calls that function and builds no new code.
