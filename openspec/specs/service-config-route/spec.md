# service-config-route Specification

## Purpose
The `GET /api/v1/config` route of the Service REST API and the active, non-secret configuration that it returns.

## Requirements

### Requirement: The config route returns the active settings
The `GET /api/v1/config` route SHALL build its reply from `load_settings()`, which reads the declared variables and the config files, and SHALL NOT use the bare `Settings()` constructor that reads no source.

#### Scenario: An environment variable reaches the reply
- **WHEN** `DEVOPS_CLI_AI_MODEL` is `example-model` and a client sends `GET /api/v1/config`
- **THEN** `config.ai.model` in the reply is `example-model`

#### Scenario: A config file value reaches the reply
- **WHEN** the project config file holds `ai.model: example-model` and no variable overrides it
- **THEN** `config.ai.model` in the reply is `example-model`

### Requirement: The config route redacts secrets
The `GET /api/v1/config` route SHALL replace every secret field that `secret_keys()` names with `***REDACTED***` when the loaded settings hold a value for it.

#### Scenario: A loaded secret is masked
- **WHEN** the loaded settings hold a value for `valkey.password`
- **THEN** `config.valkey.password` in the reply is `***REDACTED***` and the reply holds no clear text of the value
