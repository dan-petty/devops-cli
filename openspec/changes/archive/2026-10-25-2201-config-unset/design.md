# Design

## Context

`load_settings` merges the global config file and the project config file with PyYAML and validates the result with `Settings.model_validate`. The sections `ai`, `ai.tasks` and each `ai.tasks.<task>` set `extra="forbid"`. `devops config set` saves through `round_trip.edit` (ruamel.yaml in round-trip mode, #1999) and `write_history` (the copy and the audit record, #1921). Both need a loaded `Settings` object, so neither can remove a key that stops the load.

## Decisions

### The removal edits the text of the file and loads no settings

`remove_config_key` reads the active config file, finds the key with `round_trip.find`, and removes it with `round_trip.edit(text, {path: ABSENT})`, which already keeps the comment lines after a removed key. The write goes through the same `_write_content` as a save, so it makes the same copy and audit record. The settings cache is reset after the write. A dry run returns the same `ConfigKeyRemoval`, with no copy, and writes nothing.

### A dotted key resolves against the mappings of the file

A key can hold a dot, such as the model name `qwen3.8:27b` in `ai.gateway_weights`. So `find` walks the mappings: at each mapping it takes the key that is the rest of the dotted key, else the first key that starts it, and it backtracks when that path does not hold the rest. The key path that it returns goes to `round_trip.edit` as a tuple, as for a save.

### The error comes from pydantic's own error for an undeclared key

The `before` validators of `AIConfig` and `AITaskOverride` looped over the input keys and raised a `ValueError`. Its location was only the section, such as `('ai',)`, so the full key was lost. These loops are deleted: `extra="forbid"` already refuses the same keys, and its `extra_forbidden` error has the full key path as its location, for every section that sets it. `load_settings` catches the `ValidationError`, and when it holds `extra_forbidden` errors, it raises a `ConfigurationError` from `unknown_keys.unknown_keys_error`, chained to the validation error. A validation error with no refused key goes up as before.

### The line comes from the files, read again only on the error path

The merged mapping has no line numbers. On the error path alone, `unknown_keys_error` reads the project config file and then the global one, and takes the line of each key from the first file that holds it (`round_trip.find`). The lines of the error go in the order of the files and of the lines in them. For a key in the file that is not the active one, the command sets `DEVOPS_CLI_CONFIG` to that file, because `devops config unset` edits the active file, as `devops config set` writes it.

### A small table gives the release that removed a key

`CONST_REMOVED_CONFIG_KEYS` holds `ai.vllm_url: 0.2.34`, from the changelog of release 0.2.34. The per-model sampling and serving settings are in `CONST_AI_SERVING_SETTINGS`, and their hint moves from the deleted validator loops into the same error.

## Rejected alternatives

- **Keep the validator loops and raise a `PydanticCustomError` with the key in its context.** The loops repeat what `extra="forbid"` does, and they would still need a second code path for `ai.tasks`, which has no loop and reports `extra_forbidden`. pydantic 2.13.5 gives the full path in `loc` for `extra_forbidden`, so one path covers every section.
- **Load the config files with ruamel.yaml for every load, to keep the line of each key.** The lines are needed only when a load fails. PyYAML stays the loader of the settings, and ruamel.yaml reads the files again only on the error path.
- **A `--file` option on `devops config unset`.** `DEVOPS_CLI_CONFIG` already selects the file that `devops config set` and `devops config unset` edit, and the error names it for a key in the other file. A second way to select the file would add an option with no new need.
- **Remove the key from every config file that holds it.** `devops config set` writes one file, the active one. An unset that also edits the other file would change a file that the person did not name.
- **A migration system for removed keys.** The issue asks for the release in the message only, and a table of one entry covers the known removal. Before 1.0.0 the project keeps no migration path.
- **Remove a section that becomes empty.** `ai: {}` loads as the defaults, and the removal changes only the key that the person named.
