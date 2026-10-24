# Design

## Context

`save_settings` (`src/devops_cli/config/settings.py`) wrote `Settings.model_dump(mode="json", exclude_none=True)` to the active config file with PyYAML. `load_settings` builds the settings from the global config file, the project config file and the `DEVOPS_CLI_*` variables. So each save wrote every default, the values of the other file and of the environment, and no comment and no unknown key. See `proposal.md` for the issue and the evidence.

## Goals / Non-Goals

**Goals:**

- A save writes only the keys that the command changed, and keeps every other line of the file.
- The decision for each of the eight callers, and a test for each caller that names the keys that it writes.

**Non-Goals:**

- No change to how `load_settings` reads and merges the files.
- No change to the copy before each write and to the audit record (#1921), other than the keys that the record names.

## Decisions

### What "only the changed keys" means

A save writes a key when its value after the command differs from its value when `load_settings` returned the settings. `load_settings` keeps `settings.model_dump(mode="json")` in the private attribute `Settings._loaded`, after the environment variables and the data paths apply. `round_trip.changes` compares that copy with the current dump, leaf by leaf, by key path. The edit then sets each changed key in the file. A changed key that the file already holds with its new value changes no byte, and a save that changes no byte writes nothing, as before.

So a key that the file does not hold and that keeps its default stays out of the file. A key that keeps the value of the other config file or of an environment variable stays out of the file too.

- **Rejected alternative: compare the settings with the current values of the file that the save writes** (each key whose value differs from the file, or from the default when the file does not hold it). The settings in memory merge the other config file and the environment, so this comparison writes their values into the file. Evidence: the floor of the test suite sets `DEVOPS_CLI_TELEMETRY_ENDPOINT` and `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK`, and in the devcontainer `DEVOPS_CLI_CONFIG` makes the workspace `config.yaml` the project layer over `~/.config/devops-cli/config.yaml`. `test_a_key_that_keeps_its_default_stays_out_of_a_new_file` holds the chosen rule: neither variable reaches the file.
- **Rejected alternative: compare with a new `load_settings()` at the time of the save.** A command such as `devops config init` waits for answers. When another process changes a key in that time, the new load holds the new value, the settings of the command hold the old one, and the save writes the old value back. The copy from the first load does not see a key that the command did not change.
- **Rejected alternative: each caller passes the keys that it writes, and the save writes only those.** A list that a caller keeps by hand misses keys. Evidence: `configure-urls` keeps the keys that it set in its `configured` table, but `_update_task_gateway_urls` changes `ai.tasks.analysis.api_base_url` and `ai.tasks.chat.api_base_url` and does not add them. `config init` changes a key only for an answer that is not blank. The comparison finds each changed key.
- Settings that code makes without `load_settings`, such as `Settings.model_validate({...})`, have no copy. They start from the defaults of the model, so each value that differs from the default is a change.

### `devops config set` writes the key that it names

A person who runs `devops config set <key> <value>` asks for the value in the file. When an environment variable or the other config file already gives the same value, the comparison finds no change, and the value would go when the variable goes. So `save_settings` takes `keys`, dotted keys that it writes also when their values did not change, and `config set` gives its key for each key that is not a credential. `_canonical_key` reads `otel.<field>` as `telemetry.<field>` for `dotted_get`, `dotted_set` and this list. The other callers give no keys: each sets a value that it detects or that a person answers, and a value that the loaded settings already hold is already in effect.

### The eight callers of save_settings

All eight stay: each one must write the file. On the base commit `1b257714`:

| Caller | Command | Why it writes | Keys that it writes, when their values change | Test that names the keys |
| :--- | :--- | :--- | :--- | :--- |
| `src/devops_cli/commands/ai_runs.py:171` | `devops ai runs connect` | It shares runs through the run index that it found. The password goes to the keyring. | `runs.index_url` | `tests/test_run_store.py::test_connect_finds_the_index_saves_it_and_indexes_local_runs` |
| `src/devops_cli/commands/k8s/networking.py:960` | `devops k8s configure-urls` | It saves the service URLs that it detects. It saves only when it configured a URL. | the URLs that detection changes: `argocd.url`, `grafana.url`, `prometheus.url`, `pyroscope.url`, `tempo.url` and `telemetry.endpoint` for the infra stack; `ai.ollama_urls`, `open_webui.url`, `qdrant.url` and `valkey.url` for the llm stack; `ai.gateway_url`, and `ai.tasks.<task>.api_base_url` of a task that uses the gateway | `tests/test_k8s_bootstrap.py::test_configure_urls_persists_all_infra_endpoints` |
| `src/devops_cli/commands/k8s/cluster_context.py:66` | `devops k8s switch-context` | `devops_cli.k8s.context` gives `k8s.context` to every cluster call of devops-cli. A switch that kept the old value would send the next command to the old cluster. It saves only when the value differs. | `k8s.context` | `tests/test_k8s_context.py::test_switch_context_other_cluster_does_not_start_minikube` |
| `src/devops_cli/commands/ai.py:458` | `devops ai config` | It is the command that sets the AI settings. With `--api-key` alone, the key goes to the keyring and the file does not change. | `ai.provider`, `ai.model`, `ai.ollama_urls`, `ai.ollama_max_parallel`, `ai.api_base_url` and `ai.max_retries`, or the same keys under `ai.tasks.<task>`, for the options that it gets | `tests/test_ai_task_settings_paths.py::test_ai_config_routes_one_task_to_the_gateway` |
| `src/devops_cli/commands/telemetry.py:194` | `devops telemetry connect` | It sends telemetry to the collector that it found. `--no-save` skips the save. | `telemetry.endpoint` and `telemetry.enabled` | `tests/test_telemetry_collector_export.py::test_connect_saves_an_endpoint_that_answers` |
| `src/devops_cli/commands/ai_gateway.py:230` | `devops ai gateway connect` | It points review calls at the gateway that it found, on the LAN path. | `ai.gateway_url` and `ai.allow_private_network` | `tests/test_ai_gateway.py::TestGatewayRouteDiscovery::test_use_lan_brackets_ipv6_host` |
| `src/devops_cli/commands/config.py:257` | `devops config set` | It is the command that sets one key. A credential goes to the keyring, and the file does not change. | the key that it names, also when its value does not change | `tests/test_config_write_history.py::test_config_set_records_its_command_and_writes_the_key_it_changed_alone`, `::test_config_set_of_a_credential_writes_no_config_file` and `tests/test_config_save_round_trip.py::test_config_set_writes_its_key_when_an_environment_variable_gives_the_same_value` |
| `src/devops_cli/commands/config.py:358` | `devops config init` | It is the setup wizard. A blank answer keeps the value. Tokens go to the keyring. | the keys that the answers change: `github.default_org`, `repos.base_dir`, `grafana.url`, `prometheus.url` and `argocd.url` | `tests/commands/test_config.py::test_config_init_names_the_active_config_file_it_writes` |

A test names the keys through the audit record of each write, which `tests/support/config_writes.py` reads, or through the whole text of the file.

### Unknown keys stay, the removed Valkey keys too

The issue asks to keep the keys that the model does not know, so the save keeps every key that it does not change. An old file holds `valkey.host`, `valkey.port` and `valkey.db`, which #2060 removed from the model. The loader ignores them (`ValkeyConfig` keeps `extra="ignore"`), no setting reads them, and a save keeps them as the file holds them. The `valkey-endpoint` scenario that said "a save writes only `url`, `timeout` and `threat_intel_ttl`" changes to say this. A person removes the old keys by hand, or keeps them for an older devops-cli.

- **Rejected alternative: a save drops the keys that a schema change removed.** The save would need a list of removed keys, which is a shim for an old schema, and it would also drop the keys of a newer devops-cli that shares the file.

### How the edit keeps the file

`round_trip.edit` loads the text with `YAML(typ="rt")` and `preserve_quotes`, sets each changed key path, removes each key path that a change removes, and dumps. A key path is a tuple, because a key can hold a dot, as the model names in `ai.gateway_weights` do. The four parts that ruamel.yaml does not do alone:

- **Indentation.** The mapping indentation is the column of the first key of the first nested block mapping, from `lc`, less the column of its parent key. The sequence indentation and offset come from `load_yaml_guess_indent`. With no block sequence in the file, a new sequence goes at the column of its key, as PyYAML writes it.
- **`null`.** A subclass of `RoundTripRepresenter` writes `null`. The round trip does not keep the spelling of a null, so `~` and an empty value become `null`, which is the spelling of PyYAML and of `config.example.yaml`.
- **`---` and a file of comments alone.** The events of `YAML.parse` tell when the document starts with `---`. ruamel.yaml loads a file of comments alone as nothing, so the edit puts the new keys after the text of that file.
- **The comment lines that end a section.** ruamel.yaml keeps the end-of-line comment of a value and the comment and blank lines after it in one token on the last scalar of the section. Before the edit adds a key to the section, or replaces a sequence or a mapping, it takes the lines after the end-of-line comment from that token. After the edit, it gives them to the last scalar of the new value. A removed key gives its lines to the new last scalar of its mapping.

A file that is not valid YAML, or whose document is not a mapping, raises `ConfigurationError` with the path. The message names the class of the YAML error and no part of the text, because the text can hold a credential.

- **Rejected alternative: PyYAML with a text patch of the changed lines.** It needs a second YAML parser for the positions of the keys, written here, and it cannot add a key to a section without one.
- **Rejected alternative: leave the comment lines where ruamel.yaml attaches them.** Probe on `config.example.yaml`: `devops ai gateway connect` would put `gateway_url` below `# ── Kubernetes`, and `ssh.key_prefix` would go below `# ── Repository management`. The YAML is the same, but a person reads the key under the wrong heading.

### The audit record

`write_history.record_write` takes the bytes before and after the write, and names the keys whose values differ between the two files. `write_history.changed_keys` uses `round_trip.changes`, so one comparison serves the save and the record. The `data` section needs no pruning any more: it changes only when a command changes a data path, so `_prune_default_data_config` goes.

## Risks / Trade-offs

- A file with mixed indentation gets one indentation at its first save, as the ruamel.yaml documentation says. The copy of the file before the write keeps the old text.
- A command that sets a key to the value that it had after the load writes nothing for it, apart from `devops config set`. For the detected values of the connect commands, the value is already in effect.
- The edit keeps the comments inside a sequence or a mapping only when the edit does not replace it. A changed list, such as `ai.ollama_urls`, loses the comments between its items. The comment lines after the list stay.
- A file with a duplicate key loads, because PyYAML keeps the last value, but a save refuses it: ruamel.yaml raises `DuplicateKeyError`, and the save names the file and the error class. The file stays as it is, and a person removes the duplicate.
- A removal of the one key of a file loses the comment lines after it. No caller removes a key at the top level: removals come from dictionary settings such as `ai.gateway_weights`.
