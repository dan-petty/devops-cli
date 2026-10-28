## ADDED Requirements

### Requirement: devops config audit-keys scans each config file that the settings merge
`devops config audit-keys` SHALL scan each config file that the settings load from: the global config file and the project config file. The report SHALL list each of these files that exists under `scanned_config_files`. A plaintext secret in any of these files SHALL fail the audit.

#### Scenario: A plaintext secret in the global config file and a project file that DEVOPS_CLI_CONFIG names
- **WHEN** the global config file holds `ai.api_key` with a value, `DEVOPS_CLI_CONFIG` names a file that holds no secret, and `devops config audit-keys --json` runs
- **THEN** `scanned_config_files` holds the global config file and the file that `DEVOPS_CLI_CONFIG` names, `plaintext_leaks` holds `config.yaml:ai.api_key`, `is_compliant` is false, and the command exits 1

#### Scenario: A plaintext secret in the global config file and a project file that the directory walk finds
- **WHEN** the global config file holds `ai.api_key` with a value, `DEVOPS_CLI_CONFIG` is not set, the current directory holds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys --json` runs
- **THEN** `scanned_config_files` holds the global config file and `.devcontainer/config.yaml`, `plaintext_leaks` holds `config.yaml:ai.api_key`, `is_compliant` is false, and the command exits 1
