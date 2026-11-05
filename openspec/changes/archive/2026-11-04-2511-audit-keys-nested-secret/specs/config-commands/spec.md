## ADDED Requirements

### Requirement: devops config audit-keys finds a plaintext secret at its full dotted key
`devops config audit-keys` SHALL examine each credential of the settings at its full dotted key, at any depth of a config file. A credential key that holds a value SHALL fail the audit.

#### Scenario: A plaintext secret three levels deep
- **WHEN** the active config file holds `service.github_app.private_key` with a value, and `devops config audit-keys --json` runs
- **THEN** `plaintext_leaks` holds `<config file path>:service.github_app.private_key`, `is_compliant` is false, and the command exits 1

#### Scenario: A credential key with no value
- **WHEN** the active config file holds `service.github_app.private_key` with no value, and `devops config audit-keys --json` runs
- **THEN** `plaintext_leaks` is empty, `is_compliant` is true, and the command exits 0

## MODIFIED Requirements

### Requirement: A leak of devops config audit-keys names the full path of its file
Each leak that `devops config audit-keys` reports SHALL name the full path of its file, as `<path>:<dotted key>`, in the table output and in each serialized output.

#### Scenario: The table names the full path of the global config file that holds a secret
- **WHEN** the global config file holds `ai.api_key` with a value, the directory walk finds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys` runs
- **THEN** the security alert names `<global config file path>:ai.api_key`, and the command exits 1
