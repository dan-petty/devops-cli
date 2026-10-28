## ADDED Requirements

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
