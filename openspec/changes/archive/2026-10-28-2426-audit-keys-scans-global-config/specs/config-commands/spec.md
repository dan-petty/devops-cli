## ADDED Requirements

### Requirement: devops config audit-keys scans each config file that the settings merge
`devops config audit-keys` SHALL scan each config file that the settings load from: the global config file and the project config file. The report SHALL list each of these files that exists under `scanned_config_files`. A plaintext secret in any of these files SHALL fail the audit.

#### Scenario: A plaintext secret in the global config file and a project file that DEVOPS_CLI_CONFIG names
- **WHEN** the global config file holds `ai.api_key` with a value, `DEVOPS_CLI_CONFIG` names a file that holds no secret, and `devops config audit-keys --json` runs
- **THEN** `scanned_config_files` holds the global config file and the file that `DEVOPS_CLI_CONFIG` names, `plaintext_leaks` holds `<global config file path>:ai.api_key`, `is_compliant` is false, and the command exits 1

#### Scenario: A plaintext secret in the global config file and a project file that the directory walk finds
- **WHEN** the global config file holds `ai.api_key` with a value, `DEVOPS_CLI_CONFIG` is not set, the current directory holds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys --json` runs
- **THEN** `scanned_config_files` holds the global config file and `.devcontainer/config.yaml`, `plaintext_leaks` holds `<global config file path>:ai.api_key`, `is_compliant` is false, and the command exits 1

### Requirement: A leak of devops config audit-keys names the full path of its file
Each leak that `devops config audit-keys` reports SHALL name the full path of its file, as `<path>:<section>.<key>`, in the table output and in each serialized output.

#### Scenario: The table names the full path of the global config file that holds a secret
- **WHEN** the global config file holds `ai.api_key` with a value, the directory walk finds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys` runs
- **THEN** the security alert names `<global config file path>:ai.api_key`, and the command exits 1

### Requirement: devops config audit-keys quotes no text of a config file that it cannot load
`devops config audit-keys` SHALL report a config file that the YAML loader of the settings cannot load as unaudited. No output or log of the audit SHALL quote the text of that file.

#### Scenario: A global config file that the YAML loader cannot load
- **WHEN** the global config file holds `ai:` and `  api_key: !!bool <text>`, and `devops config audit-keys --json` runs
- **THEN** `unaudited_config_files` holds the global config file and `plaintext_leaks` is empty. The log names the file and `KeyError`, no output or log holds `<text>`, and the command exits 1
