## ADDED Requirements

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
