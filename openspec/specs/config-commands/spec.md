# config-commands Specification

## Purpose
What the `devops config` commands tell the user about the config file that they read and write.

## Requirements

### Requirement: devops config init names the file that it writes
When `devops config init` saves the settings, its `Config file:` line SHALL name the file that the wizard wrote, which is the active config path.

#### Scenario: DEVOPS_CLI_CONFIG names a different file
- **WHEN** `DEVOPS_CLI_CONFIG` names a file that is not the default config path, and the user completes `devops config init`
- **THEN** the wizard writes the new values to that file, and its `Config file:` line names that file

### Requirement: A settings save writes only the changed keys
When a command saves the settings, it SHALL write into the config file only the keys whose values the command changed after it loaded the settings. A key that keeps its default, or the value that the other config file or an environment variable gives, SHALL stay out of the file.

#### Scenario: A new config file
- **WHEN** a command changes `github.default_org` and saves into a file that does not exist, and the environment sets `DEVOPS_CLI_TELEMETRY_ENDPOINT` and `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK`
- **THEN** the new file holds `github.default_org` alone

### Requirement: A settings save keeps the rest of the config file
A save SHALL keep the comments, the order of the keys, the keys that devops-cli does not know and every line that it does not change in the config file.

#### Scenario: A file with comments, an unknown key and a changed key
- **WHEN** the config file holds comments, the unknown section `legacy_section`, the removed keys `valkey.host` and `valkey.port`, and `github.default_org: old-org`, and a command changes `github.default_org` to `new-org`
- **THEN** the file holds `new-org` in place of `old-org` and every other line as before, and the audit record of the write names `github.default_org` alone

#### Scenario: A copy of the example config
- **WHEN** the config file is a copy of `config.example.yaml`, and a command changes `github.default_org` and `ai.ollama_urls` and sets `ssh.key_prefix` and `runs.index_url`
- **THEN** the file changes in those lines alone: `key_prefix` is the line after `rotation_days`, before the heading comment of the next section, and the `runs` section is at the end

### Requirement: devops config set writes the key that it names
`devops config set` SHALL write the key that it names into the config file, also when the loaded settings already hold the value. For a credential, it SHALL write no config file.

#### Scenario: config set and a value from the environment
- **WHEN** `DEVOPS_CLI_GITHUB_DEFAULT_ORG` is `example-org`, and `devops config set github.default_org example-org` runs
- **THEN** the config file holds `github.default_org: example-org`

#### Scenario: config set of a credential
- **WHEN** `devops config set grafana.token <value>` runs
- **THEN** the command exits 0, the config file does not change, and the audit log records no config write

### Requirement: A settings save refuses a file that holds no mapping
A save into a file that is not valid YAML, or that holds no mapping, SHALL fail with a configuration error that names the file and does not quote its content, and SHALL leave the file as it is.

#### Scenario: A file that holds no mapping
- **WHEN** the config file holds a YAML sequence, or text that is not valid YAML, and a command saves a changed key
- **THEN** the save fails with the exit code 1 and the error code `CONFIGURATION_ERROR`, the message names the file, and the file and its directory do not change

### Requirement: Each command that saves the settings writes only its own keys
Each command that saves the settings SHALL write only the keys that it changes. The scenario of each command names its keys.

#### Scenario: devops ai runs connect
- **WHEN** `devops ai runs connect` finds the run index and the index answers
- **THEN** the one config write names `runs.index_url` alone

#### Scenario: devops k8s configure-urls
- **WHEN** `devops k8s configure-urls --stack infra` detects the ArgoCD, Grafana, Prometheus, Pyroscope and Tempo services
- **THEN** the one config write names `argocd.url`, `grafana.url`, `prometheus.url`, `pyroscope.url`, `telemetry.endpoint` and `tempo.url`

#### Scenario: devops k8s configure-urls task gateway URLs
- **WHEN** `devops k8s configure-urls` changes only task gateway URLs
- **THEN** the one config write names each changed `ai.tasks.<task>.api_base_url` key, and the report displays the changed keys

