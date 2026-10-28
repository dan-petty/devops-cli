## ADDED Requirements

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
