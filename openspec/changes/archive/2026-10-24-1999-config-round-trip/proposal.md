# Proposal

## Why

Issue #1999: `save_settings` wrote the whole settings model back to `config.yaml`. A save dropped the comments, the order of the keys and the keys that the model does not know, and it wrote every default. The settings in memory merge the global config file, the project config file and the `DEVOPS_CLI_*` variables, so a save also copied the values of the other file and of the environment into the file that it wrote. #1921 added a copy before each write and a change record, so a person can restore a file, but a save still rewrote the whole file.

## What Changes

- `save_settings` writes only the keys whose values the command changed after `load_settings` returned the settings. `load_settings` keeps the values that it returned in a private attribute of `Settings`, and the save compares the settings with them. Settings that code makes without `load_settings` start from the defaults of the model.
- The new module `devops_cli.config.round_trip` edits the file with `ruamel.yaml` in round-trip mode. The file keeps its comments, the order of its keys, its quotes, the keys that devops-cli does not know, its indentation and its `---` marker. A file of comments alone keeps the comments before the new keys. A value that is not set is written as `null`. The comment lines that end a section stay after a key that the save adds to the section, so a new key does not go below the heading comment of the next section.
- A key that keeps its value stays out of the file: a default, a value of the other config file and a value of an environment variable.
- `devops config set` names its key to the save, so the file gets the key also when an environment variable or the other config file already gives the same value. A credential goes to the keyring, and the config file does not change. Before, a credential save rewrote the whole file.
- The keys that devops-cli does not know stay. `valkey.host`, `valkey.port` and `valkey.db` of an old file, which #2060 removed from the model, are such keys: the loader ignores them, and a save keeps them.
- A file that is not valid YAML, or that holds no mapping, stops the save with a `ConfigurationError` that names the file and does not quote its content. Before, the save replaced a file that held a sequence.
- The audit record of a write names the keys whose values changed in the file, so it names the keys that the save wrote.
- The eight callers of `save_settings` all stay, because each one must write the file (the table is in `design.md`). Each one has a test that names the keys that it writes.
- `ruamel.yaml==0.19.1` becomes a runtime dependency.
- A consumer observes the config file that the commands write, so the change carries a spec delta: two ADDED requirements in `config-commands`, and the changed scenario for the removed Valkey keys in `valkey-endpoint`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: a settings save writes only the changed keys and keeps the rest of the file, and each command that saves the settings writes only its own keys.
- `valkey-endpoint`: a save keeps the removed `valkey.host`, `valkey.port` and `valkey.db` keys of an old file.

## Impact

- Code: `src/devops_cli/config/round_trip.py` (new), `src/devops_cli/config/settings.py`, `src/devops_cli/config/write_history.py`, `src/devops_cli/commands/config.py` and `src/devops_cli/docs/generator.py`.
- Dependencies: `pyproject.toml` and `uv.lock` (`ruamel.yaml==0.19.1`, pure Python for the round trip; its C extension is an optional extra).
- Docs: `docs/CONFIGURATION.md` (generated), `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pyyaml_jinja2.md` and `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`.
- Tests: `tests/test_config_save_round_trip.py` (new), `tests/support/config_writes.py` (new), `tests/test_config_write_history.py`, `tests/commands/test_config.py`, `tests/test_ai_gateway.py`, `tests/test_ai_task_settings_paths.py`, `tests/test_k8s_bootstrap.py`, `tests/test_k8s_context.py`, `tests/test_run_store.py`, `tests/test_telemetry_collector_export.py`, `tests/test_valkey.py` and `tests/invariants/test_hermetic_floor.py`.

## Feasibility