#### Scenario: devops k8s switch-context
- **WHEN** the config file holds `k8s.context: default`, and `devops k8s switch-context production-cluster` runs
- **THEN** the file holds `k8s.context: production-cluster` and nothing more

#### Scenario: devops ai config
- **WHEN** `devops ai config --task chat --provider gateway --model devops-coder` runs
- **THEN** the one config write names `ai.tasks.chat.model` and `ai.tasks.chat.provider`

#### Scenario: devops telemetry connect
- **WHEN** the config file holds `telemetry.enabled: false`, and `devops telemetry connect` finds a collector that answers
- **THEN** the file holds `telemetry.enabled: true` and the `telemetry.endpoint` of the collector, and nothing more

#### Scenario: devops ai gateway connect
- **WHEN** the config file holds `ai.allow_private_network: false`, and `devops ai gateway connect` finds a gateway that answers
- **THEN** the one config write names `ai.allow_private_network` and `ai.gateway_url`

#### Scenario: devops config set
- **WHEN** `devops config set github.default_org first-org` runs
- **THEN** the config file gets `github.default_org: first-org` after its other lines, and the audit record names `github.default_org` alone

#### Scenario: devops config init
- **WHEN** the answers to `devops config init` name a new default org and a new repos directory, and skip the other questions
- **THEN** the one config write names `github.default_org` and `repos.base_dir`

### Requirement: Settings values validate against field types at load and on set
When settings values load from environment variables or configuration files, or update through `devops config set`, each value SHALL pass the declared type and constraints of its field. An invalid value SHALL cause the load or command to fail with a configuration error naming the setting or environment variable without exposing sensitive input text.

#### Scenario: Non-positive timeout in environment variable is refused
- **WHEN** an environment variable sets a timeout or duration field to `0`, `-1`, `inf`, or non-numeric text
- **THEN** loading settings fails with a configuration error naming the environment variable

#### Scenario: Malformed URL in configuration file or command is refused
- **WHEN** a configuration file or `devops config set` specifies a URL lacking an approved scheme or matching host origin
- **THEN** the operation fails with an error naming the key without exposing credentials

### Requirement: devops config unset removes a key from the config file
`devops config unset <key>` SHALL remove the dotted key and its value from the active config file, and SHALL keep every other line, comment and key of the file. It SHALL load no settings, so it also removes a key that stops the settings from loading. It SHALL copy the file to `<name>.bak-<YYYYMMDD-HHMMSS>` before the change, and record the removed key in the audit log. A key name that holds a dot SHALL resolve as one key.

#### Scenario: A key that stops the settings from loading
- **WHEN** the config file holds comments and `ai.vllm_url`, `devops config get ai.provider` fails because of that key, and `devops config unset ai.vllm_url` runs
- **THEN** the command exits 0 and names the file, the line of the key and the copy, the file holds every line as before except the line of `ai.vllm_url`, the copy holds the file as before, and `devops config get ai.provider` exits 0

#### Scenario: A key whose name holds a dot
- **WHEN** the config file holds `ai.gateway_weights` with the keys `qwen3.8:27b` and `gemma4:26b`, and `devops config unset ai.gateway_weights.qwen3.8:27b` runs
- **THEN** the file holds `ai.gateway_weights` with `gemma4:26b` alone

### Requirement: The copies of devops config unset hold no credential value
The copies of the file that `devops config unset` keeps SHALL hold no value of a credential that the removal takes out of the file. A copy shows such a value as `***REDACTED***`, with the key in place. This holds for the new copy, for each older retained copy, and for a credential below a removed section.

#### Scenario: A credential key
- **WHEN** the config file holds `ai.api_key` with the value `FAKE-2645-value` and `ai.model`, and `devops config unset ai.api_key` runs
- **THEN** no file in the directory holds `FAKE-2645-value`, and the new copy holds `ai.api_key` with the value `***REDACTED***` and `ai.model` as before

#### Scenario: A credential in an older copy
- **WHEN** 10 older copies hold `ai.api_key` with a value, and `devops config unset ai.api_key` runs
- **THEN** 10 copies stay, and none holds the value

