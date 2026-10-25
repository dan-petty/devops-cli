# Spec Delta

## ADDED Requirements

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
