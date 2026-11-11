## ADDED Requirements

### Requirement: The settings load reads a config file as YAML 1.2
The settings load SHALL read each config file as YAML 1.2, the version that a settings save writes. A bare `off`, `on`, `yes` or `no` SHALL load as a string, and a bare `true` or `false` SHALL load as a bool. A key that a mapping holds two times SHALL stop the load with a configuration error that names the file, the line and the column, and that quotes no text of the file.

#### Scenario: A bare off or on for the intake mode
- **WHEN** the active config file holds `roadmap.intake.jev` with the bare value `off`, or with the bare value `on`
- **THEN** `load_settings()` gives `roadmap.intake.jev` equal to that string

#### Scenario: A bare off for a decision point
- **WHEN** the active config file holds `roadmap.decisions` with `stage.verify_screen: off`
- **THEN** `load_settings()` gives the mode `off` for `stage.verify_screen`

#### Scenario: A YAML bool for the intake mode
- **WHEN** the active config file holds `roadmap.intake.jev: true`
- **THEN** `load_settings()` raises a validation error for the field `roadmap.intake.jev`

#### Scenario: A key that a mapping holds two times
- **WHEN** the active config file holds `ai:`, `  provider: ollama` and `  provider: FAKE-value`
- **THEN** the load fails with the message `Cannot load the settings: <file> is not valid YAML (DuplicateKeyError) at line 3, column 3.`, the error has no cause and no context, and no output holds `FAKE-value`

### Requirement: devops config set writes a value that the next load reads as the same string
After `devops config set <key> <value>` writes a string setting to the config file, the next settings load SHALL give the same string, also for a word that YAML 1.1 reads as a bool or a number.

#### Scenario: A word that YAML 1.1 reads as a bool or a number
- **WHEN** `devops config set` runs with `roadmap.intake.jev off`, with `search.language no` or with `k8s.context 12:30`
- **THEN** the command exits 0, and `devops config get` of the key prints the value that was set

### Requirement: The audit record of a config write compares the values as YAML 1.2
The audit record of a config write SHALL read the file before and after the write as YAML 1.2, and it SHALL name only the keys whose values changed.

#### Scenario: A quoted value that a write makes bare
- **WHEN** a write changes the line `  context: "12:30"` under `k8s:` to `  context: 12:30`, and changes nothing else
- **THEN** the audit record of the write names no changed key

### Requirement: devops config audit-keys reads a config file as YAML 1.2
`devops config audit-keys` SHALL read each config file as YAML 1.2. A credential whose bare value is a word that YAML 1.1 reads as `false`, such as `no`, SHALL count as a plaintext secret.

#### Scenario: A credential with the bare value no
- **WHEN** the active config file holds `ai.api_key: no`, and `devops config audit-keys --json` runs
- **THEN** `plaintext_leaks` names `ai.api_key` of the file, `is_compliant` is false, and the command exits 1

### Requirement: The ConfigMap render reads the config of its template as YAML 1.2
The ConfigMap render SHALL read the config in the ConfigMap template as YAML 1.2. It SHALL validate the settings of the YAML 1.2 read of the config that it writes, which is the config that the Service loads.

#### Scenario: A bare off in the template
- **WHEN** the config of the ConfigMap template holds `roadmap.intake.jev: off` with no quotes
- **THEN** the render succeeds, and a YAML 1.2 read of the rendered config gives the string `off` for `roadmap.intake.jev`

### Requirement: The SSH key prefix reads a project config file as YAML 1.2
The SSH key prefix SHALL read `ssh.key_prefix` from a project config file as YAML 1.2.

#### Scenario: A bare no as the key prefix of a project
- **WHEN** the project config file of a workspace holds `ssh.key_prefix: no` with no quotes, and no other source sets the prefix
- **THEN** the key prefix of the workspace is `no`

## MODIFIED Requirements

### Requirement: A write or an edit of a config file quotes no text of a file that a YAML parser cannot load
When devops-cli reads a config file without the settings load, and ruamel.yaml cannot load the file with the YAML 1.2 reader or with the round trip, the read SHALL fail with a configuration error. The message SHALL name the file and the type of the error, and the line and the column when the error gives them. The message, the exception chain of the error and the output of the command SHALL hold no text of the file.

#### Scenario: A local tag that ruamel.yaml accepts and PyYAML does not
- **WHEN** the active config file holds `ai:`, `  provider: ollama` and `  api_key: !vault FAKE-value-tag`, and `devops config unset ai.provider` runs
- **THEN** the command exits 1 with the message `Cannot read the config file: <file> is not valid YAML (ConstructorError) at line 3, column 12.`, the error has no cause and no context, no output holds `FAKE-value-tag`, and the file stays as it was

#### Scenario: A tagged value that a parser cannot build
- **WHEN** the round trip finds or edits a key in a file that holds `api_key: !!int FAKE-value-int` or `api_key: !!bool FAKE-value-bool`
- **THEN** it fails with a configuration error that names the file and the type of the error, `ValueError` or `KeyError`, the error has no cause and no context, and no text of the error holds the value in any case

#### Scenario: The audit record of a write
- **WHEN** the audit record of a write parses a file that holds `api_key: !vault FAKE-value-tag`
- **THEN** it fails with a configuration error that holds no text of the file