#### Scenario: A section that holds a credential
- **WHEN** the config file holds `ai.api_key` with a value, and `devops config unset ai` runs
- **THEN** the copy holds `ai.api_key` with the value `***REDACTED***`

#### Scenario: A key that is not a credential
- **WHEN** `devops config unset ai.model` runs
- **THEN** the copy holds the file as it was before the change

### Requirement: The copies of devops config unset keep the rest of the file
A comment line of a copy that holds the value SHALL lose its comment text. Every other line of a copy SHALL stay as it was, with its line ends. A copy SHALL keep the mode of the file, and the command SHALL keep the newest 10 copies.

#### Scenario: A comment that holds the value
- **WHEN** the config file holds `ai.api_key` with the line comment `# was <value>`, and `devops config unset ai.api_key` runs
- **THEN** the copy holds no `<value>`, and its other comments stay

#### Scenario: A copy with CRLF line ends
- **WHEN** the config file and an older copy have CRLF line ends, and `devops config unset ai.api_key` runs
- **THEN** each copy holds CRLF line ends, and only the credential changed

### Requirement: devops config unset stops for a copy that it cannot redact
A copy that is not UTF-8 text, is not YAML, or does not hold a YAML mapping SHALL stop `devops config unset` with an error that names the copy and quotes no text. The command SHALL stop before the config file changes, and SHALL make no new copy.

#### Scenario: A copy that is not a YAML mapping
- **WHEN** an older copy is not UTF-8 text, is not YAML, or is a YAML list or a plain line, and `devops config unset ai.api_key` runs
- **THEN** the command exits 1 with an error that names the copy and quotes no value, the config file stays as it was, and no new copy is made

### Requirement: devops config unset refuses a key that the file does not hold
When the active config file does not hold the key, `devops config unset <key>` SHALL exit 1 with a message that names the file and the key, and SHALL leave the file and its directory as they are.

#### Scenario: A key that the file does not hold
- **WHEN** `devops config unset ai.no_such_key` runs and the config file does not hold that key
- **THEN** the command exits 1 with the message `The config file <file> does not hold the key 'ai.no_such_key'. Nothing changed.`, and the file and its directory do not change

### Requirement: devops config unset --dry-run writes nothing
`devops config unset <key> --dry-run` SHALL print the dry-run response with the file, the key, its line and the lines of the unified diff of the removal, and SHALL write no file and no audit record.

#### Scenario: A dry run of a removal
- **WHEN** `devops config unset ai.vllm_url --dry-run` runs and the config file holds `ai.vllm_url` on line 7
- **THEN** the command exits 0, the dry-run response holds the key, the line 7 and the diff lines `@@ -7 +6,0 @@` and `-  vllm_url: <value>`, and the file, its directory and the audit log do not change

### Requirement: The error of a refused key names its file, its line and the command that removes it
When a config file holds a key that a settings section refuses (`ai`, `ai.tasks` or `ai.tasks.<task>`), loading the settings SHALL fail with a configuration error that gives one line for each such key. The line SHALL name the full dotted key, the file and the line of the key, and the `devops config unset` command that removes it. For a key in a config file that is not the active one, the command SHALL set `DEVOPS_CLI_CONFIG` to that file.

#### Scenario: An unknown key in each refusing section
- **WHEN** the active config file holds `no_such_key` in `ai`, in `ai.tasks` or in one `ai.tasks.<task>`, and a command loads the settings
- **THEN** the load fails with the exit code 1 and the error code `CONFIGURATION_ERROR`, and the message names the full dotted key, such as `ai.tasks.chat.no_such_key`, its file and line, and `devops config unset` with that key

#### Scenario: A key in the config file that is not the active one
- **WHEN** the config file that is not the active one holds `ai.vllm_url` on line 4
- **THEN** the message names that file and line 4, and the command `DEVOPS_CLI_CONFIG=<that file> devops config unset ai.vllm_url`

### Requirement: The error of a refused key gives the reason when it is known
For a key that a release removed, the line of the error SHALL name the release. For a per-model sampling or serving setting, the line SHALL say that the setting belongs in a gateway deployment's `litellm_params` or the Ollama tag.

