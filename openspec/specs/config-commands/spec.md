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
