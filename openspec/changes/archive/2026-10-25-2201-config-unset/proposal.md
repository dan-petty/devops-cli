# Proposal

## Why

Issue #2201: the `ai` settings refuse a key that they do not declare. A config file that still holds a removed key, such as `ai.vllm_url`, stops every command that loads the settings with the pydantic error `ai  Value error, Unknown configuration key 'vllm_url'`. The error does not name the file, the line or a fix, and `devops config` has no command that removes a key, so a person must edit the file by hand.

## What Changes

- Add `devops config unset <key>`. It removes the key and its value from the active config file with the round-trip editor of `devops config set`, so the comments, the order and the other lines stay. It loads no settings, so it works when the key stops the load. A write copies the file to `<name>.bak-<YYYYMMDD-HHMMSS>` and records the removed key in the audit log, as a save does. A key that the file does not hold exits 1 and changes nothing. `--dry-run` prints the change, with the lines of its unified diff, and writes nothing.
- When the settings do not load because a section refuses a key, the error names the full dotted key, the file and the line of the key, and the command that removes it: `Unknown configuration key 'ai.vllm_url' at <file>:<line>. Release 0.2.34 removed it. Remove it with: devops config unset ai.vllm_url`. A table of removed keys gives the release. A key in the config file that is not the active one gets the command with `DEVOPS_CLI_CONFIG` set to that file. The error applies to every section with `extra="forbid"`: `ai`, `ai.tasks` and each `ai.tasks.<task>`.
- The hint for the per-model sampling and serving settings (`top_k`, `min_p`, `presence_penalty`, `repeat_penalty`, `think`, `keep_alive`) moves into this error.
- The command, its option and its messages are observable behavior, so the change carries a spec delta for `config-commands`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: `devops config unset` removes a key from the config file, and the error of a refused key names the key, the file, the line and the command that removes it.

## Impact

- `src/devops_cli/config/round_trip.py`: `find` gives the key path and the line of a dotted key in the text of a config file.
- `src/devops_cli/config/unknown_keys.py`: the error of the refused keys.
- `src/devops_cli/config/settings.py`: `load_settings` raises that error; `remove_config_key` removes a key; the hand-written unknown-key loops of `AIConfig` and `AITaskOverride` are deleted.
- `src/devops_cli/commands/config.py`: the `unset` command.
- `src/devops_cli/models/config.py`: `ConfigKeyRemoval`.
- `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/`: the table of removed keys, the serving settings, the messages and the help text.
- `src/devops_cli/docs/generator.py` and the generated documents; the knowledge base page `configuration_and_settings.md`.

## Feasibility

- Reproduced on `origin/main` (527558fa) with a temporary config file that holds `ai.vllm_url` under `DEVOPS_CLI_CONFIG`: `devops config get ai.provider` exits 1 with `ValidationError: 1 validation error for Settings / ai / Value error, Unknown configuration key 'vllm_url'. [type=value_error]`.
- `CHANGELOG.md`, release 0.2.34, names the removal of the settings field `AIConfig.vllm_url`.
- ruamel.yaml 0.19.1 in round-trip mode gives the 0-based line and column of each mapping key through `CommentedMap.lc.key(<key>)`, also for a flow mapping. It refuses a duplicate key (`DuplicateKeyError`, a `YAMLError`) that PyYAML accepts.
- pydantic 2.13.5 reports a key that a section with `extra="forbid"` does not declare as an error of type `extra_forbidden` whose `loc` is the full key path, such as `('ai', 'tasks', 'chat', 'no_such_key')`. The `before` validators of `AIConfig` and `AITaskOverride` raised a `ValueError` whose `loc` was only the section, so they hid the path.
- `round_trip.edit` already removes a key path given the value `ABSENT` and keeps the comment lines after the key (#1999), and `write_history.back_up` already writes the UTC copy `<name>.bak-<YYYYMMDD-HHMMSS>` (#1921).

## Existing Tool Considered

- ruamel.yaml, which `devops config set` already uses, gives the round trip and the line of each key. pydantic's `extra="forbid"` refuses the undeclared keys and names their full paths. The standard library `difflib` makes the dry-run diff, and `shlex` quotes the command. No new dependency.
- `yq` can delete a path, but it is another binary to pin and start, and the round trip that `devops config set` uses already covers the need inside the process.
- The change deletes the two hand-written unknown-key loops in `AIConfig._migrate_append_cache` and `AITaskOverride._validate_unknown_keys`, which repeated what `extra="forbid"` does and hid the key path.
