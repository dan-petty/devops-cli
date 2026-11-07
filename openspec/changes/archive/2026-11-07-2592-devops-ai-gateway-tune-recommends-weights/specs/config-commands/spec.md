## MODIFIED Requirements

### Requirement: devops config unset removes a key from the config file
`devops config unset <key>` SHALL remove the dotted key and its value from the active config file, and SHALL keep every other line, comment and key of the file. It SHALL load no settings, so it also removes a key that stops the settings from loading. It SHALL copy the file to `<name>.bak-<YYYYMMDD-HHMMSS>` before the change, and record the removed key in the audit log. A key name that holds a dot SHALL resolve as one key.

#### Scenario: A key that stops the settings from loading
- **WHEN** the config file holds comments and `ai.vllm_url`, `devops config get ai.provider` fails because of that key, and `devops config unset ai.vllm_url` runs
- **THEN** the command exits 0 and names the file, the line of the key and the copy, the file holds every line as before except the line of `ai.vllm_url`, the copy holds the file as before, and `devops config get ai.provider` exits 0

#### Scenario: A key whose name holds a dot
- **WHEN** the config file holds `ai.gateway_concurrency` with the keys `qwen3.8:27b` and `gemma4:26b`, and `devops config unset ai.gateway_concurrency.qwen3.8:27b` runs
- **THEN** the file holds `ai.gateway_concurrency` with `gemma4:26b` alone

### Requirement: devops config set refuses an unknown key before it asks for a value
`devops config set` SHALL take a key that names a settings field that holds a value, the `otel.<field>` name of a telemetry field, or a credential. For any other key, it SHALL exit 1 with the message `Unknown config key: '<key>'` before it asks for a value, reads `--from-file` or loads the settings, and it SHALL store nothing.

#### Scenario: An unknown key without a VALUE
- **WHEN** `devops config set no.such_key` runs
- **THEN** the command exits 1, its output is `Unknown config key: 'no.such_key'` alone, and the keyring and the config file do not change

#### Scenario: The keys that devops config set takes
- **WHEN** the key is `github.default_org`, `domain`, `ai.tasks.chat.model`, `service.github_app.app_id`, `otel.enabled`, `firecrawl.api_key`, `grafana.token` or `service.github_app.private_key`
- **THEN** the key is a config key, and the keys `ai`, `ai.tasks.chat`, `github.no_such_key`, `ai.gateway_concurrency.example-model` and `ai.model_dump` are not