#### Scenario: A key that a release removed
- **WHEN** the active config file holds `ai.vllm_url` on line 8, and a command loads the settings
- **THEN** the message is `Unknown configuration key 'ai.vllm_url' at <file>:8. Release 0.2.34 removed it. Remove it with: devops config unset ai.vllm_url`

#### Scenario: A per-model sampling setting
- **WHEN** the active config file holds `ai.tasks.analysis.top_k`, and a command loads the settings
- **THEN** the message names `ai.tasks.analysis.top_k` and its line, says that per-model sampling and serving settings belong in a gateway deployment's `litellm_params` or the Ollama tag, and names `devops config unset ai.tasks.analysis.top_k`

### Requirement: devops config audit-keys exits 0 only on a compliant audit
`devops config audit-keys` SHALL exit 0 only when no config file that it scans holds a plaintext secret and it reads and parses each of these files. It SHALL exit 1 when a config file holds a plaintext secret, or when it cannot read or parse a config file. The table output and each serialized output SHALL print the full report before the exit. The command SHALL print its success line only when it exits 0.

#### Scenario: A plaintext secret in the table output
- **WHEN** the active config file holds `grafana.token` with a value, and `devops config audit-keys` runs
- **THEN** the table shows `LEAK DETECTED` for `grafana.token`, the security alert names the leak, the success line does not show, and the command exits 1

#### Scenario: A plaintext secret in the JSON output
- **WHEN** the active config file holds `grafana.token` with a value, and `devops config audit-keys --json` runs
- **THEN** the JSON report holds `is_compliant: false` and the leak of `grafana.token` under `plaintext_leaks`, and the command exits 1

#### Scenario: A compliant config
- **WHEN** no config file that the audit scans holds a secret value, and each of these files parses
- **THEN** the command exits 0, and the table output shows the success line

#### Scenario: A config file that does not parse
- **WHEN** the active config file is not valid YAML, and `devops config audit-keys` runs
- **THEN** the command reports the file unaudited, the success line does not show, and the command exits 1

### Requirement: devops config set refuses an unknown key before it asks for a value
`devops config set` SHALL take a key that names a settings field that holds a value, the `otel.<field>` name of a telemetry field, or a credential. For any other key, it SHALL exit 1 with the message `Unknown config key: '<key>'` before it asks for a value, reads `--from-file` or loads the settings, and it SHALL store nothing.

#### Scenario: An unknown key without a VALUE
- **WHEN** `devops config set no.such_key` runs
- **THEN** the command exits 1, its output is `Unknown config key: 'no.such_key'` alone, and the keyring and the config file do not change

#### Scenario: The keys that devops config set takes
- **WHEN** the key is `github.default_org`, `domain`, `ai.tasks.chat.model`, `service.github_app.app_id`, `otel.enabled`, `firecrawl.api_key`, `grafana.token` or `service.github_app.private_key`
- **THEN** the key is a config key, and the keys `ai`, `ai.tasks.chat`, `github.no_such_key`, `ai.gateway_weights.example-model` and `ai.model_dump` are not

### Requirement: The message of an unknown key names the known keys with a similar name
When known keys have a name similar to the unknown key, a second line after `Unknown config key: '<key>'` SHALL name them, the nearest first. `devops config get` SHALL print the same lines for a key that it cannot find.

#### Scenario: A removed key with a VALUE
- **WHEN** `devops config set tavily.api_key <value>` runs
- **THEN** the command exits 1, its output is `Unknown config key: 'tavily.api_key'` and `Known keys with a similar name: ai.api_key, firecrawl.api_key, qdrant.api_key`, and the keyring and the config file do not change

#### Scenario: An unknown key with --from-file
- **WHEN** `devops config set firecrawl.apikey --from-file -` runs with a value on stdin
- **THEN** the command exits 1, its output is `Unknown config key: 'firecrawl.apikey'` and `Known keys with a similar name: firecrawl.api_key, ai.api_key, qdrant.api_key`, and the keyring and the config file do not change

