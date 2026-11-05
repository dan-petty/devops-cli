## ADDED Requirements

### Requirement: A write or an edit of a config file quotes no text of a file that a YAML parser cannot load
When devops-cli reads a config file without the settings load, and PyYAML or ruamel.yaml cannot load the file, the read SHALL fail with a configuration error. The message SHALL name the file and the type of the error, and the line and the column when the error gives them. The message, the exception chain of the error and the output of the command SHALL hold no text of the file.

#### Scenario: A local tag that ruamel.yaml accepts and PyYAML does not
- **WHEN** the active config file holds `ai:`, `  provider: ollama` and `  api_key: !vault FAKE-value-tag`, and `devops config unset ai.provider` runs
- **THEN** the command exits 1 with the message `Cannot read the config file: <file> is not valid YAML (ConstructorError) at line 3, column 12.`, the error has no cause and no context, no output holds `FAKE-value-tag`, and the file stays as it was

#### Scenario: A tagged value that a parser cannot build
- **WHEN** the round trip finds or edits a key in a file that holds `api_key: !!int FAKE-value-int` or `api_key: !!bool FAKE-value-bool`
- **THEN** it fails with a configuration error that names the file and the type of the error, `ValueError` or `KeyError`, the error has no cause and no context, and no text of the error holds the value in any case

#### Scenario: The audit record of a write
- **WHEN** the audit record of a write parses a file that holds `api_key: !vault FAKE-value-tag`
- **THEN** it fails with a configuration error that holds no text of the file
