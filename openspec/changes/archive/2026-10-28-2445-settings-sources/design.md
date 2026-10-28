# Design

## The order

`setting_sources(layers)` returns the sources of a load, the first one that holds a key winning:

1. `SettingVariables(Settings)`: each declared setting whose variable is set and not empty. A list setting takes a JSON list or comma-separated values (`_coerce_setting_value`, as `devops config set` does). When `DEVOPS_CLI_DATA_DIR` is set, the source also sets each data path that no variable of its own sets to that directory and the path's relative part, so the data paths of a config file do not apply, as `_resolve_data_config` did.
2. `MappingSource(Settings, layers.project)`: the project config file, without its null values at any depth, so a null keeps the value of the global file, as `_deep_merge` did.
3. `MappingSource(Settings, layers.global_config)`: the global config file.
4. The field defaults, which pydantic gives to each key that no source holds.

`load_settings` builds `Settings(_build_sources=(setting_sources(layers), {}))`. pydantic-settings merges the sources with `deep_update` and validates the result once. `telemetry_from_environment` builds the same way from `SettingVariables(Settings, ("telemetry.enabled", "telemetry.endpoint"))` and a fixed layer `{"telemetry": {"enabled": False}}`.

`SettingVariables` keeps the variable of each key that it set. When the validation of the merged settings fails on a key that a variable set, the load raises `Environment variable <name> cannot set <key>: <location>: <reason>`, the text that `_apply_env_overrides` gave. An error on a key that a file set stays a `ValidationError`, and a key that a section refuses still gets its file and line (#2201).

## Credentials

A credential keeps its own chain, declared once in `security.secrets.build_default_resolver`: the OS keyring, Vault, the variable, then the config file for a credential that a file can hold. The keyring is the canonical store, so it comes before the variable. That order is not a settings source, because a credential is read through `SecretResolver` with an audit record and is never a value in `Settings`, except the credentials that a file can hold, which stay plain fields. `setting_sources` names this place.

## Decisions

- Only the value that wins is checked. A config file value that a variable replaces is no longer validated. This is the rule of pydantic-settings, and the alternative (validate each layer apart) lets a value that applies nowhere stop every load.
- `ai.tasks.embedding` gets the class `AIEmbeddingTaskOverride`, whose `model` defaults to `DEFAULT_RAG_EMBEDDING_MODEL`. The default lives in the class, so any partial value from any source keeps it. It was the only section whose default differed from its class's defaults (checked by walking every section of `Settings`).
- A config file that holds no mapping raises `ConfigurationError` with `ERRORS.config.not_mapping`, because a source needs a mapping.

## Rejected alternatives

- **Declare the order in `settings_customise_sources`, so that `Settings()` loads.** 113 tests and 2 modules in `src` (`docs/generator.py`, `server/routes/workspace.py`) build `Settings()` and expect the defaults, and the test floor sets three variables in every test. `Settings()` would then read them and the files.
- **`nested_model_default_partial_update=True` with pydantic-settings' `DefaultSettingsSource`.** It dumps the defaults of each section into the merged input. Then `AIConfig._migrate_append_cache` always sees `ollama_urls` and `cache`, and drops a legacy `ollama_base_url` or `append_cache` key without a word.
- **A context variable that turns the sources on during a load.** It keeps `settings_customise_sources` as the one place, but `Settings()` would then depend on hidden state.
- **`YamlConfigSettingsSource` for the files.** See the proposal: no cache, and an error that quotes the file text (#1468).
- **Validate each layer apart to keep the old error for a replaced value.** Two or three validations on each load, and a value that does not apply could stop the load.