#### Scenario: devops config get of an unknown key
- **WHEN** `devops config get firecrawl.apikey` runs
- **THEN** the command exits 1, and its output is `Unknown config key: 'firecrawl.apikey'` and `Known keys with a similar name: firecrawl.api_key, ai.api_key, qdrant.api_key`

### Requirement: A config file that is not valid YAML stops the load with an error that quotes none of its text
When a config file that the settings load from is not valid YAML, is not UTF-8, or holds a tagged value that the YAML loader cannot build, the load of the settings SHALL fail with a configuration error. The message SHALL name the file and the type of the error, and the line and the column when the error gives them. The message, the exception chain of the error and the output of the load SHALL hold no text of the file.

#### Scenario: A line that does not parse holds a credential
- **WHEN** the active config file holds `ai:` and the line `  api_key: FAKE-value: x`, and a command loads the settings
- **THEN** the load fails with the exit code 1 and the error code `CONFIGURATION_ERROR`, the message is `Cannot load the settings: <file> is not valid YAML (ScannerError) at line 2, column 22.`, the error has no cause and no context, and no output holds `FAKE-value`

#### Scenario: A tagged value that the YAML loader cannot build holds a credential
- **WHEN** the active config file holds `ai:` and the line `  api_key: !!int FAKE-value`, and a command loads the settings
- **THEN** the load fails with the message `Cannot load the settings: <file> is not valid YAML (ValueError).`, the error has no cause and no context, and no output holds `FAKE-value`

### Requirement: devops config get reports a config file that does not load on one line
When the settings do not load because a config file is not valid YAML, `devops config get` SHALL print the message of the error on one line and exit 1. Its output SHALL hold no traceback and no text of the file.

#### Scenario: devops config get with a line that does not parse
- **WHEN** the active config file holds `ai:` and the line `  api_key: FAKE-value: x`, and `devops config get ai.provider` runs
- **THEN** the command prints `✗ Cannot load the settings: <file> is not valid YAML (ScannerError) at line 2, column 22.` on one line, prints no traceback and no text of the file, and exits 1

### Requirement: The variable of a setting follows its key
A variable SHALL set each declared setting. Its name SHALL be `DEVOPS_CLI_` and the setting's dotted key in upper case, with `_` for `.`, and with `TASK` for the `tasks` segment of `ai.tasks`.

#### Scenario: A plain setting and a task setting
- **WHEN** `DEVOPS_CLI_AI_REFERENCE_MODEL` is `gpt-5` and `DEVOPS_CLI_CLOUDFLARE_ACCESS_BYPASS_IPS` is `192.0.2.1, 198.51.100.0/24`, and the settings load
- **THEN** `ai.reference_model` is `gpt-5` and `cloudflare.access.bypass_ips` is `["192.0.2.1", "198.51.100.0/24"]`

#### Scenario: The variable of a task setting
- **WHEN** the variable of `ai.tasks.chat.provider` is read
- **THEN** it is `DEVOPS_CLI_AI_TASK_CHAT_PROVIDER`

### Requirement: devops config env lists every variable that sets a setting or a credential
`devops config env` and `docs/ENV_VARS.md` SHALL list the variable of every declared setting and of every credential, each with a description.

#### Scenario: The variables that the list missed
- **WHEN** `devops config env` lists its variables
- **THEN** the list holds `DEVOPS_CLI_AI_TASK_CHAT_REASONING_EFFORT`, `DEVOPS_CLI_AI_RAG_TOP_K` and `DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD`, and no listed variable has an empty description

### Requirement: devops config show lists every setting and every credential
`devops config show` SHALL print each declared setting and each credential once, sorted by key. It SHALL print a credential that has a value as `****`, never its value. `--json` SHALL print the rows as a list of objects with `key` and `value`.

#### Scenario: A credential and a setting from the environment
- **WHEN** `DEVOPS_CLI_GRAFANA_TOKEN` and `DEVOPS_CLI_AI_MODEL` are set, and `devops config show --json` runs
- **THEN** the row of `grafana.token` has the value `****`, the row of `ai.model` has the value of the variable, and the output does not hold the token

