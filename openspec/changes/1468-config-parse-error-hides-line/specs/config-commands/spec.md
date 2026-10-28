## ADDED Requirements

### Requirement: A config file that is not valid YAML stops the load with an error that quotes none of its text
When a config file that the settings load from is not valid YAML, the load of the settings SHALL fail with a configuration error. The message SHALL name the file, the type of the YAML error, and the line and the column where the parser stopped. The message, the exception chain of the error and the output of the command SHALL hold no text of the file. `devops config get` SHALL print the message on one line and exit 1, with no traceback.

#### Scenario: A line that does not parse holds a credential
- **WHEN** the active config file holds `ai:` and the line `  api_key: FAKE-value: x`, and a command loads the settings
- **THEN** the load fails with the exit code 1 and the error code `CONFIGURATION_ERROR`, the message is `Cannot load the settings: <file> is not valid YAML (ScannerError) at line 2, column 22.`, the error has no cause and no context, and no output holds `FAKE-value`

#### Scenario: devops config get with that file
- **WHEN** the active config file holds that line, and `devops config get ai.provider` runs
- **THEN** the command prints `✗ Cannot load the settings: <file> is not valid YAML (ScannerError) at line 2, column 22.` and nothing more, and exits 1