- The ruamel.yaml documentation (`https://yaml.dev/doc/ruamel.yaml/overview/` and `/detail/`) says that a round trip keeps the comments, the block style, the key order, the flow style of a sequence and the hand-made anchor names, and that reassigning a value or replacing list items keeps this. It says that the round trip does not keep the indentation of each line: `yaml.indent(mapping=, sequence=, offset=)` sets one indentation for the document, and a file with inconsistent indentation becomes consistent at the first round trip. Collections that the round-trip parser reads have an `lc` property with the line and the column.
- PyPI: ruamel.yaml 0.19.1 was released on 2026-01-02. The project made ten releases in 2025, from 0.18.8 to 0.19.0. The round trip is pure Python; the C extension is the optional extra `libyaml`.
- Probed in the worktree with ruamel.yaml 0.19.1: a load and a dump of `config.example.yaml` with `preserve_quotes`, a mapping indentation of 2, the sequence indentation 4 and offset 2 from `ruamel.yaml.util.load_yaml_guess_indent`, and a representer that writes `null`, gives the same bytes. The same holds for a file that PyYAML wrote (sequence indentation 2, offset 0). With no changes to the settings, ruamel.yaml writes an empty value for `null` and drops a `---` marker. It attaches the comment lines between two sections to the last value of the first section (`CommentToken('# the org\n\n# valkey section\n')` on `github.default_org`), so `doc["github"]["new_key"] = ...` put the new key below `# valkey section`. `load_yaml_guess_indent` gives the indentation of the first block sequence, not the indentation of the mappings (4 for `config.example.yaml`, which indents its mappings by 2). The module handles these points.
- Library source: `CommentedMap.__setitem__` keeps the quote style of a replaced quoted scalar, and `CommentedMap.insert` moves no comment.
- On the base commit `1b257714`, `save_settings` has eight callers: `src/devops_cli/commands/ai_runs.py:171`, `src/devops_cli/commands/k8s/networking.py:960`, `src/devops_cli/commands/k8s/cluster_context.py:66`, `src/devops_cli/commands/ai.py:458`, `src/devops_cli/commands/telemetry.py:194`, `src/devops_cli/commands/ai_gateway.py:230`, and `src/devops_cli/commands/config.py:257` and `:358`.
- `load_settings` merges `~/.config/devops-cli/config.yaml`, the project config file and the `DEVOPS_CLI_*` variables (`_read_config_layers`, `_apply_env_overrides`). `.devcontainer/devcontainer.json` sets `DEVOPS_CLI_CONFIG` to the workspace `config.yaml`, so in the devcontainer the global file is the other layer. A comparison of the settings with the file that the save writes would copy the values of that layer and of the environment into the file.
- Cost of the copy that `load_settings` keeps, measured over 500 runs: `Settings.model_dump(mode="json")` takes 0.14 ms, and `Settings.model_validate({})` takes 2.8 ms.
- On the base commit, the 23 new and changed tests fail, because each save wrote the whole model: 10 in `tests/test_config_save_round_trip.py`, 5 in `tests/test_config_write_history.py` (`devops config set` is one of them), one in each of the seven test files of the other callers, and one in `tests/test_valkey.py`. After the change, they pass.

## Existing Tool Considered

ruamel.yaml in round-trip mode is the open, maintained tool for an edit of a YAML file that keeps its comments, its key order, its quotes and its unknown keys. pydantic's `model_dump` gives the values that the save compares, and PyYAML still reads the config files for the loader and for the audit record. Other tools do not cover the need: PyYAML drops the comments, strictyaml uses ruamel.yaml for its round trip and refuses parts of YAML that the config files use, such as flow sequences, and tomlkit edits TOML only.

The change builds four parts on ruamel.yaml: the mapping indentation from the `lc` positions that ruamel.yaml reads, the `null` representer on a subclass of the round-trip representer, the `---` marker from the events of `YAML.parse`, and the move of the comment lines that end a section. Cost: about 130 lines of code, about 300,000 tokens to build with its tests, about 15,000 tokens a year to keep and fix, and about 5 hours of elapsed time.

The change deletes `_prune_default_data_config` of `src/devops_cli/config/settings.py`, `_leaves` and `_ABSENT` of `src/devops_cli/config/write_history.py`, which `round_trip.leaves` and `round_trip.changes` replace, and the dump of the whole model with PyYAML in `save_settings`.