### Requirement: A setting resolves in one declared order
`load_settings` SHALL resolve each setting from the first source that holds it, in this order: its variable, the project config file, the global config file. A setting that no source holds SHALL keep the default of its field. Only the value that a setting takes SHALL be checked against the type of the setting.

#### Scenario: Each layer in turn
- **WHEN** `ai.reference_model` is set by `DEVOPS_CLI_AI_REFERENCE_MODEL`, the project config file and the global config file, and then by fewer of them in turn
- **THEN** the loaded value is the variable's, then the project file's, then the global file's, then the default

#### Scenario: A variable replaces a file value that does not validate
- **WHEN** the project config file holds `qdrant.timeout: 0` and `DEVOPS_CLI_QDRANT_TIMEOUT` is `45`
- **THEN** the settings load, and `qdrant.timeout` is `45.0`

#### Scenario: A file value that does not validate
- **WHEN** the project config file holds `qdrant.timeout: 0` and no variable sets it
- **THEN** the load fails with a validation error at `qdrant.timeout` that names no variable

### Requirement: Settings built in code hold their arguments and the defaults
`Settings(...)` built in code SHALL hold its arguments and the field defaults, and SHALL read no variable and no config file.

#### Scenario: A variable and a config file are set
- **WHEN** `DEVOPS_CLI_DOMAIN` and `DEVOPS_CLI_AI_REFERENCE_MODEL` are set, the project config file sets `ai.model`, and `Settings(github={"default_org": "example-org"})` is built
- **THEN** its `domain`, `ai.reference_model` and `ai.model` are the defaults, and `github.default_org` is `example-org`

### Requirement: A config file that holds no mapping stops the load
When the project or the global config file holds a YAML document that is not a mapping of keys to values, `load_settings` SHALL fail with `Cannot load the settings: <file> does not hold a mapping of keys to values.`

#### Scenario: A config file that holds a list
- **WHEN** the project config file, or the global config file, holds a YAML list
- **THEN** the load fails with the message that names that file

### Requirement: A credential resolves in its own declared order
A credential SHALL resolve from the OS keyring, then Vault, then its variable, then the config file for a credential that a config file can hold.

#### Scenario: Each layer of `qdrant.api_key` in turn
- **WHEN** `qdrant.api_key` is in the keyring, Vault, `DEVOPS_CLI_QDRANT_API_KEY` and the project config file, and then in fewer of them in turn
- **THEN** the resolved value is the keyring's, then Vault's, then the variable's, then the file's, then none

### Requirement: devops config audit-keys scans each config file that the settings merge
`devops config audit-keys` SHALL scan each config file that the settings load from: the global config file and the project config file. The report SHALL list each of these files that exists under `scanned_config_files`. A plaintext secret in any of these files SHALL fail the audit.

#### Scenario: A plaintext secret in the global config file and a project file that DEVOPS_CLI_CONFIG names
- **WHEN** the global config file holds `ai.api_key` with a value, `DEVOPS_CLI_CONFIG` names a file that holds no secret, and `devops config audit-keys --json` runs
- **THEN** `scanned_config_files` holds the global config file and the file that `DEVOPS_CLI_CONFIG` names, `plaintext_leaks` holds `<global config file path>:ai.api_key`, `is_compliant` is false, and the command exits 1

#### Scenario: A plaintext secret in the global config file and a project file that the directory walk finds
- **WHEN** the global config file holds `ai.api_key` with a value, `DEVOPS_CLI_CONFIG` is not set, the current directory holds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys --json` runs
- **THEN** `scanned_config_files` holds the global config file and `.devcontainer/config.yaml`, `plaintext_leaks` holds `<global config file path>:ai.api_key`, `is_compliant` is false, and the command exits 1

### Requirement: A leak of devops config audit-keys names the full path of its file
Each leak that `devops config audit-keys` reports SHALL name the full path of its file, as `<path>:<section>.<key>`, in the table output and in each serialized output.

#### Scenario: The table names the full path of the global config file that holds a secret
- **WHEN** the global config file holds `ai.api_key` with a value, the directory walk finds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys` runs
- **THEN** the security alert names `<global config file path>:ai.api_key`, and the command exits 1

