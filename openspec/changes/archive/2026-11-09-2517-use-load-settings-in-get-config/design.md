# Design

## Decisions

- **The route calls `load_settings()`.** That function reads the variables and the two config files in the order that `setting_sources` declares, so the reply holds the settings that the Service runs with. `Settings()` reads no source (`src/devops_cli/config/settings.py:1378`).
- **The route imports `load_settings` only.** `Settings` has no other use in `src/devops_cli/server/routes/workspace.py`, so the import names the function the route calls and no unused name.
- **The redaction stays as it is.** `_redact_config_dict` already masks every key of `secret_keys()`, and `load_settings()` now gives it the loaded values. The tests assert the masked value and the absence of the clear value in the reply.
- **The tests set one value per source.** An environment variable proves the variable source, a temporary project config file proves the file source, and a value under `valkey.password` proves that a loaded secret is masked.

## Rejected alternatives

- **Keep `Settings()` and read the config file in the route.** That repeats the source order of `load_settings`, including the variable names and the project lookup, and the two copies can drift.
- **Call `Settings()` with the mappings that `config_layer_paths()` reads.** `Settings` holds its arguments only, so the route would build the sources again and skip the cache and the unknown-key error that `load_settings` gives.
- **Mask the credentials that only the keyring holds.** `settings.model_dump()` holds no keyring credential, because those credentials are not settings fields. The route cannot return a value that the settings do not hold, so the requirement covers the secret fields that the settings carry.
