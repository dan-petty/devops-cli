## ADDED Requirements

### Requirement: The alert of devops config audit-keys names a command that removes a leak
The alert that `devops config audit-keys` prints for a plaintext secret SHALL name `devops config set <key>`, which stores a credential in the OS keyring, and `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`, which removes the plaintext value from the file of the leak. The alert SHALL NOT name a value in the argument list.

#### Scenario: A leak in the global config file while a project file is active
- **WHEN** the global config file holds `ai.api_key` with a value, the directory walk finds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys` runs
- **THEN** the alert names `devops config set <key>` and `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`, and the command exits 1. A plain `devops config unset ai.api_key` exits 1 and changes nothing. `DEVOPS_CLI_CONFIG=<global config file> devops config unset ai.api_key` exits 0, and the next `devops config audit-keys` exits 0 with no leak

#### Scenario: A leak in the config.yaml of the current directory that the settings do not merge
- **WHEN** `config.yaml` in the current directory holds `grafana.token` with a value, `DEVOPS_CLI_CONFIG` names another file that holds no secret, and `devops config audit-keys` runs
- **THEN** the alert names the same removal command. `DEVOPS_CLI_CONFIG=<that config.yaml> devops config unset grafana.token` exits 0, and the next `devops config audit-keys` exits 0 with no leak

### Requirement: The help of devops config names the removal command of a leak
The help of `devops config audit-keys` SHALL name the same removal command as its alert. The help of `devops config unset` SHALL say that `DEVOPS_CLI_CONFIG` names the file that the command edits.

#### Scenario: The help names the removal command
- **WHEN** `devops config audit-keys --help` and `devops config unset --help` run
- **THEN** the help of `audit-keys` holds `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`, and the help of `unset` holds the text that `DEVOPS_CLI_CONFIG` names the file that the command edits