### Requirement: devops config audit-keys quotes no text of a config file that it cannot load
`devops config audit-keys` SHALL report a config file that the YAML loader of the settings cannot load as unaudited. No output or log of the audit SHALL quote the text of that file.

#### Scenario: A global config file that the YAML loader cannot load
- **WHEN** the global config file holds `ai:` and `  api_key: !!bool <text>`, and `devops config audit-keys --json` runs
- **THEN** `unaudited_config_files` holds the global config file and `plaintext_leaks` is empty. The log names the file and `KeyError`, no output or log holds `<text>`, and the command exits 1

### Requirement: A setting reaches each module that reads it
A module outside `config/` SHALL read a setting from the loaded settings. Where it has no loaded settings, it SHALL read the default that the setting's field declares (`setting_default`). It SHALL NOT read a `DEFAULT_*` name that a settings field takes as its default.

#### Scenario: The chunk size and overlap of the RAG index
- **WHEN** the project config file sets `ai.rag.chunk_size: 900` and `ai.rag.chunk_overlap: 90`, and a `SemanticChunker` is built with no sizes
- **THEN** it splits files by 900 and 90

#### Scenario: The defaults of a RAG search
- **WHEN** `DEVOPS_CLI_AI_RAG_TOP_K` is `9` and `DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD` is `0.6`, and `devops --dry-run ai rag query` runs with no `--top-k` and no `--min-score`
- **THEN** the dry run shows `top_k` 9 and `min_score` 0.6

#### Scenario: A retriever with no defaults
- **WHEN** `DEVOPS_CLI_AI_RAG_TOP_K` is `7` and `DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD` is `0.55`, and a `SemanticRetriever` is built with no defaults
- **THEN** its default top-k is 7 and its default score threshold is 0.55

#### Scenario: The sampling that group analysis records
- **WHEN** the project config file sets `ai.tasks.analysis.temperature: 0.7` and `ai.tasks.analysis.top_p: 0.8`, and group analysis runs with no sampling given
- **THEN** the report records temperature 0.7 and top-p 0.8

#### Scenario: An audit log destination in the configured data directory
- **WHEN** the project config file sets `data.dir`, no `DEVOPS_CLI_DATA_DIR` is set, and `DEVOPS_CLI_AUDIT_LOG_DEST` names a file in that directory
- **THEN** an audit event is written to that file

#### Scenario: The GitHub quota ledger
- **WHEN** `DEVOPS_CLI_DATA_CACHE_DIR` names a directory
- **THEN** the cache directory of each GitHub identity is in that directory

#### Scenario: The state of the roadmap Service
- **WHEN** the project config file sets `data.dir` and no `DEVOPS_CLI_DATA_DIR` is set
- **THEN** the Service keeps its state in `roadmap` under that directory

#### Scenario: The snapshot digest of the OSV database
- **WHEN** `DEVOPS_CLI_DATA_CACHE_DIR` names a directory that holds an `osv_db` database, and the digest is computed with no directory given
- **THEN** the digest is stamped in `osv_db` under that directory

### Requirement: The alert of devops config audit-keys names the commands that remove a leak
The alert for a plaintext secret SHALL name `devops config set <key>`, with `--from-file <path>` for a multi-line credential. It SHALL name `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`, which removes the value from the file of the leak. It SHALL NOT name a value in the argument list.

#### Scenario: A leak in the global config file while a project file is active
- **WHEN** the global config file holds `ai.api_key` with a value, the directory walk finds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys` runs
- **THEN** the alert names both commands, and the command exits 1. A plain `devops config unset ai.api_key` exits 1 and changes nothing. `DEVOPS_CLI_CONFIG=<global config file> devops config unset ai.api_key` exits 0. The next `devops config audit-keys` exits 0 with no leak

#### Scenario: A leak in the config.yaml of the current directory that the settings do not merge
- **WHEN** `config.yaml` in the current directory holds `grafana.token` with a value, `DEVOPS_CLI_CONFIG` names another file with no secret, and `devops config audit-keys` runs
- **THEN** the alert names the same commands. `DEVOPS_CLI_CONFIG=<that config.yaml> devops config unset grafana.token` exits 0. The next `devops config audit-keys` exits 0 with no leak

#### Scenario: A multi-line credential
- **WHEN** the global config file holds `argocd.github_app_private_key` as a PEM block, and a person follows the alert with `--from-file <path>` and then the removal command
- **THEN** the keyring holds the whole PEM text, the removal exits 0, and the next `devops config audit-keys` exits 0

### Requirement: The alert of devops config audit-keys warns about the quotes
The alert SHALL say to quote the file and the key for the shell. It SHALL name no copy of the file to delete, because the removal leaves no copy that holds the value.

#### Scenario: The alert for a leak
- **WHEN** the global config file holds `ai.api_key` with a value and `devops config audit-keys` runs
- **THEN** the alert holds "Quote <file> and <key> for the shell." and names no `.bak-` copy

### Requirement: The alert of devops config audit-keys prints for any name
The audit SHALL print the alert and the line of an unaudited file for any section name, key name or path. A name that is markup for the terminal, such as `[/x]`, SHALL NOT stop the print.

#### Scenario: A section name that is markup
- **WHEN** `config.yaml` in the current directory holds the section `[/x]` with the key `grafana.token` and a value, and `devops config audit-keys` runs
- **THEN** the alert names `[/x].grafana.token`, and the command exits 1

#### Scenario: A directory name that is markup
- **WHEN** `DEVOPS_CLI_CONFIG` names a file that is not valid YAML in the directories `[` and `x]`, and `devops config audit-keys` runs
- **THEN** the line of the unaudited file names the path, and the command exits 1

### Requirement: The help of devops config names the commands that remove a leak
The help of `devops config audit-keys` SHALL name the same commands as its alert. The help of `devops config unset` SHALL say that `DEVOPS_CLI_CONFIG` names the file that the command edits, and that `--from-file <path>` stores a multi-line credential.

#### Scenario: The help names the commands
- **WHEN** `devops config audit-keys --help` and `devops config unset --help` run
- **THEN** the help of `audit-keys` holds `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` and `--from-file <path>`. The help of `unset` says that `DEVOPS_CLI_CONFIG` names the file that the command edits

### Requirement: merge-key-unset-reports-clear-error
When the target key is present only through a YAML merge key, devops config unset SHALL exit with code 1 and print a message that names the file and states the key comes from a merge key. It SHALL NOT print a Python traceback.

#### Scenario: unset a merge-derived key
- **WHEN** the config file defines the key via <<: *anchor and the user runs devops config unset on that key
- **THEN** the command exits 1, prints a message naming the file and mentioning the merge key, and prints no Python traceback

### Requirement: direct-key-removal-unchanged
When the target key is directly present in the file, devops config unset SHALL remove the key and exit with code 0.

#### Scenario: unset a directly-present key
- **WHEN** the config file holds the key as a direct entry and the user runs devops config unset on that key
- **THEN** the key is removed from the file and the command exits 0

### Requirement: Preserve existing file mode on write
A write of a config file that already exists MUST preserve the mode of the existing file.

#### Scenario: Write to a 0600 file
- **WHEN** A config file with mode 0600 is written by devops config set or devops config unset
- **THEN** The resulting file has mode 0600

### Requirement: New config file gets mode 0600
A config file that does not exist and is created by a write MUST be created with mode 0600.

#### Scenario: Create a new config file
- **WHEN** A write creates a config file that did not exist before
- **THEN** The new file has mode 0600

### Requirement: Backup copy keeps source mode
A backup copy of a config file MUST have the same mode as the source file.

#### Scenario: Copy a 0600 file
- **WHEN** A backup copy is made of a config file with mode 0600
- **THEN** The copy has mode 0600

### Requirement: Temporary file never more open than source
A temporary file written during a config write MUST have a mode no more open than the file it replaces, or 0600 when no file exists.

#### Scenario: Tmp file mode during redact copy
- **WHEN** A temporary file is created during a redacted copy of a config file with mode 0600
- **THEN** The temporary file has mode 0600 before it is replaced by os.replace
